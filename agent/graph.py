from __future__ import annotations

import logging

from langgraph.graph import StateGraph, START, END

from agent.state import AgentState
from agent.nodes.planner import planner_node
from agent.nodes.researcher import researcher_node
from agent.nodes.critic import critic_node, route_after_critic
from agent.nodes.synthesizer import synthesizer_node
import time

logger = logging.getLogger(__name__)


# ── Node name constants ────────────────────────────────────────────────────────
# Define as constants so typos are caught at import time, not at runtime.

PLANNER    = "planner"
RESEARCHER = "researcher"
CRITIC     = "critic"
SYNTHESIZER = "synthesizer"


# ── Graph builder ──────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """
    Constructs and returns the uncompiled StateGraph.

    Kept separate from compile() so tests can inspect the graph structure
    without invoking it.
    """
    graph = StateGraph(AgentState)

    # ── Register nodes ────────────────────────────────────────────────────────
    graph.add_node(PLANNER,     planner_node)
    graph.add_node(RESEARCHER,  researcher_node)
    graph.add_node(CRITIC,      critic_node)
    graph.add_node(SYNTHESIZER, synthesizer_node)

    # ── Static edges ──────────────────────────────────────────────────────────
    graph.add_edge(START,      PLANNER)      # entry point
    graph.add_edge(PLANNER,    RESEARCHER)   # always plan → research
    graph.add_edge(RESEARCHER, CRITIC)       # always research → critique

    # ── Conditional edge: Critic → (Researcher | Synthesizer) ─────────────────
    graph.add_conditional_edges(
        source=CRITIC,
        path=route_after_critic,             # returns "researcher" or "synthesizer"
        path_map={
            RESEARCHER:  RESEARCHER,
            SYNTHESIZER: SYNTHESIZER,
        },
    )

    # ── Terminal edge ─────────
    graph.add_edge(SYNTHESIZER, END)

    return graph


# ── Compiled singleton ────────

def _compile() -> object:
    """Compile the graph once at module import time."""
    g = build_graph()
    compiled = g.compile()
    logger.info(
        "LangGraph compiled | nodes=%s",
        [PLANNER, RESEARCHER, CRITIC, SYNTHESIZER],
    )
    return compiled


compiled_graph = _compile()


# ── Convenience runner ────────

def run_research(query: str) -> AgentState:
    """
    High-level helper: run the full research pipeline for a query.

    This is the function called by FastAPI and Redis cache layer.

    Args:
        query: Raw user research question.

    Returns:
        Final AgentState after the graph reaches END.

    Raises:
        Exception: Propagates any unhandled graph-level exception.
    """
    from agent.state import initial_state

    logger.info("Graph run started | query=%r", query)
    initial = initial_state(query)

    try:
        final_state: AgentState = compiled_graph.invoke(
            initial,
            config={
                "recursion_limit": 25,   # hard safety net; our loop cap is ≤2
            },
        )
        logger.info(
            "Graph run complete | confidence=%d | sources=%d | iterations=%d",
            final_state.get("confidence_score", 0),
            len(final_state.get("sources", [])),
            final_state.get("iteration_count", 0),
        )
        return final_state

    except Exception as exc:
        logger.error("Graph run failed: %s", exc, exc_info=True)
        raise
