from __future__ import annotations

import json
import logging
from pathlib import Path

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from agent.state import AgentState
from config.settings import settings

logger = logging.getLogger(__name__)

#  Prompt 
_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "synthesizer_prompt.txt"
_SYSTEM_PROMPT: str = _PROMPT_PATH.read_text(encoding="utf-8")

#  LLM 
_llm = ChatGroq(
    model=settings.groq_model,
    api_key=settings.groq_api_key,
    temperature=0.4,   # slight creativity for readable prose, not zero
    max_tokens=2048,   # report can be long
)


#  Node function ─

def synthesizer_node(state: AgentState) -> dict:
    """
    LangGraph node: Synthesizer.

    Reads all research notes from state, calls the Groq LLM to write a
    structured report, and updates final_report, confidence_score, sources.

    Args:
        state: Current AgentState with approved research_data.

    Returns:
        Partial state dict with final_report, confidence_score, sources.
    """
    query = state["query"]
    research_data = state.get("research_data", [])
    iteration_count = state.get("iteration_count", 0)

    logger.info(
        "Synthesizer node | query=%r | notes=%d | iterations=%d",
        query,
        len(research_data),
        iteration_count,
    )

    if not research_data:
        logger.error("Synthesizer: no research data available")
        return {
            "final_report": _empty_report(query),
            "confidence_score": 0,
            "sources": [],
            "error": "Synthesizer received no research data.",
        }

    human_content = _format_synthesizer_input(query, research_data)

    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=human_content),
    ]

    try:
        response = _llm.invoke(messages)
        raw_text = response.content.strip()
        logger.debug("Synthesizer raw response length: %d chars", len(raw_text))

        report, confidence, sources = _parse_output(raw_text, research_data)

    except Exception as exc:
        logger.error("Synthesizer node failed: %s", exc, exc_info=True)
        report = _error_report(query, str(exc))
        confidence = 0
        sources = _extract_all_urls(research_data)

    logger.info(
        "Synthesizer done | confidence=%d | sources=%d | report_len=%d",
        confidence,
        len(sources),
        len(report),
    )

    return {
        "final_report": report,
        "confidence_score": confidence,
        "sources": sources,
        "error": None,
    }


#  Input formatter ─

def _format_synthesizer_input(query: str, research_data: list) -> str:
    """
    Convert all research notes into the prompt format the Synthesizer expects.
    """
    lines = [f"Original query: {query}", "", "Research Notes:"]

    for i, rd in enumerate(research_data, start=1):
        results = rd.get("results", [])
        note_text = ""
        sources_list = []

        for r in results:
            if r.get("title") == "__synthesised_note__":
                note_text = r.get("content", "")
            elif r.get("url"):
                sources_list.append(
                    {"title": r.get("title", ""), "url": r["url"]}
                )

        if not note_text:
            # Fall back to first result content if no synthesised note
            if results:
                note_text = results[0].get("content", "")

        lines += [
            f"--- Note {i} ---",
            f"Sub-question: {rd['sub_question']}",
            f"Note: {note_text}",
            f"Sources: {json.dumps(sources_list)}",
            "",
        ]

    return "\n".join(lines)


#  Output parser ─

def _parse_output(
    raw_text: str, research_data: list
) -> tuple[str, int, list[str]]:
    """
    Parse the LLM's JSON response into (report_markdown, confidence_score, sources).

    Falls back gracefully if JSON parsing fails.
    """
    clean = raw_text.strip()
    if clean.startswith("```"):
        clean = "\n".join(
            line for line in clean.splitlines() if not line.startswith("```")
        ).strip()

    try:
        data = json.loads(clean)
        report: str = data.get("report", "").replace("\\n", "\n")
        confidence: int = int(data.get("confidence_score", 50))
        confidence = max(0, min(100, confidence))   # clamp 0-100
        sources: list[str] = data.get("sources", [])

        if not report:
            raise ValueError("Empty report in parsed JSON")

        return report, confidence, sources

    except (json.JSONDecodeError, ValueError, KeyError) as exc:
        logger.warning(
            "Synthesizer: JSON parse failed (%s) — using raw text as report", exc
        )
        # The raw text might already be valid markdown even without JSON wrapper
        if len(raw_text) > 200:
            return raw_text, 50, _extract_all_urls(research_data)

        return _error_report("(parse failed)", str(exc)), 0, []


#  Fallback report templates ─

def _empty_report(query: str) -> str:
    return (
        f"# Research Report: {query}\n\n"
        "**Error:** The research pipeline produced no data. "
        "Please check your API keys and try again."
    )


def _error_report(query: str, error: str) -> str:
    return (
        f"# Research Report: {query}\n\n"
        f"**Error during synthesis:** {error}\n\n"
        "The research pipeline encountered an error while generating the final report. "
        "Partial results may be available in the sources list."
    )


def _extract_all_urls(research_data: list) -> list[str]:
    """Collect all non-empty URLs from research_data as a flat deduplicated list."""
    seen: set[str] = set()
    urls: list[str] = []
    for rd in research_data:
        for r in rd.get("results", []):
            url = r.get("url", "")
            if url and url not in seen:
                seen.add(url)
                urls.append(url)
    return urls
