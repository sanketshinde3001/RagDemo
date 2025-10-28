"""
Script to create chat_history table in Supabase
"""

from supabase import create_client
from dotenv import load_dotenv
import os

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

print("Creating chat_history table in Supabase...")

# SQL to create the table
sql = """
-- Create chat_history table
CREATE TABLE IF NOT EXISTS chat_history (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    message TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_chat_history_session 
ON chat_history(session_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_chat_history_created 
ON chat_history(created_at DESC);

-- Enable Row Level Security
ALTER TABLE chat_history ENABLE ROW LEVEL SECURITY;

-- Allow all operations
CREATE POLICY IF NOT EXISTS "Allow all operations on chat_history" 
ON chat_history FOR ALL USING (true) WITH CHECK (true);
"""

try:
    # Execute the SQL
    result = client.rpc('exec_sql', {'sql': sql}).execute()
    print("✓ Table created successfully!")
    
    # Verify table exists
    result = client.table('chat_history').select('*').limit(1).execute()
    print("✓ Table verified - ready to use!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    print("\nPlease create the table manually in Supabase SQL Editor:")
    print("1. Go to your Supabase Dashboard")
    print("2. Click 'SQL Editor' in the left sidebar")
    print("3. Click 'New Query'")
    print("4. Copy and paste the SQL from: migrations/001_create_chat_history.sql")
    print("5. Click 'Run'")
