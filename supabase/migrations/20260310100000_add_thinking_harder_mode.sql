-- Allow a third inference mode for deeper reasoning sessions
ALTER TABLE public.chat_messages
  DROP CONSTRAINT IF EXISTS chat_messages_mode_used_check;

ALTER TABLE public.chat_messages
  ADD CONSTRAINT chat_messages_mode_used_check
  CHECK (mode_used IN ('instant', 'thinking', 'thinking_harder'));

-- Force PostgREST to reload schema cache
NOTIFY pgrst, 'reload schema';
