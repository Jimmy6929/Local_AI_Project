"""
Document processing pipeline for RAG.

Handles text extraction (PDF, DOCX, TXT, MD), chunking with overlap,
embedding generation, and storage in Supabase (document_chunks table).
"""

import io
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from app.config import Settings, get_settings
from app.services.embedding import EmbeddingService, get_embedding_service


# ── Text Extraction ──────────────────────────────────────────────────────

def extract_text_from_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages)


def extract_text_from_docx(data: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(data))
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())


def extract_text(data: bytes, file_type: str) -> str:
    """Extract plain text from supported file types."""
    ft = file_type.lower()
    if ft in ("application/pdf", "pdf"):
        return extract_text_from_pdf(data)
    if ft in ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"):
        return extract_text_from_docx(data)
    # TXT / MD — decode as UTF-8
    return data.decode("utf-8", errors="replace")


# ── Chunking ─────────────────────────────────────────────────────────────

_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


def chunk_text(text: str, chunk_size: int = 512, chunk_overlap: int = 50) -> List[str]:
    """
    Split text into overlapping chunks using a recursive character splitter.

    Tries to split on paragraph boundaries first, then sentences, then words.
    chunk_size and chunk_overlap are in *characters* (not tokens) for simplicity.
    """
    if not text.strip():
        return []

    chunks: List[str] = []
    _recursive_split(text, _SEPARATORS, chunk_size, chunk_overlap, chunks)
    return [c for c in chunks if c.strip()]


def _recursive_split(
    text: str,
    separators: List[str],
    chunk_size: int,
    chunk_overlap: int,
    result: List[str],
):
    if len(text) <= chunk_size:
        result.append(text.strip())
        return

    sep = separators[0] if separators else ""
    next_seps = separators[1:] if len(separators) > 1 else [""]

    if sep == "":
        # Hard character split as last resort
        for i in range(0, len(text), chunk_size - chunk_overlap):
            piece = text[i : i + chunk_size]
            if piece.strip():
                result.append(piece.strip())
        return

    parts = text.split(sep)
    current: List[str] = []
    current_len = 0

    for part in parts:
        part_len = len(part) + len(sep)
        if current_len + part_len > chunk_size and current:
            merged = sep.join(current).strip()
            if len(merged) > chunk_size and next_seps:
                _recursive_split(merged, next_seps, chunk_size, chunk_overlap, result)
            elif merged:
                result.append(merged)

            # Keep overlap
            overlap_parts: List[str] = []
            overlap_len = 0
            for p in reversed(current):
                if overlap_len + len(p) + len(sep) > chunk_overlap:
                    break
                overlap_parts.insert(0, p)
                overlap_len += len(p) + len(sep)
            current = overlap_parts
            current_len = overlap_len

        current.append(part)
        current_len += part_len

    if current:
        merged = sep.join(current).strip()
        if len(merged) > chunk_size and next_seps:
            _recursive_split(merged, next_seps, chunk_size, chunk_overlap, result)
        elif merged:
            result.append(merged)


# ── Processing Pipeline ──────────────────────────────────────────────────

class DocumentProcessor:
    """Orchestrates the full document processing pipeline."""

    def __init__(self, settings: Settings, embedding_service: EmbeddingService):
        self.settings = settings
        self.embedding = embedding_service
        self.chunk_size = settings.rag_chunk_size
        self.chunk_overlap = settings.rag_chunk_overlap

    def process(self, file_data: bytes, file_type: str) -> List[Tuple[str, List[float]]]:
        """
        Extract text, chunk, and embed.

        Returns list of (chunk_text, embedding_vector) tuples.
        """
        text = extract_text(file_data, file_type)
        if not text.strip():
            raise ValueError("No text could be extracted from the document")

        chunks = chunk_text(text, self.chunk_size, self.chunk_overlap)
        if not chunks:
            raise ValueError("Document produced no text chunks")

        print(f"[doc_processor] Extracted {len(text)} chars → {len(chunks)} chunks")

        embeddings = self.embedding.embed_batch(chunks)
        return list(zip(chunks, embeddings))


_processor: Optional[DocumentProcessor] = None


def get_document_processor() -> DocumentProcessor:
    """Get cached DocumentProcessor instance."""
    global _processor
    if _processor is None:
        _processor = DocumentProcessor(get_settings(), get_embedding_service())
    return _processor
