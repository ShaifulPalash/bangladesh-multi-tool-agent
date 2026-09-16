"""
Web search tool for the Bangladesh Multi-Tool Agent.

Search priority:
    1. Tavily — primary search provider
    2. DDGS (DuckDuckGo) — fallback search provider

Tavily is used when TAVILY_API_KEY is available.
If Tavily is unavailable or fails, DDGS is used as a fallback.

The tool returns clean text results to the main AI agent.
"""

import os

from langchain_core.tools import tool

try:
    from langchain_tavily import TavilySearch
except ImportError:
    TavilySearch = None

try:
    from ddgs import DDGS
except ImportError:
    DDGS = None


def _format_tavily_results(results) -> str:
    """
    Convert Tavily search results into clean text.

    Tavily normally returns a dictionary containing a
    'results' list. Each result is normally a dictionary
    containing fields such as 'content' and 'url'.
    """

    # Tavily may return:
    # {"results": [...]}
    if isinstance(results, dict):
        results = results.get("results", [])

    # Make sure results are iterable as a list.
    if not isinstance(results, list):
        results = [results]

    formatted = []

    for result in results:
        # Normal Tavily result.
        if isinstance(result, dict):
            content = str(result.get("content", "")).strip()
            url = str(result.get("url", "")).strip()

            if not content:
                continue

            if url:
                formatted.append(
                    f"- {content}\n  Source: {url}"
                )
            else:
                formatted.append(f"- {content}")

        # Protect against a string result.
        elif isinstance(result, str):
            content = result.strip()

            if content:
                formatted.append(f"- {content}")

    return "\n\n".join(formatted)


def _format_ddgs_results(results) -> str:
    """
    Convert DDGS search results into clean text.

    DDGS normally returns dictionaries like:

        {
            "title": "...",
            "href": "...",
            "body": "..."
        }
    """

    formatted = []

    for result in results:
        if isinstance(result, dict):
            title = str(result.get("title", "")).strip()
            body = str(result.get("body", "")).strip()
            href = str(result.get("href", "")).strip()

            # Prefer the body because it contains the search snippet.
            content = body or title

            if not content:
                continue

            if href:
                formatted.append(
                    f"- {content}\n  Source: {href}"
                )
            else:
                formatted.append(f"- {content}")

        # Protect against unexpected string results.
        elif isinstance(result, str):
            content = result.strip()

            if content:
                formatted.append(f"- {content}")

    return "\n\n".join(formatted)


def _search_tavily(query: str) -> str:
    """
    Search using Tavily.

    Returns:
        Formatted search results.

    Raises:
        RuntimeError: If Tavily is unavailable or the search fails.
    """

    if TavilySearch is None:
        raise RuntimeError(
            "langchain-tavily is not installed."
        )

    if not os.getenv("TAVILY_API_KEY", "").strip():
        raise RuntimeError(
            "TAVILY_API_KEY is not configured."
        )

    search = TavilySearch(
        max_results=5,
        topic="general",
    )

    results = search.invoke({"query": query})

    formatted = _format_tavily_results(results)

    if not formatted:
        raise RuntimeError(
            "Tavily returned no usable search results."
        )

    return formatted


def _search_ddgs(query: str) -> str:
    """
    Search using DDGS (DuckDuckGo Search).

    Returns:
        Formatted search results.

    Raises:
        RuntimeError: If DDGS is unavailable or the search fails.
    """

    if DDGS is None:
        raise RuntimeError(
            "ddgs is not installed."
        )

    with DDGS() as ddgs:
        results = list(
            ddgs.text(
                query,
                max_results=5,
            )
        )

    formatted = _format_ddgs_results(results)

    if not formatted:
        raise RuntimeError(
            "DDGS returned no usable search results."
        )

    return formatted


def _run_search(query: str) -> str:
    """
    Run a web search.

    Tavily is the primary provider.
    DDGS is used automatically if Tavily fails.
    """

    query = query.strip()

    if not query:
        return "Please provide a search query."

    # ---------------------------------------------------------
    # 1. Try Tavily first.
    # ---------------------------------------------------------
    try:
        return _search_tavily(query)

    except Exception as tavily_error:
        # -----------------------------------------------------
        # 2. Fall back to DDGS.
        # -----------------------------------------------------
        try:
            return _search_ddgs(query)

        except Exception as ddgs_error:
            return (
                "Web search failed.\n\n"
                f"Tavily error: {tavily_error}\n"
                f"DDGS error: {ddgs_error}"
            )


@tool
def web_search_tool(query: str) -> str:
    """
    Search the web for general-knowledge questions.

    Use this tool for questions about:
      - Definitions
      - Government organizations
      - Policies
      - History
      - Culture
      - General information
      - Current information

    Do not use this tool for questions that can be answered
    directly from the local Bangladesh databases.
    """

    return _run_search(query)
