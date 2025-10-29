"""
BM25 Index for Keyword-Based Search (In-Memory)
Free alternative to vector search - great for exact matches
"""

from typing import List, Dict, Optional
import logging
from rank_bm25 import BM25Okapi
import re
from datetime import datetime

logger = logging.getLogger(__name__)


class BM25Index:
    """
    In-memory BM25 index for fast keyword search
    Stored per session in RAM - no external services needed
    """
    
    # Global storage: {session_id: {index, chunks, timestamp}}
    _indexes = {}
    
    @classmethod
    def build_index(
        cls,
        session_id: str,
        chunks: List[Dict]
    ) -> bool:
        """
        Build BM25 index for a session
        
        Args:
            session_id: Unique session/document ID
            chunks: List of text chunks with metadata
            
        Returns:
            Success boolean
        """
        try:
            if not chunks:
                logger.warning(f"No chunks to index for session {session_id}")
                return False
            
            # Tokenize all chunk texts
            tokenized_corpus = [
                cls._tokenize(chunk.get('text', ''))
                for chunk in chunks
            ]
            
            # Log sample tokens for debugging
            if tokenized_corpus:
                logger.info(f"📚 Sample tokens from first chunk: {tokenized_corpus[0][:30]}...")
                logger.info(f"📊 Token count per chunk: {[len(tokens) for tokens in tokenized_corpus]}")
            
            # Build BM25 index
            bm25 = BM25Okapi(tokenized_corpus)
            
            # Store in memory
            cls._indexes[session_id] = {
                'index': bm25,
                'chunks': chunks,  # Keep reference to original chunks
                'tokenized_corpus': tokenized_corpus,
                'created_at': datetime.now(),
                'num_chunks': len(chunks)
            }
            
            logger.info(f"✓ Built BM25 index for session {session_id}: {len(chunks)} chunks")
            return True
            
        except Exception as e:
            logger.error(f"Error building BM25 index: {e}")
            return False
    
    @classmethod
    def search(
        cls,
        session_id: str,
        query: str,
        top_k: int = 10
    ) -> List[Dict]:
        """
        Search BM25 index with query
        
        Args:
            session_id: Session to search in
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of chunks with BM25 scores
        """
        try:
            # Check if index exists
            if session_id not in cls._indexes:
                logger.warning(f"No BM25 index found for session '{session_id}'")
                logger.info(f"Available sessions: {list(cls._indexes.keys())}")
                return []
            
            index_data = cls._indexes[session_id]
            bm25 = index_data['index']
            chunks = index_data['chunks']
            
            logger.debug(f"Searching BM25 index with {len(chunks)} chunks")
            
            # Tokenize query
            tokenized_query = cls._tokenize(query)
            
            if not tokenized_query:
                logger.warning(f"Query tokenized to empty: '{query}'")
                return []
            
            logger.info(f"🔍 Tokenized query: {tokenized_query}")
            
            # Get BM25 scores
            scores = bm25.get_scores(tokenized_query)
            
            # Log all scores for debugging
            logger.info(f"📊 BM25 scores for {len(chunks)} chunks: {[round(s, 3) for s in scores]}")
            
            # Get top K indices
            top_indices = sorted(
                range(len(scores)),
                key=lambda i: scores[i],
                reverse=True
            )[:top_k]
            
            # Build results with scores
            results = []
            for idx in top_indices:
                # Include ALL results - BM25 can have negative scores for rare terms
                # The ranking is still valid, just lower confidence
                chunk = chunks[idx].copy()
                chunk['bm25_score'] = float(scores[idx])
                chunk['search_method'] = 'bm25'
                results.append(chunk)
                logger.info(f"  ✓ Chunk {idx}: score={scores[idx]:.3f}, preview={chunk.get('text', '')[:100]}...")
            
            if not results:
                logger.warning(f"⚠️  No BM25 results found. Query tokens: {tokenized_query}")
                # Show sample of corpus tokens for debugging
                if chunks:
                    sample_text = chunks[0].get('text', '')[:200]
                    sample_tokens = cls._tokenize(sample_text)[:20]
                    logger.info(f"📝 Sample corpus tokens: {sample_tokens}")
            
            logger.info(f"BM25 search for '{query}': {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Error searching BM25 index: {e}")
            return []
    
    @classmethod
    def get_index_stats(cls, session_id: str) -> Optional[Dict]:
        """Get statistics about an index"""
        if session_id not in cls._indexes:
            return None
        
        index_data = cls._indexes[session_id]
        return {
            'session_id': session_id,
            'num_chunks': index_data['num_chunks'],
            'created_at': index_data['created_at'].isoformat(),
            'age_seconds': (datetime.now() - index_data['created_at']).total_seconds()
        }
    
    @classmethod
    def delete_index(cls, session_id: str) -> bool:
        """Delete index from memory"""
        if session_id in cls._indexes:
            del cls._indexes[session_id]
            logger.info(f"Deleted BM25 index for session {session_id}")
            return True
        return False
    
    @classmethod
    def get_all_sessions(cls) -> List[str]:
        """Get all active session IDs"""
        return list(cls._indexes.keys())
    
    @classmethod
    def cleanup_old_indexes(cls, max_age_hours: int = 24):
        """Remove indexes older than specified hours"""
        now = datetime.now()
        to_delete = []
        
        for session_id, data in cls._indexes.items():
            age_hours = (now - data['created_at']).total_seconds() / 3600
            if age_hours > max_age_hours:
                to_delete.append(session_id)
        
        for session_id in to_delete:
            cls.delete_index(session_id)
        
        if to_delete:
            logger.info(f"Cleaned up {len(to_delete)} old BM25 indexes")
    
    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """
        Simple tokenization for BM25
        Lowercases, removes punctuation, splits on whitespace
        """
        # Lowercase
        text = text.lower()
        
        # Remove punctuation but keep alphanumeric
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # Split and filter empty
        tokens = [token for token in text.split() if token]
        
        return tokens


def build_bm25_index(session_id: str, chunks: List[Dict]) -> bool:
    """
    Convenience function to build BM25 index
    
    Args:
        session_id: Unique session identifier
        chunks: List of text chunks
        
    Returns:
        Success boolean
    """
    return BM25Index.build_index(session_id, chunks)


def search_bm25(session_id: str, query: str, top_k: int = 10) -> List[Dict]:
    """
    Convenience function to search BM25 index
    
    Args:
        session_id: Session identifier
        query: Search query
        top_k: Number of results
        
    Returns:
        List of matching chunks with scores
    """
    return BM25Index.search(session_id, query, top_k)


def get_bm25_stats(session_id: str) -> Optional[Dict]:
    """Get BM25 index statistics"""
    return BM25Index.get_index_stats(session_id)
