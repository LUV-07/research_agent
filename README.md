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

### Option 1 — Lambda (easiest, no local setup needed)

Point Streamlit to the Lambda API:
```powershell
(Get-Content streamlit_app.py) -replace 'API_BASE = .*', 'API_BASE = "https://24w35xlb2a.execute-api.ap-south-1.amazonaws.com"' | Set-Content streamlit_app.py
```

Then run:
```powershell
streamlit run streamlit_app.py
```

---

### Option 2 — Fully Local

Point Streamlit to the local API:
```powershell
(Get-Content streamlit_app.py) -replace 'API_BASE = .*', 'API_BASE = "http://127.0.0.1:8000"' | Set-Content streamlit_app.py
```

Then open 3 terminals:

**Terminal 1 — Start Redis:**
```powershell
docker compose up -d
```

**Terminal 2 — Start FastAPI:**
```powershell
.venv\Scripts\activate
python -m uvicorn main:app --reload --reload-exclude "streamlit_app.py"
```

**Terminal 3 — Start Streamlit:**
```powershell
.venv\Scripts\activate
streamlit run streamlit_app.py
```

Open http://localhost:8501

---

### Switch between Local and Lambda anytime

```powershell
# Switch to Lambda
(Get-Content streamlit_app.py) -replace 'API_BASE = .*', 'API_BASE = "https://24w35xlb2a.execute-api.ap-south-1.amazonaws.com"' | Set-Content streamlit_app.py

# Switch to Local
(Get-Content streamlit_app.py) -replace 'API_BASE = .*', 'API_BASE = "http://127.0.0.1:8000"' | Set-Content streamlit_app.py
```

Always restart Streamlit after switching.

See COMMANDS.md for all other commands.

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
