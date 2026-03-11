"""
Web search service using self-hosted SearXNG.

Queries SearXNG's JSON API, extracts top results, and formats them
for injection into the LLM context so the model can cite up-to-date
information.
"""

import re
from typing import Any, Dict, List, Optional

import httpx

from app.config import Settings, get_settings

_TRIVIAL_PATTERNS = re.compile(
    r"^("
    r"h(i|ey|ello|owdy)"
    r"|yo"
    r"|sup"
    r"|thanks?( you)?"
    r"|thx"
    r"|ok(ay)?"
    r"|sure"
    r"|yep|yeah|yes|no|nope"
    r"|bye|goodbye|see ya"
    r"|good (morning|afternoon|evening|night)"
    r"|gm|gn"
    r"|lol|lmao|haha"
    r"|\\?"   # lone question mark
    r"|\\!"
    r")$",
    re.IGNORECASE,
)


class WebSearchService:
    """Queries SearXNG for web results and formats them for LLM context."""

    def __init__(self, settings: Settings):
        self.base_url = settings.searxng_url.rstrip("/")
        self.enabled = settings.web_search_enabled
        self.timeout = settings.web_search_timeout
        self.max_results = settings.web_search_max_results

    def should_search(self, message: str) -> bool:
        """Return False only for trivial/greeting messages."""
        if not self.enabled:
            return False
        cleaned = message.strip().rstrip("?!., ")
        if len(cleaned) < 2:
            return False
        return not _TRIVIAL_PATTERNS.match(cleaned)

    async def search(self, query: str, num_results: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Query SearXNG and return a list of result dicts with
        keys: title, url, content (snippet).

        Returns an empty list on any failure so chat can proceed without search.
        """
        limit = num_results or self.max_results
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    f"{self.base_url}/search",
                    params={
                        "q": query,
                        "format": "json",
                        "engines": "google,duckduckgo,brave,wikipedia",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            print(f"[web_search] SearXNG query failed: {exc}")
            return []

        raw_results = data.get("results", [])
        seen_urls: set[str] = set()
        results: List[Dict[str, Any]] = []

        for item in raw_results:
            url = item.get("url", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            snippet = (item.get("content") or "").strip()
            if not snippet:
                continue
            if len(snippet) > 300:
                snippet = snippet[:300].rsplit(" ", 1)[0] + "..."
            results.append({
                "title": (item.get("title") or "Untitled").strip(),
                "url": url,
                "content": snippet,
            })
            if len(results) >= limit:
                break

        print(f"[web_search] Found {len(results)} results for: {query[:80]}")
        return results

    def format_results_for_context(self, results: List[Dict[str, Any]]) -> str:
        """Format search results into a text block for the system message."""
        if not results:
            return ""
        lines = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "Untitled")
            url = r.get("url", "")
            snippet = r.get("content", "")
            lines.append(f"[{i}] {title}\n    URL: {url}\n    {snippet}")
        return "\n\n".join(lines)


# ── Singleton ────────────────────────────────────────────────────

_web_search_service: Optional[WebSearchService] = None


def get_web_search_service() -> WebSearchService:
    """Get cached WebSearchService instance."""
    global _web_search_service
    if _web_search_service is None:
        _web_search_service = WebSearchService(get_settings())
    return _web_search_service
