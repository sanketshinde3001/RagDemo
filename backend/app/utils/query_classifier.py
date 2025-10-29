"""
Query Classifier and Router
Determines query type and routes to appropriate handler:
- Simple greetings -> Direct response
- Document questions -> RAG retrieval
- Web search queries -> SerpAPI
"""

import logging
from typing import Dict, Literal
import re

logger = logging.getLogger(__name__)

QueryType = Literal["greeting", "document", "web_search"]


class QueryClassifier:
    """
    Classify user queries to determine appropriate handling
    """
    
    def __init__(self):
        # Simple greeting patterns
        self.greeting_patterns = [
            r'^hi+$',
            r'^hello+$',
            r'^hey+$',
            r'^good (morning|afternoon|evening|day)$',
            r'^how are you$',
            r'^how\'s it going$',
            r'^what\'s up$',
            r'^greetings$',
            r'^sup$',
        ]
        
        # Web search indicators
        self.web_search_keywords = [
            'current', 'today', 'latest', 'recent', 'news',
            'weather', 'stock price', 'who is', 'what is happening',
            'current events', 'right now', 'this week', 'this month',
            'trending', 'breaking', 'update on'
        ]
        
        # Document-specific keywords
        self.document_keywords = [
            'document', 'page', 'pdf', 'file', 'essay', 'paper',
            'section', 'chapter', 'paragraph', 'text', 'content',
            'according to', 'in the document', 'what does it say',
            'summarize', 'explain this', 'tell me about this'
        ]
    
    def classify(self, query: str, has_documents: bool = False) -> Dict[str, any]:
        """
        Classify a query
        
        Args:
            query: User's query text
            has_documents: Whether user has uploaded documents in this session
            
        Returns:
            Dictionary with:
            - type: 'greeting', 'document', or 'web_search'
            - confidence: 0.0 to 1.0
            - reason: Explanation of classification
        """
        query_lower = query.lower().strip()
        
        # 1. Check for simple greetings
        for pattern in self.greeting_patterns:
            if re.match(pattern, query_lower):
                return {
                    'type': 'greeting',
                    'confidence': 1.0,
                    'reason': 'Matched greeting pattern'
                }
        
        # 2. Check for web search indicators
        web_score = sum(1 for keyword in self.web_search_keywords if keyword in query_lower)
        
        # 3. Check for document-specific keywords
        doc_score = sum(1 for keyword in self.document_keywords if keyword in query_lower)
        
        # Decision logic
        if not has_documents:
            # No documents uploaded - either greeting or web search
            if web_score > 0:
                return {
                    'type': 'web_search',
                    'confidence': 0.8,
                    'reason': f'No documents available, query contains web search keywords'
                }
            else:
                return {
                    'type': 'greeting',
                    'confidence': 0.6,
                    'reason': 'No documents available, treating as general query'
                }
        
        # Has documents - choose between document and web search
        if doc_score > 0:
            return {
                'type': 'document',
                'confidence': 0.9,
                'reason': f'Contains document-specific keywords (score: {doc_score})'
            }
        
        if web_score > 2:
            # Strong web search signal
            return {
                'type': 'web_search',
                'confidence': 0.85,
                'reason': f'Strong web search indicators (score: {web_score})'
            }
        
        # Default to document search if documents available
        if has_documents:
            return {
                'type': 'document',
                'confidence': 0.7,
                'reason': 'Documents available, defaulting to document search'
            }
        
        # Fallback
        return {
            'type': 'web_search',
            'confidence': 0.5,
            'reason': 'Uncertain, defaulting to web search'
        }
    
    def get_greeting_response(self, query: str) -> str:
        """
        Generate a friendly greeting response with markdown formatting
        """
        query_lower = query.lower().strip()
        
        if 'how are you' in query_lower or 'how\'s it going' in query_lower:
            return """I'm doing **great**, thank you for asking! 😊

I'm your AI document assistant, ready to help you with:
- 📄 **Document Q&A** - Ask questions about your uploaded PDFs
- 🔍 **Web Search** - Toggle web search for real-time information
- 🎤 **Voice Input** - Speak your questions naturally

How can I assist you today?"""
        
        if 'morning' in query_lower:
            return """**Good morning!** 🌅

I'm ready to help you explore your documents. Here's what I can do:
- Answer questions from your PDF documents
- Search the web for additional information
- Understand voice commands

Upload a PDF or ask me anything!"""
        
        if 'afternoon' in query_lower:
            return """**Good afternoon!** ☀️

Ready to assist with your document questions. I can help with:
- **Document analysis** - Deep insights from your PDFs
- **Web research** - Real-time information when needed
- **Smart search** - Find exactly what you need

What would you like to know?"""
        
        if 'evening' in query_lower:
            return """**Good evening!** 🌙

I'm here to help with your documents. My capabilities include:
- Answering questions based on your uploaded PDFs
- Web search integration for current information
- Multi-modal understanding (text + images)

How can I help you tonight?"""
        
        # Default friendly greeting
        return """**Hello!** 👋

I'm your **AI Document Assistant** powered by Gemini 2.0. Here's how I can help:

**My Capabilities:**
- 📄 Answer questions from your PDF documents
- 🔍 Search the web when needed (toggle the switch)
- 🎤 Understand voice commands
- 🖼️ Analyze text and images

**To get started:**
1. Upload a PDF document
2. Ask questions about it
3. Enable web search for real-time info

What can I help you with?"""


# Singleton instance
_classifier = None

def get_query_classifier() -> QueryClassifier:
    """Get or create query classifier singleton"""
    global _classifier
    if _classifier is None:
        _classifier = QueryClassifier()
    return _classifier
