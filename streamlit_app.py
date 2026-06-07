"""
streamlit_app.py

Streamlit frontend for the Autonomous Research Agent.

Run with:
    streamlit run streamlit_app.py

Requires the FastAPI backend to be running at http://127.0.0.1:8000
"""

import time
import requests
import streamlit as st

#  Page config ─
st.set_page_config(
    page_title="Research Agent",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

#  Custom CSS 
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=JetBrains+Mono:wght@400;500&family=Inter:wght@300;400;500&display=swap');

/*  Root theme  */
:root {
    --bg:        #0a0a0f;
    --surface:   #111118;
    --border:    #1e1e2e;
    --accent:    #7c6af7;
    --accent2:   #f97316;
    --text:      #e2e2f0;
    --muted:     #6b6b8a;
    --success:   #22c55e;
    --warning:   #f59e0b;
}

/*  Global  */
html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg) !important;
    color: var(--text) !important;
    font-family: 'Inter', sans-serif !important;
}

[data-testid="stSidebar"] {
    background: var(--surface) !important;
    border-right: 1px solid var(--border) !important;
}

/*  Hide Streamlit chrome  */
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stToolbar"] { display: none; }

/*  Hero header  */
.hero {
    padding: 2.5rem 0 1.5rem;
    border-bottom: 1px solid var(--border);
    margin-bottom: 2rem;
}
.hero-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem;
    letter-spacing: 0.2em;
    color: var(--accent);
    text-transform: uppercase;
    margin-bottom: 0.5rem;
}
.hero-title {
    font-family: 'Syne', sans-serif;
    font-size: 2.8rem;
    font-weight: 800;
    color: var(--text);
    line-height: 1.1;
    margin: 0;
}
.hero-title span { color: var(--accent); }
.hero-sub {
    font-size: 0.95rem;
    color: var(--muted);
    margin-top: 0.6rem;
    font-weight: 300;
}

/*  Input area  */
.stTextArea textarea {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    color: var(--text) !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.95rem !important;
    padding: 1rem !important;
}
.stTextArea textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 2px rgba(124,106,247,0.15) !important;
}

/*  Buttons  */
.stButton > button {
    background: var(--accent) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-family: 'Syne', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    padding: 0.65rem 2rem !important;
    width: 100% !important;
    transition: all 0.2s ease !important;
    letter-spacing: 0.02em !important;
}
.stButton > button:hover {
    background: #6a58e6 !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 20px rgba(124,106,247,0.3) !important;
}

/*  Metric cards  */
.metric-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1rem;
    margin: 1.5rem 0;
}
.metric-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1.1rem 1.2rem;
}
.metric-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 0.4rem;
}
.metric-value {
    font-family: 'Syne', sans-serif;
    font-size: 1.7rem;
    font-weight: 700;
    color: var(--text);
    line-height: 1;
}
.metric-value.accent  { color: var(--accent); }
.metric-value.success { color: var(--success); }
.metric-value.warning { color: var(--warning); }
.metric-value.orange  { color: var(--accent2); }

/*  Confidence bar  */
.conf-bar-bg {
    background: var(--border);
    border-radius: 99px;
    height: 6px;
    margin-top: 0.5rem;
    overflow: hidden;
}
.conf-bar-fill {
    height: 100%;
    border-radius: 99px;
    background: linear-gradient(90deg, var(--accent), var(--accent2));
    transition: width 1s ease;
}

/*  Sub-questions  */
.sq-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin: 0.8rem 0;
}
.sq-item {
    background: var(--surface);
    border: 1px solid var(--border);
    border-left: 3px solid var(--accent);
    border-radius: 0 8px 8px 0;
    padding: 0.6rem 1rem;
    font-size: 0.88rem;
    color: var(--text);
    font-family: 'Inter', sans-serif;
}

/*  Report area  */
.report-container {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 2rem 2.2rem;
    margin-top: 1rem;
    line-height: 1.75;
}
.report-container h1 {
    font-family: 'Syne', sans-serif !important;
    font-size: 1.6rem !important;
    font-weight: 700 !important;
    color: var(--text) !important;
    border-bottom: 1px solid var(--border) !important;
    padding-bottom: 0.8rem !important;
    margin-bottom: 1.2rem !important;
}
.report-container h2 {
    font-family: 'Syne', sans-serif !important;
    font-size: 1.1rem !important;
    font-weight: 600 !important;
    color: var(--accent) !important;
    margin-top: 1.8rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
}
.report-container h3 {
    font-family: 'Inter', sans-serif !important;
    font-size: 1rem !important;
    font-weight: 500 !important;
    color: var(--text) !important;
    margin-top: 1.2rem !important;
}
.report-container p {
    color: #c5c5d8 !important;
    font-size: 0.93rem !important;
}
.report-container ul, .report-container ol {
    color: #c5c5d8 !important;
    font-size: 0.93rem !important;
}
.report-container strong { color: var(--text) !important; }
.report-container code {
    background: var(--border) !important;
    color: var(--accent) !important;
    padding: 0.15em 0.4em !important;
    border-radius: 4px !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.85em !important;
}

