-- Create chat_history table in Supabase
-- Run this in Supabase SQL Editor

-- Create the table
CREATE TABLE IF NOT EXISTS chat_history (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    message TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index for efficient session queries
CREATE INDEX IF NOT EXISTS idx_chat_history_session 
ON chat_history(session_id, created_at DESC);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_chat_history_created 
ON chat_history(created_at DESC);

-- Enable Row Level Security (optional but recommended)
ALTER TABLE chat_history ENABLE ROW LEVEL SECURITY;

-- Create policy to allow all operations (modify as needed for your security requirements)
CREATE POLICY "Allow all operations on chat_history" 
ON chat_history 
FOR ALL 
USING (true) 
WITH CHECK (true);

-- Add comment
COMMENT ON TABLE chat_history IS 'Stores conversation history for RAG chatbot with session-based isolation';
COMMENT ON COLUMN chat_history.session_id IS 'Session identifier to group related conversations';
COMMENT ON COLUMN chat_history.role IS 'Message sender: user or assistant';
COMMENT ON COLUMN chat_history.message IS 'Message content';
COMMENT ON COLUMN chat_history.metadata IS 'Additional metadata (sources, chunks, model info, etc.)';
