"""
Web search service using self-hosted SearXNG.

Queries SearXNG's JSON API, extracts top results, and formats them
for injection into the LLM context so the model can cite up-to-date
information.  Optionally fetches full-page content via trafilatura
for the top N results to give the model richer evidence.
"""

import asyncio
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

try:
    import trafilatura
except ImportError:  # graceful fallback if not installed
    trafilatura = None  # type: ignore[assignment]

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

# Domain patterns for source classification
_OFFICIAL_PATTERNS = (
    ".gov", ".edu", ".mil",
    "docs.", "developer.", "devdocs.",
    "mozilla.org/en-US/docs",
)
_REFERENCE_DOMAINS = (
    "wikipedia.org", "wikimedia.org", "wikidata.org",
    "britannica.com",
)
_FORUM_DOMAINS = (
    "stackoverflow.com", "stackexchange.com", "superuser.com",
    "serverfault.com", "askubuntu.com",
    "reddit.com", "quora.com",
    "github.com/issues", "github.com/discussions",
    "discourse.",
)
_NEWS_DOMAINS = (
    "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk",
    "nytimes.com", "theguardian.com", "washingtonpost.com",
    "arstechnica.com", "techcrunch.com", "theverge.com",
    "wired.com", "bloomberg.com",
)


def _extract_domain(url: str) -> str:
    """Pull hostname from a URL, stripping www. prefix."""
    try:
        host = urlparse(url).hostname or ""
        return host.removeprefix("www.")
    except Exception:
        return ""


def _classify_source(url: str) -> str:
    """Categorise a URL as official / reference / forum / news / web."""
    lower = url.lower()
    domain = _extract_domain(url).lower()
    for pat in _OFFICIAL_PATTERNS:
        if pat in domain or pat in lower:
            return "official"
    for pat in _REFERENCE_DOMAINS:
        if pat in domain:
            return "reference"
    for pat in _FORUM_DOMAINS:
        if pat in lower:
            return "forum"
    for pat in _NEWS_DOMAINS:
        if pat in domain:
            return "news"
    return "web"


_TRUST_LABELS: Dict[str, str] = {
    "official": "high trust",
    "reference": "high trust, may lag",
    "news": "high trust for events",
    "forum": "moderate trust",
    "web": "low trust, cross-check",
}


def _is_duplicate_content(new_snippet: str, existing_snippets: List[str], threshold: float = 0.6) -> bool:
    """Check if new_snippet is too similar to any existing snippet (Jaccard on word sets)."""
    new_words = set(new_snippet.lower().split())
    if not new_words:
        return False
    for existing in existing_snippets:
        existing_words = set(existing.lower().split())
        if not existing_words:
            continue
        intersection = len(new_words & existing_words)
        union = len(new_words | existing_words)
        if union > 0 and intersection / union >= threshold:
            return True
    return False


class WebSearchService:
    """Queries SearXNG for web results and formats them for LLM context."""

    def __init__(self, settings: Settings):
        self.base_url = settings.searxng_url.rstrip("/")
        self.enabled = settings.web_search_enabled
        self.timeout = settings.web_search_timeout
        self.max_results = settings.web_search_max_results
        self.snippet_max_chars = settings.web_search_snippet_max_chars
        self.fetch_full_content = settings.web_search_fetch_full_content
        self.full_content_count = settings.web_search_full_content_count
        self.full_content_max_chars = settings.web_search_full_content_max_chars
        self.full_content_timeout = settings.web_search_full_content_timeout

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
        keys: title, url, content, domain, source_type, engines, published_date.

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
        existing_snippets: List[str] = []
        results: List[Dict[str, Any]] = []

        for item in raw_results:
            url = item.get("url", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            snippet = (item.get("content") or "").strip()
            if not snippet:
                continue
            # Deduplicate near-identical snippets from different engines
            if _is_duplicate_content(snippet, existing_snippets):
                continue
            if len(snippet) > self.snippet_max_chars:
                snippet = snippet[:self.snippet_max_chars].rsplit(" ", 1)[0] + "..."
            existing_snippets.append(snippet)
            results.append({
                "title": (item.get("title") or "Untitled").strip(),
                "url": url,
                "content": snippet,
                "domain": _extract_domain(url),
                "source_type": _classify_source(url),
                "engines": item.get("engines", []),
                "published_date": item.get("publishedDate", ""),
            })
            if len(results) >= limit:
                break

        print(f"[web_search] Found {len(results)} results for: {query[:80]}")
        return results

    async def _fetch_page_content(self, url: str) -> Optional[str]:
        """Fetch full-page content from *url* and extract clean text."""
        if trafilatura is None:
            return None
        try:
            async with httpx.AsyncClient(timeout=self.full_content_timeout) as client:
                resp = await client.get(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (compatible; AlfredBot/1.0)"},
                    follow_redirects=True,
                )
                resp.raise_for_status()
                html = resp.text
        except Exception as exc:
            print(f"[web_search] Full-page fetch failed for {url}: {exc}")
            return None

        text = trafilatura.extract(
            html,
            include_links=False,
            include_tables=True,
            include_comments=False,
        )
        if not text:
            return None
        if len(text) > self.full_content_max_chars:
            text = text[: self.full_content_max_chars].rsplit(" ", 1)[0]
        return text

    async def enrich_with_full_content(
        self, results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Fetch full-page text for the top N results (concurrent)."""
        if not self.fetch_full_content or not results:
            return results

        count = min(self.full_content_count, len(results))
        tasks = [self._fetch_page_content(results[i]["url"]) for i in range(count)]
        fetched = await asyncio.gather(*tasks, return_exceptions=True)

        for i, content in enumerate(fetched):
            if isinstance(content, BaseException) or content is None:
                results[i]["full_content"] = None
                results[i]["content_source"] = "snippet"
            else:
                results[i]["full_content"] = content
                results[i]["content_source"] = "full_page"

        for i in range(count, len(results)):
            results[i]["full_content"] = None
            results[i]["content_source"] = "snippet"

        full_ok = sum(1 for r in results if r.get("content_source") == "full_page")
        print(f"[web_search] Full-page enrichment: {full_ok}/{count} succeeded")
        return results

    def format_results_for_context(self, results: List[Dict[str, Any]]) -> str:
        """Format search results into a text block for the system message."""
        if not results:
            return ""
        lines = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "Untitled")
            url = r.get("url", "")
            domain = r.get("domain", "")
            source_type = r.get("source_type", "web")
            trust = _TRUST_LABELS.get(source_type, "unknown")

            # Prefer full-page content when available
            body = r.get("full_content") or r.get("content", "")
            content_tag = "[Full page content]" if r.get("content_source") == "full_page" else "[Snippet only]"

            header = (
                f"[{i}] {title}\n"
                f"    URL: {url} | Type: {source_type} ({trust}) | Domain: {domain}\n"
                f"    {content_tag}"
            )
            lines.append(f"{header}\n    {body}")
        return "\n\n".join(lines)


# ── Singleton ────────────────────────────────────────────────────

_web_search_service: Optional[WebSearchService] = None


def get_web_search_service() -> WebSearchService:
    """Get cached WebSearchService instance."""
    global _web_search_service
    if _web_search_service is None:
        _web_search_service = WebSearchService(get_settings())
    return _web_search_service
