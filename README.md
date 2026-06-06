# Autonomous Research Agent

A production-grade multi-node LangGraph agent that takes a research query,
breaks it into sub-tasks, searches the web, self-critiques, and returns a
structured, citation-backed report.

## Architecture

```
START → Planner → Researcher → Critic ──► Researcher (retry, max 2×)
                                    └───► Synthesizer → END
```

| Node | Role |
|------|------|
| **Planner** | Decomposes query into 3-5 focused sub-questions |
| **Researcher** | Tavily web search + LLM synthesis per sub-question |
| **Critic** | Quality-gates research; loops back or passes forward |
| **Synthesizer** | Writes final report with citations + confidence score |

## Quick Start

### 1. Prerequisites
- Python 3.10+
- Docker (for Redis)
- Free API keys: [Groq](https://console.groq.com/keys) · [Tavily](https://app.tavily.com/home) · [LangSmith](https://smith.langchain.com/settings)

### 2. Install
```bash
git clone <repo-url> && cd research_agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure
```bash
cp .env.template .env
# Edit .env and fill in your API keys
```

### 4. Start Redis
```bash
docker compose up -d
```

### 5. Run the API
```bash
uvicorn main:app --reload
# or: python main.py
```

### 6. Run a query
```bash
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the environmental impacts of lithium mining?"}'
```

## API Reference

### `POST /research`
| Field | Type | Description |
|-------|------|-------------|
| `query` | string | Research question (10-500 chars) |
| `force_refresh` | bool | Bypass Redis cache (default: false) |

**Response:**
```json
{
  "query": "...",
  "report": "# Research Report: ...",
  "confidence_score": 82,
  "sources": ["https://..."],
  "iteration_count": 1,
  "sub_questions": ["..."],
  "cache_hit": false,
  "elapsed_seconds": 14.3
}
```

### `GET /health`
Returns status of API, Redis, and configuration.

### `DELETE /research/cache`
Force-expire a cached query result.

## Project Structure
```
research_agent/
├── main.py                  # FastAPI app
├── agent/
│   ├── graph.py             # LangGraph StateGraph
│   ├── state.py             # AgentState TypedDict
│   └── nodes/               # planner · researcher · critic · synthesizer
├── tools/search.py          # Tavily wrapper
├── config/settings.py       # Env-based config
├── redis_cache/cache.py     # MD5-keyed Redis cache
├── prompts/                 # System prompts (×4)
├── requirements.txt
├── docker-compose.yml
└── .env.template
```
