"""
Serper API Web Search Integration
Performs web searches for queries that need external information
"""

import logging
from typing import Dict, List, Optional
import os
import requests

logger = logging.getLogger(__name__)


class WebSearcher:
    """
    Perform web searches using Serper API (serper.dev)
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize web searcher
        
        Args:
            api_key: Serper API key (optional, will use env var if not provided)
        """
        self.api_key = api_key or os.getenv('SERPER_API_KEY')
        self.base_url = "https://google.serper.dev/search"
        
        if not self.api_key:
            logger.warning("SERPER_API_KEY not configured - web search disabled")
        else:
            logger.info("Web searcher initialized with Serper API")
    
    def search(self, query: str, num_results: int = 5) -> Dict[str, any]:
        """
        Perform web search using Serper API
        
        Args:
            query: Search query
            num_results: Number of results to return
            
        Returns:
            Dictionary with search results
        """
        if not self.api_key:
            return {
                'success': False,
                'error': 'Serper API not configured',
                'results': []
            }
        
        try:
            logger.info(f"Performing web search for: {query}")
            
            # Prepare request
            headers = {
                'X-API-KEY': self.api_key,
                'Content-Type': 'application/json'
            }
            
            payload = {
                'q': query,
                'num': num_results
            }
            
            # Make request
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=10
            )
            
            response.raise_for_status()
            results = response.json()
            
            # Extract organic results
            organic_results = results.get("organic", [])
            
            # Format results
            formatted_results = []
            for result in organic_results[:num_results]:
                formatted_results.append({
                    'title': result.get('title', ''),
                    'link': result.get('link', ''),
                    'snippet': result.get('snippet', ''),
                    'source': result.get('link', '').split('/')[2] if result.get('link') else ''
                })
            
            logger.info(f"✓ Found {len(formatted_results)} web search results")
            
            return {
                'success': True,
                'results': formatted_results,
                'query': query
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Web search error: {e}")
            return {
                'success': False,
                'error': str(e),
                'results': []
            }
        except Exception as e:
            logger.error(f"Unexpected web search error: {e}")
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
