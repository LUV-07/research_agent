# Research Agent — Commands Reference

## ─── RUN ON LOCAL ──────────────────────────────────────────────────────────

### Step 1 — Point Streamlit to Local API
```powershell
(Get-Content D:\research_agent\streamlit_app.py) -replace 'API_BASE = .*', 'API_BASE = "http://127.0.0.1:8000"' | Set-Content D:\research_agent\streamlit_app.py
```

### Step 2 — Start Redis (Window 1)
```powershell
cd D:\research_agent
docker compose up -d
```

### Step 3 — Start FastAPI (Window 2)
```powershell
cd D:\research_agent
.venv\Scripts\activate
python -m uvicorn main:app --reload --reload-exclude "streamlit_app.py"
```

### Step 4 — Start Streamlit (Window 3)
```powershell
cd D:\research_agent
.venv\Scripts\activate
streamlit run streamlit_app.py
```

### Step 5 — Open Browser
```
http://localhost:8501
```

---

## ─── RUN ON LAMBDA ─────────────────────────────────────────────────────────

### Step 1 — Point Streamlit to Lambda API
```powershell
(Get-Content D:\research_agent\streamlit_app.py) -replace 'API_BASE = .*', 'API_BASE = "https://24w35xlb2a.execute-api.ap-south-1.amazonaws.com"' | Set-Content D:\research_agent\streamlit_app.py
```

### Step 2 — Start Streamlit only (Window 1)
```powershell
cd D:\research_agent
.venv\Scripts\activate
streamlit run streamlit_app.py
```

### Step 3 — Open Browser
```
http://localhost:8501
```

---

## ─── SWITCH BETWEEN LOCAL AND LAMBDA ───────────────────────────────────────

### Switch to Local
```powershell
(Get-Content D:\research_agent\streamlit_app.py) -replace 'API_BASE = .*', 'API_BASE = "http://127.0.0.1:8000"' | Set-Content D:\research_agent\streamlit_app.py
```

### Switch to Lambda
```powershell
(Get-Content D:\research_agent\streamlit_app.py) -replace 'API_BASE = .*', 'API_BASE = "https://24w35xlb2a.execute-api.ap-south-1.amazonaws.com"' | Set-Content D:\research_agent\streamlit_app.py
```

### Check which API is active
```powershell
Select-String "API_BASE" D:\research_agent\streamlit_app.py
```

### Always restart Streamlit after switching
```powershell
# Press Ctrl+C then:
streamlit run streamlit_app.py
```

---

## ─── USEFUL COMMANDS ────────────────────────────────────────────────────────

### Check Redis is running
```powershell
docker ps
docker exec research_agent_redis redis-cli ping
```

### Check API health (Local)
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -Method GET
```

### Check API health (Lambda)
```powershell
Invoke-RestMethod -Uri "https://24w35xlb2a.execute-api.ap-south-1.amazonaws.com/health" -Method GET
```

### Run a research query (Local)
```powershell
$body = '{"query": "Your research question here"}'
Invoke-RestMethod -Uri "http://127.0.0.1:8000/research" -Method POST -ContentType "application/json" -Body $body
```

### Run a research query (Lambda)
```powershell
$body = '{"query": "Your research question here"}'
Invoke-RestMethod -Uri "https://24w35xlb2a.execute-api.ap-south-1.amazonaws.com/research" -Method POST -ContentType "application/json" -Body $body
```

### Clear cached result
```powershell
$body = '{"query": "Your query here"}'
Invoke-RestMethod -Uri "http://127.0.0.1:8000/research/cache" -Method DELETE -ContentType "application/json" -Body $body
```

### Stop Redis
```powershell
docker compose down
``

### Update Lambda with new code
```powershell
cd D:\research_agent
docker buildx build --platform linux/amd64 --provenance=false -t 259732629822.dkr.ecr.ap-south-1.amazonaws.com/research-agent:latest --push .
aws lambda update-function-code --function-name research-agent --image-uri 259732629822.dkr.ecr.ap-south-1.amazonaws.com/research-agent:latest --region ap-south-1
```


## ─── FREE TIER LIMITS ───────────────────────────────────────────────────────

| Service       | Free Limit              | Per Run Usage     |
|---------------|-------------------------|-------------------|
| Groq          | 1,000 req/day           | ~4 requests       |
| Tavily        | 1,000 searches/month    | ~15 searches      |
| AWS Lambda    | 1M requests/month       | 1 request         |
| Upstash Redis | 10,000 commands/day     | ~5 commands       |
| LangSmith     | 5,000 traces/month      | 1 trace           |

Estimated free queries: ~66/month (limited by Tavily)
