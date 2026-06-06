from __future__ import annotations

import logging
from typing import Any

from tavily import TavilyClient, MissingAPIKeyError, InvalidAPIKeyError, UsageLimitExceededError

from agent.state import SearchResult
from config.settings import settings

logger = logging.getLogger(__name__)


# ── Custom exceptions ─────────────────────────────────────────────────────────

class SearchError(Exception):
    """Base exception for all search failures."""


class SearchAuthError(SearchError):
    """Raised when the Tavily API key is invalid or missing."""


class SearchQuotaError(SearchError):
    """Raised when the Tavily free-tier quota is exhausted."""


class SearchEmptyError(SearchError):
    """Raised when Tavily returns zero results for a query."""


# ── Client singleton ──────────────────────────────────────────────────────────

def _get_client() -> TavilyClient:
    """
    Returns a cached TavilyClient.

    The client is module-level so it's created once per process.
    In Lambda / serverless contexts a new process is spun up per cold start,
    so this is safe.
    """
    return TavilyClient(api_key=settings.tavily_api_key)


_client: TavilyClient | None = None


def _client_singleton() -> TavilyClient:
    global _client
    if _client is None:
        _client = _get_client()
    return _client


# ── Core search function ──────────────────────────────────────────────────────

def search(
    query: str,
    *,
    max_results: int | None = None,
    search_depth: str = "advanced",
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
) -> list[SearchResult]:
    """
    Search the web via Tavily and return structured results.

    Args:
        query:           The search query string.
        max_results:     Number of results to return (defaults to settings value).
        search_depth:    "basic" (fast) or "advanced" (thorough). Defaults to
                         "advanced" for research quality.
        include_domains: Restrict results to these domains (optional).
        exclude_domains: Block results from these domains (optional).

    Returns:
        List of SearchResult TypedDicts, sorted by Tavily relevance score desc.

    Raises:
        SearchAuthError:  API key problem.
        SearchQuotaError: Free-tier limit hit.
        SearchEmptyError: No results found.
        SearchError:      Any other Tavily failure.
    """
    n = max_results or settings.tavily_max_results
    query = query.strip()

    if not query:
        raise ValueError("search() called with an empty query string")

    logger.info("Tavily search | query=%r | max_results=%d", query, n)

    client = _client_singleton()

    try:
        raw: dict[str, Any] = client.search(
            query=query,
            max_results=n,
            search_depth=search_depth,
            include_domains=include_domains or [],
            exclude_domains=exclude_domains or [],
            include_answer=False,    # we want raw results, not a pre-summarised answer
            include_raw_content=False,
        )
    except MissingAPIKeyError as exc:
        raise SearchAuthError("Tavily API key is missing") from exc
    except InvalidAPIKeyError as exc:
        raise SearchAuthError(f"Tavily API key is invalid: {exc}") from exc
    except UsageLimitExceededError as exc:
        raise SearchQuotaError("Tavily free-tier quota exceeded") from exc
    except Exception as exc:
        raise SearchError(f"Tavily search failed: {exc}") from exc

    results = _parse_results(raw)

    if not results:
        raise SearchEmptyError(f"Tavily returned no results for query: {query!r}")

    logger.info("Tavily search | got %d results", len(results))
    return results


# ── Result parsing ────────────────────────────────────────────────────────────

def _parse_results(raw: dict[str, Any]) -> list[SearchResult]:
    """
    Convert the raw Tavily response dict into a list of SearchResult TypedDicts.

    Tavily response shape:
        {
            "query": "...",
            "results": [
                {
                    "title": "...",
                    "url": "...",
                    "content": "...",   # snippet ~200 words
                    "score": 0.97,
                    ...
                },
                ...
            ]
        }
    """
    parsed: list[SearchResult] = []
    seen_urls: set[str] = set()

    for item in raw.get("results", []):
        url = _clean_url(item.get("url", ""))
        if not url or url in seen_urls:
            continue                          # skip malformed or duplicate URLs

        seen_urls.add(url)
        parsed.append(
            SearchResult(
                title=item.get("title", "Untitled").strip(),
                content=_truncate(item.get("content", ""), max_chars=1500),
                url=url,
                score=float(item.get("score", 0.0)),
            )
        )

    # Sort highest relevance first
    parsed.sort(key=lambda r: r["score"], reverse=True)
    return parsed


def _clean_url(url: str) -> str:
    """Strip whitespace and ensure the URL has a scheme."""
    url = url.strip()
    if url and not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def _truncate(text: str, max_chars: int) -> str:
    """Hard-truncate content to avoid bloating the LLM context window."""
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + " …"


# ── Batch search helper ───────────────────────────────────────────────────────

def batch_search(
    queries: list[str],
    *,
    max_results: int | None = None,
) -> dict[str, list[SearchResult]]:
    """
    Run `search()` for every query and return a mapping of query → results.

    Failed individual queries are logged and skipped — the returned dict will
    simply not contain an entry for that query.

    Args:
        queries:     List of query strings (typically the Planner's sub-questions).
        max_results: Passed through to `search()`.

    Returns:
        Dict mapping each successful query string to its search results.
    """
    output: dict[str, list[SearchResult]] = {}

    for query in queries:
        try:
            output[query] = search(query, max_results=max_results)
        except SearchEmptyError:
            logger.warning("No results for sub-question: %r — skipping", query)
        except SearchError as exc:
            logger.error("Search failed for sub-question %r: %s", query, exc)

    return output
