from __future__ import annotations

from typing import Annotated, Any
from typing_extensions import TypedDict
import operator


#  Supporting types 

class SearchResult(TypedDict):
    """One result returned by Tavily for a single sub-question."""
    title: str
    content: str
    url: str
    score: float          # Tavily relevance score 0-1


class ResearchData(TypedDict):
    """Bundled search results for a single sub-question."""
    sub_question: str
    results: list[SearchResult]


class CritiqueDecision(TypedDict):
    """Structured output from the Critic node."""
    passed: bool                     # True  → go to Synthesizer
                                     # False → loop back to Researcher
    gaps: list[str]                  # issues found (empty if passed)
    refined_queries: list[str]       # replacement sub-questions (if not passed)
    reasoning: str                   # short explanation for the trace log


#  Main state 

class AgentState(TypedDict):
    """
    Shared state object passed between every node.

    Annotation rules
    
    - `Annotated[list, operator.add]`  → LangGraph *appends* new items
      instead of replacing the list. Used for sources so no node
      accidentally clobbers another node's data.
    - Plain types (str, int, bool, …)  → last-write wins (normal behaviour).
    """

    #  Input ─
    query: str
   

    #  Planner outputs ─
    sub_questions: list[str]
   
    #  Researcher outputs 
    research_data: list[ResearchData]
    

    #  Critic outputs 
    critique: CritiqueDecision | None
    
    critique_passed: bool
   
    iteration_count: int
   

    #  Synthesizer outputs ─
    final_report: str
    

    confidence_score: int
    

    sources: Annotated[list[str], operator.add]
    

    #  Internal / metadata ─
    error: str | None
    

    cache_hit: bool
    

#  Default factory ─

def initial_state(query: str) -> AgentState:
    """
    Returns a fully-initialised AgentState for a new research job.

    Always use this factory instead of constructing the TypedDict by hand,
    so defaults stay in one place.

    Args:
        query: Raw user query string.

    Returns:
        AgentState with all fields set to safe zero-values.
    """
    return AgentState(
        query=query,
        sub_questions=[],
        research_data=[],
        critique=None,
        critique_passed=False,
        iteration_count=0,
        final_report="",
        confidence_score=0,
        sources=[],
        error=None,
        cache_hit=False,
    )
