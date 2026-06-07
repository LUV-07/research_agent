"""
redis_cache/cache.py
────────────────────
Redis-backed cache for research results.

Cache strategy
──────────────
- Key   : MD5 hash of the lowercased, stripped query string
- Value : JSON-serialised AgentState (only the fields needed for a response)
- TTL   : configurable via REDIS_CACHE_TTL (default 3600 s)

Design principles
─────────────────
- FAIL OPEN: if Redis is unreachable, log a warning and proceed without cache.
  The agent still works — it just hits the APIs every time.
- Only cache SUCCESSFUL results (confidence_score > 0, final_report non-empty).
- Cached results have `cache_hit: true` injected so the API response is honest.

Usage:
    from redis_cache.cache import get_cached_result, cache_result, invalidate

    cached = get_cached_result(query)
    if cached:
        return cached           # AgentState dict, cache_hit=True

    result = run_research(query)
    cache_result(query, result)
    return result
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import redis

from config.settings import settings

logger = logging.getLogger(__name__)

# ── Redis client (lazy singleton) ─────────────────────────────────────────────

_redis_client: redis.Redis | None = None


def _get_redis() -> redis.Redis | None:
    """
    Return a connected Redis client, or None if the connection fails.

    Lazy-initialised so import-time failures don't crash the whole app.
    """
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    # Get Redis URL — clean it in case .env has extra content
    raw_url = settings.redis_url.strip()

    # Extract just the URL if it contains extra CLI flags
    for prefix in ["redis-cli --tls -u ", "redis-cli -u "]:
        if prefix in raw_url:
            raw_url = raw_url.split(prefix)[-1].strip()

    # Ensure correct scheme
    if not raw_url.startswith(("redis://", "rediss://", "unix://")):
        logger.warning("Redis URL has invalid scheme — caching disabled")
        return None

    try:
        client = redis.from_url(
            raw_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        client.ping()
        _redis_client = client
        logger.info("Redis connected | url=%s", raw_url)
        return _redis_client
    except Exception as exc:
        logger.warning(
            "Redis unavailable — caching disabled (%s: %s)",
            type(exc).__name__,
            exc,
        )
        return None


# ── Key builder ────────────────────────────────────────────────────────────────

def _make_key(query: str) -> str:
    """
    Deterministic cache key from the query string.

    Normalise (lowercase + strip) before hashing so
    "What is AI?" and "what is ai?" hit the same cache entry.

    Returns a string like:  research:a1b2c3d4e5f6...
    """
    normalised = query.lower().strip()
    digest = hashlib.md5(normalised.encode("utf-8")).hexdigest()
    return f"research:{digest}"


# ── Serialisation ─────────────────────────────────────────────────────────────

# Only these fields are cached — full research_data can be large and is
# not needed to serve a cached API response.
_CACHED_FIELDS = [
    "query",
    "final_report",
    "confidence_score",
    "sources",
    "iteration_count",
    "sub_questions",
]


def _serialise(state: dict) -> str:
    """Extract cacheable fields from AgentState and serialise to JSON."""
    slim = {k: state.get(k) for k in _CACHED_FIELDS}
    slim["cache_hit"] = True
    return json.dumps(slim, ensure_ascii=False)


def _deserialise(raw: str) -> dict[str, Any]:
    """Deserialise a cached JSON string back to a partial AgentState dict."""
    return json.loads(raw)


# ── Public API ────────────────────────────────────────────────────────────────

def get_cached_result(query: str) -> dict[str, Any] | None:
    """
    Look up a query in the cache.

    Args:
        query: Raw user query string.

    Returns:
        Partial AgentState dict with `cache_hit=True` if found, else None.
    """
    client = _get_redis()
    if client is None:
        return None

    key = _make_key(query)
    try:
        raw = client.get(key)
        if raw is None:
            logger.debug("Cache MISS | key=%s", key)
            return None
        logger.info("Cache HIT  | key=%s | query=%r", key, query[:60])
        return _deserialise(raw)
    except redis.RedisError as exc:
        logger.warning("Cache GET error (%s) — treating as miss", exc)
        return None


def cache_result(query: str, state: dict) -> bool:
    """
    Store a research result in the cache.

    Only caches results that have a non-empty report and a positive
    confidence score. Partial / error results are never cached.

    Args:
        query: Raw user query string.
        state: Final AgentState dict from the graph run.

    Returns:
        True if successfully cached, False otherwise.
    """
    # Quality gate
    if not state.get("final_report") or state.get("confidence_score", 0) <= 0:
        logger.debug("Cache SKIP — result quality insufficient")
        return False

    client = _get_redis()
    if client is None:
        return False

    key = _make_key(query)
    try:
        serialised = _serialise(state)
        client.setex(key, settings.redis_cache_ttl, serialised)
        logger.info(
            "Cache SET  | key=%s | ttl=%ds | query=%r",
            key,
            settings.redis_cache_ttl,
            query[:60],
        )
        return True
    except redis.RedisError as exc:
        logger.warning("Cache SET error (%s) — continuing without cache", exc)
        return False


def invalidate(query: str) -> bool:
    """
    Remove a specific query from the cache (e.g. to force a refresh).

    Args:
        query: Raw user query string.

    Returns:
        True if the key existed and was deleted, False otherwise.
    """
    client = _get_redis()
    if client is None:
        return False

    key = _make_key(query)
    try:
        deleted = client.delete(key)
        if deleted:
            logger.info("Cache INVALIDATED | key=%s", key)
        return bool(deleted)
    except redis.RedisError as exc:
        logger.warning("Cache DELETE error (%s)", exc)
        return False


def cache_health() -> dict[str, Any]:
    """
    Return a health status dict for the /health endpoint.

    Returns:
        Dict with keys: connected (bool), latency_ms (float|None), url (str).
    """
    client = _get_redis()
    if client is None:
        return {"connected": False, "latency_ms": None, "url": settings.redis_url}

    try:
        import time
        t0 = time.perf_counter()
        client.ping()
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {"connected": True, "latency_ms": latency_ms, "url": settings.redis_url}
    except redis.RedisError:
        return {"connected": False, "latency_ms": None, "url": settings.redis_url}