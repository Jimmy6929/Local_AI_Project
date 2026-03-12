"""
RAG (Retrieval-Augmented Generation) service.

Embeds the user query, searches document_chunks via pgvector similarity,
and formats matching chunks as context for injection into the LLM prompt.
"""

from typing import Any, Dict, List, Optional

import httpx

from app.config import Settings, get_settings
from app.services.embedding import EmbeddingService, get_embedding_service


class RAGService:
    """Retrieve relevant document context for a user query."""

    def __init__(self, settings: Settings, embedding_service: EmbeddingService):
        self.settings = settings
        self.embedding = embedding_service
        self.enabled = settings.rag_enabled
        self.match_count = settings.rag_match_count
        self.match_threshold = settings.rag_match_threshold
        self.max_context_chars = settings.rag_max_context_chars

    async def user_has_documents(self, user_token: str) -> bool:
        """
        Check if the user has any document chunks (completed RAG documents).
        Skips embedding load when user has no documents.
        """
        if not self.enabled:
            return False
        url = f"{self.settings.supabase_url}/rest/v1/document_chunks?select=id&limit=1"
        headers = {
            "apikey": self.settings.supabase_anon_key,
            "Authorization": f"Bearer {user_token}",
            "Prefer": "count=none",
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                rows = resp.json()
                return len(rows) > 0
        except Exception as exc:
            print(f"[rag] user_has_documents check failed: {type(exc).__name__}: {exc}")
            return False

    async def retrieve_context(
        self,
        user_token: str,
        query: str,
        limit: Optional[int] = None,
        threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Embed the query and search for matching document chunks.

        Uses the Supabase RPC match_documents_with_metadata which
        enforces RLS via the user's JWT.

        Returns list of dicts with keys:
            chunk_id, document_id, filename, content, chunk_index, similarity
        """
        if not self.enabled:
            return []

        print(f"[rag] Embedding query ({len(query)} chars)...")
        query_embedding = self.embedding.embed(query)
        count = limit or self.match_count
        thresh = threshold or self.match_threshold

        rpc_url = f"{self.settings.supabase_url}/rest/v1/rpc/match_documents_with_metadata"
        headers = {
            "apikey": self.settings.supabase_anon_key,
            "Authorization": f"Bearer {user_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "query_embedding": query_embedding,
            "match_threshold": thresh,
            "match_count": count,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(rpc_url, json=payload, headers=headers)
                resp.raise_for_status()
                results = resp.json()
        except httpx.HTTPStatusError as exc:
            print(f"[rag] RPC HTTP error {exc.response.status_code}: {exc.response.text[:500]}")
            return []
        except Exception as exc:
            print(f"[rag] Similarity search failed: {type(exc).__name__}: {exc}")
            return []

        if not results:
            print(f"[rag] No matching chunks (threshold={thresh}). Try lowering RAG_MATCH_THRESHOLD.")
            return []

        print(f"[rag] Found {len(results)} matching chunks (top similarity: {results[0].get('similarity', 0):.3f})")
        return results

    def format_context(self, chunks: List[Dict[str, Any]]) -> str:
        """Format retrieved chunks into a text block for the system message."""
        if not chunks:
            return ""

        lines = []
        total_chars = 0
        for i, c in enumerate(chunks, 1):
            filename = c.get("filename", "unknown")
            content = c.get("content", "")
            similarity = c.get("similarity", 0)

            entry = f"[{i}] {filename} (relevance: {similarity:.2f})\n{content}"
            if total_chars + len(entry) > self.max_context_chars:
                break
            lines.append(entry)
            total_chars += len(entry)

        return "\n\n".join(lines)


_rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    """Get cached RAGService instance."""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService(get_settings(), get_embedding_service())
    return _rag_service
