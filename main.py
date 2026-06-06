from __future__ import annotations  # must be the very first statement

# ── Path fix ──────────────────────────────────────────────────────────────────
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# ─────────────────────────────────────────────────────────────────────────────

import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any
from mangum import Mangum

import uvicorn
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# ── LangSmith — must be configured before any LangChain imports ───────────────
from config.settings import settings

os.environ.setdefault("LANGCHAIN_TRACING_V2",  str(settings.langchain_tracing_v2).lower())
os.environ.setdefault("LANGCHAIN_ENDPOINT",    settings.langchain_endpoint)
os.environ.setdefault("LANGCHAIN_API_KEY",     settings.langchain_api_key)
os.environ.setdefault("LANGCHAIN_PROJECT",     settings.langchain_project)

# ── Rest of imports (after env vars are set) ──────────────────────────────────
from agent.graph import run_research
from redis_cache.cache import cache_health, cache_result, get_cached_result, invalidate

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown logic."""
    logger.info("Research Agent API starting up")
    logger.info("Model     : %s", settings.groq_model)
    logger.info("Redis     : %s", settings.redis_url)
    logger.info("LangSmith : tracing=%s project=%s",
                settings.langchain_tracing_v2, settings.langchain_project)
    yield
    logger.info("Research Agent API shutting down")


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Autonomous Research Agent",
    description=(
        "Multi-node LangGraph agent that decomposes queries, searches the web, "
        "self-critiques, and returns citation-backed research reports."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response models ──────────────────────────────────────────────────

class ResearchRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="The research question to investigate.",
        examples=["What are the environmental impacts of lithium mining?"],
    )
    force_refresh: bool = Field(
        default=False,
        description="Set true to bypass Redis cache and re-run the full pipeline.",
    )


class ResearchResponse(BaseModel):
    query: str
    report: str
    confidence_score: int = Field(ge=0, le=100)
    sources: list[str]
    iteration_count: int
    sub_questions: list[str]
    cache_hit: bool
    elapsed_seconds: float


class HealthResponse(BaseModel):
    status: str
    redis: dict[str, Any]
    model: str
    langsmith_tracing: bool
    version: str


class CacheInvalidateRequest(BaseModel):
    query: str = Field(..., min_length=10)


class CacheInvalidateResponse(BaseModel):
    query: str
    invalidated: bool


# ── Middleware: request timing ────────────────────────────────────────────────

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    elapsed = round(time.perf_counter() - t0, 3)
    response.headers["X-Process-Time"] = str(elapsed)
    return response


# ── POST /research ─────────────────────────────────────────────────────────────

@app.post(
    "/research",
    response_model=ResearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Run a research query",
    tags=["Research"],
)
async def research(req: ResearchRequest) -> ResearchResponse:
    """
    Execute the full research pipeline for the given query.

    1. Check Redis cache (unless force_refresh=true).
    2. If cache miss → run the LangGraph pipeline.
    3. Store successful results in Redis.
    4. Return the structured report.

    The response always includes:
    - `report`           — full markdown research report
    - `confidence_score` — 0-100 self-assessed by the Synthesizer
    - `sources`          — deduplicated list of cited URLs
    - `iteration_count`  — how many Critic→Researcher loops ran
    - `cache_hit`        — true if served from Redis
    """
    t0 = time.perf_counter()
    query = req.query.strip()

    logger.info("POST /research | query=%r | force_refresh=%s", query, req.force_refresh)

    # ── 1. Cache lookup ───────────────────────────────────────────────────────
    if not req.force_refresh:
        cached = get_cached_result(query)
        if cached:
            return ResearchResponse(
                query=cached.get("query", query),
                report=cached.get("final_report", ""),
                confidence_score=cached.get("confidence_score", 0),
                sources=cached.get("sources", []),
                iteration_count=cached.get("iteration_count", 0),
                sub_questions=cached.get("sub_questions", []),
                cache_hit=True,
                elapsed_seconds=round(time.perf_counter() - t0, 3),
            )

    # ── 2. Run graph ──────────────────────────────────────────────────────────
    try:
        final_state = run_research(query)
    except Exception as exc:
        logger.error("Graph execution failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Research pipeline failed: {exc}",
        )

    # ── 3. Validate output ────────────────────────────────────────────────────
    report = final_state.get("final_report", "")
    if not report:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Research pipeline completed but produced an empty report.",
        )

    # ── 4. Cache successful result ────────────────────────────────────────────
    cache_result(query, final_state)

    elapsed = round(time.perf_counter() - t0, 3)
    logger.info(
        "POST /research complete | confidence=%d | elapsed=%.2fs | cached=%s",
        final_state.get("confidence_score", 0),
        elapsed,
        not final_state.get("cache_hit", False),
    )

    return ResearchResponse(
        query=final_state.get("query", query),
        report=report,
        confidence_score=final_state.get("confidence_score", 0),
        sources=final_state.get("sources", []),
        iteration_count=final_state.get("iteration_count", 0),
        sub_questions=final_state.get("sub_questions", []),
        cache_hit=False,
        elapsed_seconds=elapsed,
    )


# ── GET /health ────────────────────────────────────────────────────────────────

@app.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check",
    tags=["Ops"],
)
async def health() -> HealthResponse:
    """
    Returns the operational status of all subsystems:
    - API server (implicit — if this responds, it's up)
    - Redis cache connectivity and latency
    - Configured Groq model name
    - LangSmith tracing toggle
    """
    redis_status = cache_health()
    overall = "healthy" if redis_status["connected"] else "degraded"

    return HealthResponse(
        status=overall,
        redis=redis_status,
        model=settings.groq_model,
        langsmith_tracing=settings.langchain_tracing_v2,
        version=app.version,
    )


# ── DELETE /research/cache ────────────────────────────────────────────────────

@app.delete(
    "/research/cache",
    response_model=CacheInvalidateResponse,
    status_code=status.HTTP_200_OK,
    summary="Invalidate cached result for a query",
    tags=["Ops"],
)
async def invalidate_cache(req: CacheInvalidateRequest) -> CacheInvalidateResponse:
    """
    Force-expire the Redis cache entry for a specific query.
    Next call to POST /research with the same query will re-run the pipeline.
    """
    deleted = invalidate(req.query.strip())
    return CacheInvalidateResponse(query=req.query, invalidated=deleted)


# ── Global exception handler ──────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s: %s", request.url, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred. Check server logs."},
    )


# ── Dev runner ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level="info",
    )

# ── AWS Lambda handler ───────────────────────
lambda_handler = Mangum(app, lifespan="off")
