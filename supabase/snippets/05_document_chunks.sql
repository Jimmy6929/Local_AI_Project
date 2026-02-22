-- ============================================
-- 05_document_chunks.sql
-- Create document_chunks table with embeddings
-- Run this SIXTH
-- ============================================

-- Create document_chunks table with vector embeddings
CREATE TABLE IF NOT EXISTS public.document_chunks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id UUID NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  content TEXT NOT NULL,
  embedding vector(1536),  -- OpenAI text-embedding-3-small dimensions
  chunk_index INTEGER NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Add comments
COMMENT ON TABLE public.document_chunks IS 'Text chunks with embeddings for RAG vector search';
COMMENT ON COLUMN public.document_chunks.embedding IS 'Vector embedding (1536 dimensions for OpenAI text-embedding-3-small)';

-- Enable Row Level Security
ALTER TABLE public.document_chunks ENABLE ROW LEVEL SECURITY;

-- RLS Policies for document_chunks
CREATE POLICY "Users can view their own chunks"
  ON public.document_chunks
  FOR SELECT
  USING (user_id = auth.uid());

CREATE POLICY "Users can create their own chunks"
  ON public.document_chunks
  FOR INSERT
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users can delete their own chunks"
  ON public.document_chunks
  FOR DELETE
  USING (user_id = auth.uid());

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id ON public.document_chunks(document_id, chunk_index);
CREATE INDEX IF NOT EXISTS idx_document_chunks_user_id ON public.document_chunks(user_id);

-- IVFFlat index for vector similarity search
-- Note: This index works best with existing data. Re-run after loading data.
-- Lists parameter should be ~sqrt(row_count), start with 100
CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding 
  ON public.document_chunks 
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);