"""
Chat History Storage in Supabase
Manages conversation history for RAG chatbot
"""

from supabase import create_client, Client
from app.core.config import settings
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ChatStorage:
    """
    Store and retrieve chat history from Supabase
    """
    
    def __init__(self):
        """Initialize Supabase client"""
        self.client: Client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_KEY
        )
        self.table_name = "chat_history"
        self._ensure_table_exists()
    
    def _ensure_table_exists(self):
        """
        Ensure chat history table exists
        Note: You should create this table in Supabase dashboard with:
        
        CREATE TABLE chat_history (
            id BIGSERIAL PRIMARY KEY,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
            message TEXT NOT NULL,
            metadata JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        
        CREATE INDEX idx_chat_history_session ON chat_history(session_id, created_at);
        """
        logger.info(f"Using chat history table: {self.table_name}")
    
    def save_message(
        self,
        session_id: str,
        role: str,
        message: str,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Save a chat message to Supabase
        
        Args:
            session_id: Session identifier
            role: 'user' or 'assistant'
            message: Message content
            metadata: Optional metadata (sources, chunks, etc.)
        
        Returns:
            Saved message record
        """
        try:
            data = {
                "session_id": session_id,
                "role": role,
                "message": message,
                "metadata": metadata or {}
            }
            
            result = self.client.table(self.table_name).insert(data).execute()
            
            logger.info(f"✓ Saved {role} message for session {session_id}")
            return result.data[0] if result.data else {}
            
        except Exception as e:
            logger.error(f"Error saving message: {e}")
            raise
    
    def get_chat_history(
        self,
        session_id: str,
        limit: int = 10
    ) -> List[Dict]:
        """
        Get chat history for a session
        
        Args:
            session_id: Session identifier
            limit: Maximum number of messages to retrieve (default: 10 most recent)
        
        Returns:
            List of messages ordered by timestamp (oldest first)
        """
        try:
            result = self.client.table(self.table_name).select("*").eq(
                "session_id", session_id
            ).order(
                "created_at", desc=False
            ).limit(limit).execute()
            
            messages = result.data if result.data else []
            logger.info(f"Retrieved {len(messages)} messages for session {session_id}")
            
            return messages
            
        except Exception as e:
            logger.error(f"Error getting chat history: {e}")
            return []
    
    def get_recent_context(
        self,
        session_id: str,
        num_turns: int = 5
    ) -> List[Dict]:
        """
        Get recent conversation turns for context
        
        Args:
            session_id: Session identifier
            num_turns: Number of conversation turns (each turn = 1 user + 1 assistant message)
        
        Returns:
            List of recent messages formatted for Gemini context
        """
        try:
            # Get last N*2 messages (N turns = N user + N assistant)
            limit = num_turns * 2
            
            result = self.client.table(self.table_name).select(
                "role, message, created_at"
            ).eq(
                "session_id", session_id
            ).order(
                "created_at", desc=True
            ).limit(limit).execute()
            
            messages = result.data if result.data else []
            
            # Reverse to get chronological order
            messages.reverse()
            
            logger.info(f"Retrieved {len(messages)} messages for context (session {session_id})")
            
            return messages
            
        except Exception as e:
            logger.error(f"Error getting recent context: {e}")
            return []
    
    def clear_session(self, session_id: str) -> int:
        """
        Clear all messages for a session
        
        Args:
            session_id: Session identifier
        
        Returns:
            Number of messages deleted
        """
        try:
            result = self.client.table(self.table_name).delete().eq(
                "session_id", session_id
            ).execute()
            
            count = len(result.data) if result.data else 0
            logger.info(f"Deleted {count} messages for session {session_id}")
            
            return count
            
        except Exception as e:
            logger.error(f"Error clearing session: {e}")
            return 0


# Singleton instance
chat_storage = ChatStorage()
