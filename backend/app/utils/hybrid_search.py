"""
Hybrid Search: Combines BM25 (keyword) + Vector (semantic) Search
Uses Reciprocal Rank Fusion (RRF) for score combination - FREE algorithm
"""

from typing import List, Dict, Optional
import logging
from app.utils.bm25_index import search_bm25
from app.utils.pinecone_storage import get_pinecone_storage

logger = logging.getLogger(__name__)


class HybridSearch:
    """
    Combines BM25 keyword search with vector semantic search
    Uses RRF (Reciprocal Rank Fusion) for ranking
    """
    
    def __init__(
        self,
        bm25_weight: float = 0.4,
        vector_weight: float = 0.6,
        rrf_k: int = 60
    ):
        """
        Initialize hybrid search
        
        Args:
            bm25_weight: Weight for BM25 scores (0-1)
            vector_weight: Weight for vector scores (0-1)
            rrf_k: RRF constant (default 60, standard value)
        """
        self.bm25_weight = bm25_weight
        self.vector_weight = vector_weight
        self.rrf_k = rrf_k
    
    def search(
        self,
        session_id: str,
        query: str,
        top_k: int = 5,
        namespace: Optional[str] = None
    ) -> List[Dict]:
        """
        Hybrid search combining BM25 and vector search
        
        Args:
            session_id: Session identifier
            query: Search query
            top_k: Number of results to return
            namespace: Pinecone namespace
            
        Returns:
            Combined and reranked results
        """
        try:
            # Get BM25 results
            bm25_results = search_bm25(session_id, query, top_k=10)
            logger.info(f"BM25 found {len(bm25_results)} results")
            
            # Get vector search results
            vector_results = self._vector_search(session_id, query, top_k=10, namespace=namespace)
            logger.info(f"Vector search found {len(vector_results)} results")
            
            # Combine using RRF
            combined_results = self._reciprocal_rank_fusion(
                bm25_results,
                vector_results,
                top_k=top_k
            )
            
            logger.info(f"Hybrid search returned {len(combined_results)} combined results")
            return combined_results
            
        except Exception as e:
            logger.error(f"Error in hybrid search: {e}")
            # Fallback to vector search only
            return self._vector_search(session_id, query, top_k, namespace)
    
    def _vector_search(
        self,
        session_id: str,
        query: str,
        top_k: int,
        namespace: Optional[str]
    ) -> List[Dict]:
        """Perform vector search using Pinecone"""
        try:
            storage = get_pinecone_storage()
            results = storage.query(
                query_text=query,
                top_k=top_k,
                session_id=session_id,
                include_text=True
            )
            
            # Add search method tag
            for result in results:
                result['search_method'] = 'vector'
                result['vector_score'] = result.get('score', 0)
            
            return results
            
        except Exception as e:
            logger.error(f"Error in vector search: {e}")
            return []
    
    def _reciprocal_rank_fusion(
        self,
        bm25_results: List[Dict],
        vector_results: List[Dict],
        top_k: int
    ) -> List[Dict]:
        """
        Reciprocal Rank Fusion (RRF) Algorithm
        Score = sum(1 / (k + rank)) for each result list
        
        RRF is a simple, effective, and FREE reranking method
        """
        # Create a map of chunk_id -> result with combined scores
        fusion_map = {}
        
        # Process BM25 results
        for rank, result in enumerate(bm25_results, start=1):
            chunk_id = self._get_chunk_id(result)
            rrf_score = 1 / (self.rrf_k + rank)
            
            fusion_map[chunk_id] = {
                'chunk': result,
                'bm25_rank': rank,
                'bm25_rrf': rrf_score,
                'vector_rrf': 0,
                'total_score': rrf_score * self.bm25_weight
            }
        
        # Process vector results
        for rank, result in enumerate(vector_results, start=1):
            chunk_id = self._get_chunk_id(result)
            rrf_score = 1 / (self.rrf_k + rank)
            
            if chunk_id in fusion_map:
                # Chunk found in both - add vector score
                fusion_map[chunk_id]['vector_rank'] = rank
                fusion_map[chunk_id]['vector_rrf'] = rrf_score
                fusion_map[chunk_id]['total_score'] += rrf_score * self.vector_weight
            else:
                # New chunk from vector search
                fusion_map[chunk_id] = {
                    'chunk': result,
                    'bm25_rrf': 0,
                    'vector_rank': rank,
                    'vector_rrf': rrf_score,
                    'total_score': rrf_score * self.vector_weight
                }
        
        # Sort by total RRF score
        sorted_results = sorted(
            fusion_map.values(),
            key=lambda x: x['total_score'],
            reverse=True
        )[:top_k]
        
        # Build final result list with metadata
        final_results = []
        for item in sorted_results:
            chunk = item['chunk'].copy()
            chunk['hybrid_score'] = item['total_score']
            chunk['search_method'] = 'hybrid'
            
            # Add ranking details
            chunk['ranking_details'] = {
                'bm25_rank': item.get('bm25_rank'),
                'vector_rank': item.get('vector_rank'),
                'bm25_rrf': item['bm25_rrf'],
                'vector_rrf': item['vector_rrf']
            }
            
            final_results.append(chunk)
        
        return final_results
    
    def _get_chunk_id(self, chunk: Dict) -> str:
        """
        Get unique identifier for a chunk
        Uses multiple fields to ensure uniqueness
        """
        # Try different ID fields
        if 'id' in chunk:
            return str(chunk['id'])
        
        if 'chunk_id' in chunk:
            doc_id = chunk.get('doc_id', '')
            chunk_id = chunk.get('chunk_id', '')
            return f"{doc_id}_{chunk_id}"
        
        # Fallback: hash of text
        text = chunk.get('text', '')
        return str(hash(text))


def hybrid_search(
    session_id: str,
    query: str,
    top_k: int = 5,
    bm25_weight: float = 0.4,
    vector_weight: float = 0.6,
    namespace: Optional[str] = None
) -> List[Dict]:
    """
    Convenience function for hybrid search
    
    Args:
        session_id: Session ID
        query: Search query
        top_k: Number of results
        bm25_weight: Weight for keyword search (0-1)
        vector_weight: Weight for semantic search (0-1)
        namespace: Pinecone namespace
        
    Returns:
        Reranked results combining both search methods
    """
    searcher = HybridSearch(
        bm25_weight=bm25_weight,
        vector_weight=vector_weight
    )
    
    return searcher.search(session_id, query, top_k, namespace)


def keyword_search_only(
    session_id: str,
    query: str,
    top_k: int = 5
) -> List[Dict]:
    """
    Pure BM25 keyword search (no vector)
    
    Args:
        session_id: Session ID
        query: Search query
        top_k: Number of results
        
    Returns:
        BM25 results only
    """
    return search_bm25(session_id, query, top_k)
