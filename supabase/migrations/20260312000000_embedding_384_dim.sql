-- ============================================
-- Switch embedding dimension from 1536 to 384
-- (all-MiniLM-L6-v2 lighter model)
-- ============================================
-- Existing document_chunks are cleared; users must re-upload documents.

-- 1. Clear existing chunks (embeddings incompatible with new dimension)
TRUNCATE public.document_chunks;

-- 2. Drop IVFFlat index (required before column change)
DROP INDEX IF EXISTS idx_document_chunks_embedding;

-- 3. Change embedding column to 384 dimensions
ALTER TABLE public.document_chunks DROP COLUMN embedding;
ALTER TABLE public.document_chunks ADD COLUMN embedding vector(384);

-- 4. Recreate IVFFlat index for similarity search
CREATE INDEX idx_document_chunks_embedding
  ON public.document_chunks
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

-- 5. Update match_documents function
CREATE OR REPLACE FUNCTION public.match_documents(
  query_embedding vector(384),
  match_threshold FLOAT DEFAULT 0.7,
  match_count INT DEFAULT 5
)
RETURNS TABLE (
  id UUID,
  document_id UUID,
  content TEXT,
  chunk_index INTEGER,
  similarity FLOAT
)
LANGUAGE plpgsql
SECURITY INVOKER
AS $$
BEGIN
  RETURN QUERY
  SELECT
    dc.id,
    dc.document_id,
    dc.content,
    dc.chunk_index,
    1 - (dc.embedding <=> query_embedding) AS similarity
  FROM public.document_chunks dc
  WHERE dc.user_id = auth.uid()
    AND 1 - (dc.embedding <=> query_embedding) > match_threshold
  ORDER BY dc.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

-- 6. Update match_documents_with_metadata function
CREATE OR REPLACE FUNCTION public.match_documents_with_metadata(
  query_embedding vector(384),
  match_threshold FLOAT DEFAULT 0.7,
  match_count INT DEFAULT 5
)
RETURNS TABLE (
  chunk_id UUID,
  document_id UUID,
  filename TEXT,
  content TEXT,
  chunk_index INTEGER,
  similarity FLOAT
)
LANGUAGE plpgsql
SECURITY INVOKER
AS $$
BEGIN
  RETURN QUERY
  SELECT
    dc.id AS chunk_id,
    dc.document_id,
    d.filename,
    dc.content,
    dc.chunk_index,
    1 - (dc.embedding <=> query_embedding) AS similarity
  FROM public.document_chunks dc
  JOIN public.documents d ON d.id = dc.document_id
  WHERE dc.user_id = auth.uid()
    AND d.status = 'completed'
    AND 1 - (dc.embedding <=> query_embedding) > match_threshold
  ORDER BY dc.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

COMMENT ON COLUMN public.document_chunks.embedding IS 'Vector embedding (384 dimensions for all-MiniLM-L6-v2)';