/*  Source chips  */
.sources-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-top: 0.8rem;
}
.source-chip {
    background: var(--border);
    border: 1px solid #2a2a3e;
    border-radius: 99px;
    padding: 0.3rem 0.9rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem;
    color: var(--muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 280px;
    cursor: pointer;
    text-decoration: none;
    display: inline-block;
    transition: all 0.15s;
}
.source-chip:hover {
    background: var(--accent);
    color: white;
    border-color: var(--accent);
}

/*  Cache badge  */
.cache-badge {
    display: inline-block;
    background: rgba(34,197,94,0.12);
    color: var(--success);
    border: 1px solid rgba(34,197,94,0.25);
    border-radius: 99px;
    padding: 0.2rem 0.8rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem;
    letter-spacing: 0.08em;
}
.live-badge {
    display: inline-block;
    background: rgba(124,106,247,0.12);
    color: var(--accent);
    border: 1px solid rgba(124,106,247,0.25);
    border-radius: 99px;
    padding: 0.2rem 0.8rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem;
    letter-spacing: 0.08em;
}

/*  Status pill  */
.status-ok {
    color: var(--success);
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
}
.status-err {
    color: #ef4444;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
}

/*  Section label  */
.section-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 0.6rem;
    margin-top: 1.5rem;
}

