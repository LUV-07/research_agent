from __future__ import annotations

import json
import logging
from pathlib import Path

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from agent.state import AgentState
from config.settings import settings

logger = logging.getLogger(__name__)

# ── Prompt
_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "planner_prompt.txt"
_SYSTEM_PROMPT: str = _PROMPT_PATH.read_text(encoding="utf-8")

# ── LLM 
_llm = ChatGroq(
    model=settings.groq_model,
    api_key=settings.groq_api_key,
    temperature=0.3,      # low temperature → consistent, structured decomposition
    max_tokens=512,       # sub-questions list is short
)


# ── Node function 

def planner_node(state: AgentState) -> dict:
    """
    LangGraph node: Planner.

    Receives the raw user query, calls the Groq LLM with the planner prompt,
    and returns a list of sub-questions.

    Args:
        state: Current AgentState (only `query` is used).

    Returns:
        Partial state dict with `sub_questions` populated.
        On error, also sets `error`.
    """
    query = state["query"]
    logger.info("Planner node | query=%r", query)

    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=f'User query: "{query}"'),
    ]

    try:
        response = _llm.invoke(messages)
        raw_text: str = response.content.strip()
        logger.debug("Planner raw response: %s", raw_text)

        sub_questions = _parse_sub_questions(raw_text, query)

        logger.info("Planner node | generated %d sub-questions", len(sub_questions))
        return {"sub_questions": sub_questions, "error": None}

    except Exception as exc:
        logger.error("Planner node failed: %s", exc, exc_info=True)
        # Fallback: treat the original query as a single sub-question
        # so the graph can limp forward rather than crash.
        return {
            "sub_questions": [query],
            "error": f"Planner failed ({exc}); using raw query as fallback.",
        }


# ── Helpers 

def _parse_sub_questions(raw_text: str, original_query: str) -> list[str]:
    """
    Parse the LLM response into a clean list of sub-question strings.

    Tries strict JSON parsing first, then falls back to line-by-line extraction
    if the model slips a markdown fence or preamble in despite the prompt.
    """
    # 1. Strip markdown fences if present
    clean = raw_text.strip()
    if clean.startswith("```"):
        lines = clean.splitlines()
        clean = "\n".join(
            line for line in lines if not line.startswith("```")
        ).strip()

    # 2. Try JSON parse
    try:
        data = json.loads(clean)
        questions = data.get("sub_questions", [])
        if isinstance(questions, list) and len(questions) >= 1:
            return _sanitise(questions)
    except (json.JSONDecodeError, AttributeError):
        pass

    # 3. Fallback: extract lines that look like questions
    logger.warning("Planner: JSON parse failed, attempting line extraction")
    questions = [
        line.lstrip("0123456789.-) ").strip()
        for line in raw_text.splitlines()
        if line.strip().endswith("?")
    ]
    if questions:
        return _sanitise(questions)

    # 4. Last resort
    logger.error("Planner: could not extract sub-questions from response")
    return [original_query]


def _sanitise(questions: list) -> list[str]:
    """
    Strip whitespace, enforce question mark, deduplicate, clamp to 3-5.
    """
    seen: set[str] = set()
    clean: list[str] = []
    for q in questions:
        q = str(q).strip()
        if not q:
            continue
        if not q.endswith("?"):
            q += "?"
        if q.lower() not in seen:
            seen.add(q.lower())
            clean.append(q)
    # Clamp to 5 max, ensure at least 1
    return clean[:5] if clean else questions[:1]
