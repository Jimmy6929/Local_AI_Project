"""
Embedding service for RAG vector search.

Uses sentence-transformers to generate 1536-dimensional embeddings
locally on CPU/Apple Silicon. The model is lazy-loaded on first use
to avoid slowing down gateway startup.
"""

from typing import List, Optional

from app.config import Settings, get_settings


class EmbeddingService:
    """Generate text embeddings using a local sentence-transformers model."""

    def __init__(self, settings: Settings):
        self.model_name = settings.embedding_model
        self._model = None

    def _load_model(self):
        if self._model is not None:
            return
        from sentence_transformers import SentenceTransformer

        print(f"[embedding] Loading model: {self.model_name}")
        self._model = SentenceTransformer(self.model_name, trust_remote_code=True)
        print(f"[embedding] Model loaded — dim={self._model.get_sentence_embedding_dimension()}")

    # Orange/orange-nomic-v1.5-1536 requires task prefixes for correct RAG similarity
    _QUERY_PREFIX = "search_query: "
    _DOC_PREFIX = "search_document: "

    def embed(self, text: str, prefix: str = "search_query") -> List[float]:
        """Embed a single text string. Returns a 1536-dim float list."""
        self._load_model()
        p = self._QUERY_PREFIX if prefix == "search_query" else self._DOC_PREFIX
        vector = self._model.encode(p + text, normalize_embeddings=True)
        return vector.tolist()

    def embed_batch(self, texts: List[str], batch_size: int = 32, prefix: str = "search_document") -> List[List[float]]:
        """Embed multiple texts. Returns list of 1536-dim float lists."""
        if not texts:
            return []
        self._load_model()
        p = self._QUERY_PREFIX if prefix == "search_query" else self._DOC_PREFIX
        prefixed = [p + t for t in texts]
        vectors = self._model.encode(prefixed, batch_size=batch_size, normalize_embeddings=True)
        return [v.tolist() for v in vectors]


_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get cached EmbeddingService instance."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService(get_settings())
    return _embedding_service