/*  Sidebar  */
.sidebar-title {
    font-family: 'Syne', sans-serif;
    font-size: 1rem;
    font-weight: 700;
    color: var(--text);
    margin-bottom: 1rem;
}
.history-item {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 0.6rem 0.8rem;
    margin-bottom: 0.5rem;
    font-size: 0.8rem;
    color: var(--muted);
    cursor: pointer;
    transition: all 0.15s;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.history-item:hover {
    border-color: var(--accent);
    color: var(--text);
}

/*  Spinner override  */
.stSpinner > div { border-top-color: var(--accent) !important; }

/*  Selectbox / checkbox  */
.stSelectbox > div > div,
.stCheckbox > label {
    color: var(--text) !important;
}
</style>
""", unsafe_allow_html=True)

#  Constants ─

# TO RUN ON LAMBDA
#API_BASE = "http://127.0.0.1:8000"


# TO RUN ON LOCAL SYSTEM
API_BASE = "http://127.0.0.1:8000"

#  Session state ─
if "history" not in st.session_state:
    st.session_state.history = []
if "result" not in st.session_state:
    st.session_state.result = None
if "selected_query" not in st.session_state:
    st.session_state.selected_query = ""

#  Helper: call API 
def run_research(query: str, force_refresh: bool = False) -> dict:
    response = requests.post(
        f"{API_BASE}/research",
        json={"query": query, "force_refresh": force_refresh},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()

def get_health() -> dict:
    try:
        r = requests.get(f"{API_BASE}/health", timeout=3)
        return r.json()
    except Exception:
        return None

#  Sidebar ─
with st.sidebar:
    st.markdown('<div class="sidebar-title">⚙ Settings</div>', unsafe_allow_html=True)

    force_refresh = st.checkbox("Force refresh (bypass cache)", value=False)

    st.markdown("---")

    # Health check
    health = get_health()
    if health:
        st.markdown(f'<div class="status-ok">● API online</div>', unsafe_allow_html=True)
        redis_ok = health.get("redis", {}).get("connected", False)
        latency  = health.get("redis", {}).get("latency_ms", "—")
        if redis_ok:
            st.markdown(f'<div class="status-ok">● Redis connected ({latency}ms)</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="status-err">✕ Redis offline</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="status-ok">● {health.get("model","")}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="status-err">✕ API offline — start uvicorn first</div>', unsafe_allow_html=True)

    st.markdown("---")

    # History
    if st.session_state.history:
        st.markdown('<div class="sidebar-title">Recent Queries</div>', unsafe_allow_html=True)
        for item in reversed(st.session_state.history[-8:]):
            if st.button(f"↩ {item[:45]}...", key=f"hist_{item[:20]}"):
                st.session_state.selected_query = item

#  Main layout ─
st.markdown("""
<div class="hero">
    <div class="hero-label">Autonomous · Self-Correcting · Citation-Backed</div>
    <h1 class="hero-title">Research <span>Agent</span></h1>
    <p class="hero-sub">LangGraph · Groq LLaMA 3.1 · Tavily Search · Redis Cache</p>
</div>
""", unsafe_allow_html=True)

#  Query input ─
default_query = st.session_state.selected_query or ""

col1, col2 = st.columns([3, 1])
with col1:
    query = st.text_area(
        label="research_query",
        label_visibility="collapsed",
        value=default_query,
        placeholder="Ask anything… e.g. What are the geopolitical risks of rare earth dependency?",
        height=100,
        key="query_input",
    )

with col2:
    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
    run_btn = st.button("🔬  Run Research", use_container_width=True)
    if st.session_state.result:
        if st.button("🗑  Clear", use_container_width=True):
            st.session_state.result = None
            st.rerun()

#  Example queries ─
st.markdown('<div class="section-label">Try an example</div>', unsafe_allow_html=True)
examples = [
    "Impact of AI on software engineering jobs",
    "Environmental cost of lithium mining for EVs",
    "How does quantum computing threaten encryption?",
    "Current state of nuclear fusion energy",
]
ecols = st.columns(len(examples))
for i, ex in enumerate(examples):
    with ecols[i]:
        if st.button(ex, key=f"ex_{i}", use_container_width=True):
            st.session_state.selected_query = ex
            st.rerun()

#  Run the agent ─
if run_btn and query.strip():
    if len(query.strip()) < 10:
        st.error("Query must be at least 10 characters.")
    else:
        with st.spinner("Agent is researching… this takes 15-30 seconds"):
            try:
                t0 = time.time()
                result = run_research(query.strip(), force_refresh=force_refresh)
                result["_client_elapsed"] = round(time.time() - t0, 1)
                st.session_state.result = result

                # Add to history
                if query.strip() not in st.session_state.history:
                    st.session_state.history.append(query.strip())

                st.rerun()

            except requests.exceptions.ConnectionError:
                st.error("Cannot connect to API. Make sure uvicorn is running: `python -m uvicorn main:app --reload`")
            except requests.exceptions.Timeout:
                st.error("Request timed out after 120 seconds. Try a simpler query.")
            except requests.exceptions.HTTPError as e:
                st.error(f"API error: {e.response.status_code} — {e.response.text[:200]}")
            except Exception as e:
                st.error(f"Unexpected error: {e}")

#  Display results ─
if st.session_state.result:
    r = st.session_state.result
    confidence = r.get("confidence_score", 0)
    sources    = r.get("sources", [])
    sub_qs     = r.get("sub_questions", [])
    iterations = r.get("iteration_count", 0)
    elapsed    = r.get("elapsed_seconds", r.get("_client_elapsed", 0))
    cache_hit  = r.get("cache_hit", False)

    #  Metric row 
    conf_color = "success" if confidence >= 75 else "warning" if confidence >= 50 else "orange"
    badge = '<span class="cache-badge">⚡ CACHED</span>' if cache_hit else '<span class="live-badge">🔴 LIVE</span>'

    st.markdown(f"""
    <div class="metric-row">
        <div class="metric-card">
            <div class="metric-label">Confidence</div>
            <div class="metric-value {conf_color}">{confidence}<span style="font-size:1rem;color:var(--muted)">/100</span></div>
            <div class="conf-bar-bg"><div class="conf-bar-fill" style="width:{confidence}%"></div></div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Sources</div>
            <div class="metric-value accent">{len(sources)}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Critic Loops</div>
            <div class="metric-value">{iterations}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Time · {badge}</div>
            <div class="metric-value">{elapsed}<span style="font-size:1rem;color:var(--muted)">s</span></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    #  Tabs 
    tab1, tab2, tab3 = st.tabs(["📄 Report", "🔍 Sub-Questions", "🔗 Sources"])

    with tab1:
        report_md = r.get("report", "No report generated.")
        st.markdown('<div class="report-container">', unsafe_allow_html=True)
        st.markdown(report_md)
        st.markdown('</div>', unsafe_allow_html=True)

        # Download button
        st.download_button(
            label="⬇ Download Report (.md)",
            data=report_md,
            file_name=f"research_report_{int(time.time())}.md",
            mime="text/markdown",
            use_container_width=True,
        )

    with tab2:
        st.markdown('<div class="section-label">Agent decomposed your query into</div>', unsafe_allow_html=True)
        if sub_qs:
            items_html = "".join(f'<div class="sq-item">→ {q}</div>' for q in sub_qs)
            st.markdown(f'<div class="sq-list">{items_html}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<p style="color:var(--muted)">No sub-questions recorded.</p>', unsafe_allow_html=True)

    with tab3:
        st.markdown('<div class="section-label">All cited sources</div>', unsafe_allow_html=True)
        if sources:
            chips_html = "".join(
                f'<a class="source-chip" href="{url}" target="_blank" title="{url}">{url}</a>'
                for url in sources
            )
            st.markdown(f'<div class="sources-grid">{chips_html}</div>', unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            # Also show as numbered list for easy reading
            for i, url in enumerate(sources, 1):
                st.markdown(f"`[{i}]` [{url}]({url})")
        else:
            st.markdown('<p style="color:var(--muted)">No sources recorded.</p>', unsafe_allow_html=True)

elif not run_btn:
    # Empty state
    st.markdown("""
    <div style="text-align:center; padding: 4rem 2rem; color: var(--muted);">
        <div style="font-size:3rem; margin-bottom:1rem">🔬</div>
        <div style="font-family:'Syne',sans-serif; font-size:1.1rem; color:#4a4a6a">
            Enter a research question above and hit Run
        </div>
        <div style="font-size:0.85rem; margin-top:0.5rem">
            The agent will break it down, search the web, self-critique, and return a cited report
        </div>
    </div>
    """, unsafe_allow_html=True)
