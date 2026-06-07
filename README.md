# Research Agent

I built this to learn how agentic AI systems work end to end.
It takes a research question, breaks it down automatically,
searches the web, checks its own answers, and returns a cited report.

---

## How it works

The agent runs in 4 steps automatically:

**Planner** — breaks your question into 3-5 smaller searchable questions

**Researcher** — searches the web for each one using Tavily

**Critic** — reads the results and decides if they are good enough.
If not, it sends the researcher back with better queries (max 3 retries)

**Synthesizer** — writes the final report with inline citations
and a confidence score out of 100

---

## What I learned building this

Agentic loops are harder than they look — getting the critic to give
useful feedback without looping forever took most of the debugging time.

Redis caching made a real difference — repeat queries go from 120 seconds
to under 1 second.

AWS Lambda cold starts are painful with large Docker images. First request
takes 3-4 seconds longer than subsequent ones.

LangSmith was genuinely useful — being able to see exactly what prompt
went into each node made debugging much faster.

---

## Tech I used

| What | Tool |
|---|---|
| Agent framework | LangGraph |
| LLM | Groq LLaMA 3.3-70B (free tier) |
| Web search | Tavily API |
| Backend | FastAPI |
| Frontend | Streamlit |
| Cache | Redis via Upstash |
| Deployment | AWS Lambda + ECR + API Gateway |
| Observability | LangSmith |
| Container | Docker |

---

## How to run it

**On Lambda (easiest — no local setup needed):**
```bash
streamlit run streamlit_app.py
```

**Fully local:**
```bash
docker compose up -d
python -m uvicorn main:app --reload
streamlit run streamlit_app.py
```

Open http://localhost:8501

See COMMANDS.md for all commands and shortcuts.

---

## Project Structure

```
research_agent/
├── main.py                  # FastAPI app
├── streamlit_app.py         # Streamlit UI
├── Dockerfile               # Lambda container
├── agent/
│   ├── graph.py             # LangGraph StateGraph
│   ├── state.py             # AgentState TypedDict
│   └── nodes/               # planner · researcher · critic · synthesizer
├── tools/search.py          # Tavily wrapper
├── config/settings.py       # Env-based config
├── redis_cache/cache.py     # MD5-keyed Redis cache
├── prompts/                 # System prompts (x4)
├── requirements.txt
├── docker-compose.yml
├── COMMANDS.md              # All run commands
└── .env.template            # API keys template
```

---

## Live API

https://24w35xlb2a.execute-api.ap-south-1.amazonaws.com/health
