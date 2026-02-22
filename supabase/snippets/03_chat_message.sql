-- ============================================
-- 03_chat_messages.sql
-- Create chat_messages table
-- Run this FOURTH
-- ============================================

-- Create chat_messages table
CREATE TABLE IF NOT EXISTS public.chat_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID NOT NULL REFERENCES public.chat_sessions(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
  content TEXT NOT NULL,
  mode_used TEXT CHECK (mode_used IN ('instant', 'thinking')),
  tokens_used INTEGER,
  created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Add comment
COMMENT ON TABLE public.chat_messages IS 'Individual messages within chat sessions';

-- Enable Row Level Security
ALTER TABLE public.chat_messages ENABLE ROW LEVEL SECURITY;

-- RLS Policies for chat_messages
CREATE POLICY "Users can view their own messages"
  ON public.chat_messages
  FOR SELECT
  USING (user_id = auth.uid());

CREATE POLICY "Users can create their own messages"
  ON public.chat_messages
  FOR INSERT
  WITH CHECK (user_id = auth.uid());

-- Note: No UPDATE/DELETE policies - messages are immutable history
-- Add these if you need message editing:
-- CREATE POLICY "Users can update their own messages"
--   ON public.chat_messages
--   FOR UPDATE
--   USING (user_id = auth.uid())
--   WITH CHECK (user_id = auth.uid());

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_created ON public.chat_messages(session_id, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_chat_messages_user_id ON public.chat_messages(user_id);

-- Function to update session updated_at when new message is added
CREATE OR REPLACE FUNCTION public.update_session_on_new_message()
RETURNS TRIGGER AS $$
BEGIN
  UPDATE public.chat_sessions
  SET updated_at = NOW()
  WHERE id = NEW.session_id;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger to update session when message is added
DROP TRIGGER IF EXISTS on_new_chat_message ON public.chat_messages;
CREATE TRIGGER on_new_chat_message
  AFTER INSERT ON public.chat_messages
  FOR EACH ROW
  EXECUTE FUNCTION public.update_session_on_new_message();