-- ============================================
-- 08_fix_embedding_index.sql
-- Migration: Replace IVFFlat with HNSW index
-- Run this on existing databases to fix RAG
-- ============================================
--
-- IVFFlat with lists=100 on an empty table produces degenerate centroids,
-- so similarity search misses everything.  HNSW works correctly regardless
-- of table size at creation time and needs no re-training.

DROP INDEX IF EXISTS idx_document_chunks_embedding;

CREATE INDEX idx_document_chunks_embedding
  ON public.document_chunks
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);
