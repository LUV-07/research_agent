from __future__ import annotations

import json
import logging
from pathlib import Path

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from agent.state import AgentState, ResearchData, SearchResult
from config.settings import settings
from tools.search import batch_search, SearchError

logger = logging.getLogger(__name__)

#  Prompt 
_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "researcher_prompt.txt"
_SYSTEM_PROMPT: str = _PROMPT_PATH.read_text(encoding="utf-8")

#  LLM
_llm = ChatGroq(
    model=settings.groq_model,
    api_key=settings.groq_api_key,
    temperature=0.2,   # low → factual extraction, minimal creativity
    max_tokens=1024,
)


#  Node function

def researcher_node(state: AgentState) -> dict:
    """
    LangGraph node: Researcher.

    On first pass  → uses sub_questions from the Planner.
    On loop-back   → uses refined_queries from the Critic, MERGED with any
                     previously passing notes so we don't discard good work.

    Args:
        state: Current AgentState.

    Returns:
        Partial state dict with updated `research_data` and `sources`.
    """
    # Decide which questions to research this round
    critique = state.get("critique")
    is_retry = (
        critique is not None
        and not critique["passed"]
        and critique.get("refined_queries")
    )

    if is_retry:
        queries = critique["refined_queries"]
        logger.info(
            "Researcher node (retry %d) | %d refined queries",
            state["iteration_count"],
            len(queries),
        )
    else:
        queries = state["sub_questions"]
        logger.info(
            "Researcher node (first pass) | %d sub-questions", len(queries)
        )

    #  1. Web search ─
    try:
        search_results: dict[str, list[SearchResult]] = batch_search(
            queries, max_results=settings.tavily_max_results
        )
    except SearchError as exc:
        logger.error("Researcher: batch_search failed: %s", exc)
        return {"error": f"Search failed: {exc}"}

    if not search_results:
        logger.warning("Researcher: no search results returned for any query")
        return {"error": "All searches returned empty results."}

    #  2. LLM synthesis per sub-question ─
    new_notes: list[ResearchData] = []
    new_sources: list[str] = []

    for question, results in search_results.items():
        note, sources = _synthesise(question, results)
        new_notes.append(note)
        new_sources.extend(sources)

    #  3. Merge with previous research on loop-backs ─
    if is_retry:
        existing = state.get("research_data", [])
        merged = _merge_research(existing, new_notes)
    else:
        merged = new_notes

    # Deduplicate sources list
    seen: set[str] = set()
    deduped_sources: list[str] = []
    for url in new_sources:
        if url not in seen:
            seen.add(url)
            deduped_sources.append(url)

    logger.info(
        "Researcher node | produced %d notes, %d new sources",
        len(new_notes),
        len(deduped_sources),
    )

    return {
        "research_data": merged,
        "sources": deduped_sources,   # operator.add in state appends these
        "error": None,
    }


#  Synthesis helper 

def _synthesise(
    question: str, results: list[SearchResult]
) -> tuple[ResearchData, list[str]]:
    """
    Ask the LLM to read raw search results and produce a structured research note.

    Returns:
        (ResearchData TypedDict, list of source URLs from this question)
    """
    human_content = _format_search_input(question, results)

    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=human_content),
    ]

    source_urls: list[str] = [r["url"] for r in results]

    try:
        response = _llm.invoke(messages)
        raw_text = response.content.strip()
        note_data = _parse_note(raw_text, question, results)
        return note_data, source_urls

    except Exception as exc:
        logger.error("Researcher: synthesis failed for %r: %s", question, exc)
        # Return a minimal valid ResearchData so the graph keeps going
        fallback = ResearchData(
            sub_question=question,
            results=results,
        )
        return fallback, source_urls


def _format_search_input(question: str, results: list[SearchResult]) -> str:
    """Format the sub-question + search results into the prompt input."""
    lines = [f"Sub-question: {question}", "", "Search Results:"]
    for i, r in enumerate(results, start=1):
        lines += [
            f"[{i}] Title: {r['title']}",
            f"    URL: {r['url']}",
            f"    Content: {r['content']}",
            "",
        ]
    return "\n".join(lines)


def _parse_note(
    raw_text: str, question: str, results: list[SearchResult]
) -> ResearchData:
    """
    Parse the LLM's JSON response into a ResearchData dict.
    Falls back to a basic ResearchData with raw results on parse failure.
    """
    clean = raw_text.strip()
    if clean.startswith("```"):
        clean = "\n".join(
            line for line in clean.splitlines() if not line.startswith("```")
        ).strip()

    try:
        data = json.loads(clean)
        # Store the synthesised note inside results as a special first item
        # so downstream nodes can read it without schema changes
        note_result = SearchResult(
            title="__synthesised_note__",
            content=data.get("note", ""),
            url="",
            score=1.0,
        )
        parsed_sources = data.get("sources", [])
        source_results: list[SearchResult] = [
            SearchResult(
                title=s.get("title", ""),
                content="",
                url=s.get("url", ""),
                score=0.0,
            )
            for s in parsed_sources
        ]
        return ResearchData(
            sub_question=data.get("sub_question", question),
            results=[note_result] + source_results,
        )
    except (json.JSONDecodeError, KeyError) as exc:
        logger.warning("Researcher: note parse failed (%s), using raw results", exc)
        return ResearchData(sub_question=question, results=results)


#  Merge helper─

def _merge_research(
    existing: list[ResearchData], new_notes: list[ResearchData]
) -> list[ResearchData]:
    """
    Merge existing research with new notes from a retry round.

    Strategy: new notes take precedence for the same sub-question;
    existing notes for other sub-questions are preserved.
    """
    new_questions = {n["sub_question"] for n in new_notes}
    kept_existing = [e for e in existing if e["sub_question"] not in new_questions]
    return kept_existing + new_notes
