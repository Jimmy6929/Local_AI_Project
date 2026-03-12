"""
Embedding service for RAG vector search.

Uses sentence-transformers (all-MiniLM-L6-v2 by default) to generate 384-dimensional
embeddings locally on CPU/Apple Silicon. Lighter model (~80MB) for fast load.
"""

from typing import List, Optional

from app.config import Settings, get_settings


class EmbeddingService:
    """Generate text embeddings using a local sentence-transformers model."""

    def __init__(self, settings: Settings):
        self.model_name = settings.embedding_model
        self.local_files_only = settings.embedding_local_only
        self._model = None

    def _load_model(self):
        if self._model is not None:
            return
        from sentence_transformers import SentenceTransformer

        print(f"[embedding] Loading model: {self.model_name} (local_files_only={self.local_files_only})")
        self._model = SentenceTransformer(
            self.model_name,
            trust_remote_code=True,
            local_files_only=self.local_files_only,
        )
        print(f"[embedding] Model loaded — dim={self._model.get_sentence_embedding_dimension()}")

    def embed(self, text: str, prefix: str = "search_query") -> List[float]:
        """Embed a single text string. Returns 384-dim float list (all-MiniLM-L6-v2)."""
        self._load_model()
        vector = self._model.encode(text, normalize_embeddings=True)
        return vector.tolist()

    def embed_batch(self, texts: List[str], batch_size: int = 32, prefix: str = "search_document") -> List[List[float]]:
        """Embed multiple texts. Returns list of 384-dim float lists."""
        if not texts:
            return []
        self._load_model()
        vectors = self._model.encode(texts, batch_size=batch_size, normalize_embeddings=True)
        return [v.tolist() for v in vectors]


_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get cached EmbeddingService instance."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService(get_settings())
    return _embedding_service
