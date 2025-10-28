"""
SerpAPI Web Search Integration
Performs web searches for queries that need external information
"""

import logging
from typing import Dict, List, Optional
import os
from serpapi import GoogleSearch

logger = logging.getLogger(__name__)


class WebSearcher:
    """
    Perform web searches using SerpAPI
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize web searcher
        
        Args:
            api_key: SerpAPI API key (optional, will use env var if not provided)
        """
        self.api_key = api_key or os.getenv('SERPAPI_KEY')
        if not self.api_key:
            logger.warning("SERPAPI_KEY not configured - web search disabled")
        else:
            logger.info("Web searcher initialized with SerpAPI")
    
    def search(self, query: str, num_results: int = 5) -> Dict[str, any]:
        """
        Perform web search
        
        Args:
            query: Search query
            num_results: Number of results to return
            
        Returns:
            Dictionary with search results
        """
        if not self.api_key:
            return {
                'success': False,
                'error': 'SerpAPI not configured',
                'results': []
            }
        
        try:
            logger.info(f"Performing web search for: {query}")
            
            # Perform search
            params = {
                "q": query,
                "api_key": self.api_key,
                "num": num_results,
                "engine": "google"
            }
            
            search = GoogleSearch(params)
            results = search.get_dict()
            
            # Extract organic results
            organic_results = results.get("organic_results", [])
            
            # Format results
            formatted_results = []
            for result in organic_results[:num_results]:
                formatted_results.append({
                    'title': result.get('title', ''),
                    'link': result.get('link', ''),
                    'snippet': result.get('snippet', ''),
                    'source': result.get('source', '')
                })
            
            logger.info(f"✓ Found {len(formatted_results)} web search results")
            
            return {
                'success': True,
                'results': formatted_results,
                'query': query
            }
            
        except Exception as e:
            logger.error(f"Web search error: {e}")
            return {
                'success': False,
                'error': str(e),
                'results': []
            }
    
    def format_results_for_context(self, search_results: List[Dict]) -> str:
        """
        Format search results as context for LLM
        
        Args:
            search_results: List of search results
            
        Returns:
            Formatted context string
        """
        if not search_results:
            return "No web search results found."
        
        context_parts = ["Web Search Results:\n"]
        
        for i, result in enumerate(search_results, 1):
            context_parts.append(f"\n[Result {i}]")
            context_parts.append(f"Title: {result['title']}")
            context_parts.append(f"Source: {result['source']}")
            context_parts.append(f"Link: {result['link']}")
            context_parts.append(f"Snippet: {result['snippet']}")
        
        return "\n".join(context_parts)


# Singleton instance
_searcher = None

def get_web_searcher() -> WebSearcher:
    """Get or create web searcher singleton"""
    global _searcher
    if _searcher is None:
        _searcher = WebSearcher()
    return _searcher


# Simple function wrapper for convenience
def web_search(query: str, num_results: int = 5) -> Dict[str, any]:
    """
    Perform web search (convenience function)
    
    Args:
        query: Search query
        num_results: Number of results to return
        
    Returns:
        Search results dictionary
    """
    searcher = get_web_searcher()
    return searcher.search(query, num_results)
