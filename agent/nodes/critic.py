from __future__ import annotations

import json
import logging
from pathlib import Path

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from agent.state import AgentState, CritiqueDecision
from config.settings import settings

logger = logging.getLogger(__name__)

# ── Prompt ────────────────────────────────────────────────────────────────────
_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "critic_prompt.txt"
_SYSTEM_PROMPT: str = _PROMPT_PATH.read_text(encoding="utf-8")

# ── LLM ──────────────────────────────────────────────────────────────────────
_llm = ChatGroq(
    model=settings.groq_model,
    api_key=settings.groq_api_key,
    temperature=0.1,   # near-zero → deterministic quality judgement
    max_tokens=768,
)


# ── Node function ─────────────────────────────────────────────────────────────

def critic_node(state: AgentState) -> dict:
    """
    LangGraph node: Critic.

    Evaluates research_data quality and updates `critique`, `critique_passed`,
    and `iteration_count` in the state.

    Args:
        state: Current AgentState.

    Returns:
        Partial state dict with `critique`, `critique_passed`, `iteration_count`.
    """
    iteration = state["iteration_count"]
    research_data = state.get("research_data", [])
    query = state["query"]

    logger.info(
        "Critic node | iteration=%d / max=%d | notes=%d",
        iteration,
        settings.max_critic_iterations,
        len(research_data),
    )

    # ── Hard cap guard ────────────────────────────────────────────────────────
    if iteration >= settings.max_critic_iterations:
        logger.warning(
            "Critic: max iterations (%d) reached — force-passing to Synthesizer",
            settings.max_critic_iterations,
        )
        forced_pass = CritiqueDecision(
            passed=True,
            gaps=[],
            refined_queries=[],
            reasoning=(
                f"Max iterations ({settings.max_critic_iterations}) reached. "
                "Passing with available research data."
            ),
        )
        return {
            "critique": forced_pass,
            "critique_passed": True,
            "iteration_count": iteration,
        }

    # ── Build critic input ────────────────────────────────────────────────────
    human_content = _format_critic_input(query, research_data, iteration)

    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=human_content),
    ]

    try:
        response = _llm.invoke(messages)
        raw_text = response.content.strip()
        logger.debug("Critic raw response: %s", raw_text)

        decision = _parse_decision(raw_text)

    except Exception as exc:
        logger.error("Critic node failed: %s", exc, exc_info=True)
        # On LLM failure, conservatively pass so the graph doesn't stall
        decision = CritiqueDecision(
            passed=True,
            gaps=[],
            refined_queries=[],
            reasoning=f"Critic LLM call failed ({exc}); passing conservatively.",
        )

    new_iteration = iteration + (0 if decision["passed"] else 1)

    logger.info(
        "Critic decision | passed=%s | gaps=%d | iteration now=%d",
        decision["passed"],
        len(decision["gaps"]),
        new_iteration,
    )

    return {
        "critique": decision,
        "critique_passed": decision["passed"],
        "iteration_count": new_iteration,
    }


# ── Router (conditional edge) ─────────────────────────────────────────────────

def route_after_critic(state: AgentState) -> str:
    """
    LangGraph conditional edge function called after the Critic node.

    Returns:
        "researcher"  → loop back for another research pass
        "synthesizer" → proceed to final report generation
    """
    if state["critique_passed"]:
        logger.info("Critic router → synthesizer")
        return "synthesizer"
    logger.info("Critic router → researcher (retry)")
    return "researcher"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _format_critic_input(query: str, research_data: list, iteration: int) -> str:
    """Serialise the research notes into the prompt format the critic expects."""
    lines = [
        f"Original query: {query}",
        f"Iteration: {iteration}",
        "",
        "Research Notes:",
    ]

    for i, rd in enumerate(research_data, start=1):
        results = rd.get("results", [])
        # Check if synthesised note is present (inserted by researcher node)
        note_text = ""
        sources_count = 0
        for r in results:
            if r.get("title") == "__synthesised_note__":
                note_text = r.get("content", "")
            elif r.get("url"):
                sources_count += 1

        sufficient = bool(note_text)   # if we have a synthesised note, it was sufficient

        lines += [
            f"--- Note {i} ---",
            f"Sub-question: {rd['sub_question']}",
            f"Note: {note_text or '[No synthesised note — raw results only]'}",
            f"Sufficient: {sufficient}",
            f"Sources: {sources_count}",
            "",
        ]

    return "\n".join(lines)


def _parse_decision(raw_text: str) -> CritiqueDecision:
    """Parse the LLM's JSON response into a CritiqueDecision TypedDict."""
    clean = raw_text.strip()
    if clean.startswith("```"):
        clean = "\n".join(
            line for line in clean.splitlines() if not line.startswith("```")
        ).strip()

    try:
        data = json.loads(clean)
        return CritiqueDecision(
            passed=bool(data.get("passed", False)),
            gaps=data.get("gaps", []),
            refined_queries=data.get("refined_queries", []),
            reasoning=data.get("reasoning", ""),
        )
    except (json.JSONDecodeError, KeyError) as exc:
        logger.error("Critic: failed to parse decision JSON (%s): %r", exc, raw_text[:200])
        # Default to pass on parse error
        return CritiqueDecision(
            passed=True,
            gaps=[],
            refined_queries=[],
            reasoning=f"Parse error ({exc}); defaulting to pass.",
        )
