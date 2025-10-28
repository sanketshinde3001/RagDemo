"""
Pinecone Embedding Utility
Uses Pinecone's hosted inference API for embeddings
"""

from pinecone import Pinecone
from app.core.config import settings
import logging
from typing import List, Dict, Union
import time

logger = logging.getLogger(__name__)


class PineconeEmbedder:
    """
    Generate embeddings using Pinecone's hosted inference API
    No local model needed - embeddings are generated server-side
    """
    
    def __init__(self):
        """Initialize Pinecone client"""
        self.pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        self.embedding_model = settings.EMBEDDING_MODEL
        self.embedding_dimensions = settings.EMBEDDING_DIMENSIONS
        logger.info(f"Pinecone embedder initialized with model: {self.embedding_model}")
    
    def embed_texts(self, texts: List[str], batch_size: int = 96, max_retries: int = 3) -> List[List[float]]:
        """
        Generate embeddings for a list of texts using Pinecone's inference API
        
        Args:
            texts: List of text strings to embed
            batch_size: Number of texts to embed in each batch (max 96 for Pinecone)
            max_retries: Maximum number of retry attempts per batch
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        all_embeddings = []
        
        try:
            # Process in batches
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                
                logger.debug(f"Embedding batch {i//batch_size + 1}: {len(batch)} texts")
                
                # Retry logic for this batch
                for attempt in range(max_retries):
                    try:
                        # Use Pinecone's inference API to generate embeddings
                        response = self.pc.inference.embed(
                            model=self.embedding_model,
                            inputs=batch,
                            parameters={
                                "input_type": "passage"  # or "query" for search queries
                            }
                        )
                        
                        # Extract embeddings from response
                        batch_embeddings = [item['values'] for item in response.data]
                        all_embeddings.extend(batch_embeddings)
                        break  # Success, exit retry loop
                        
                    except Exception as e:
                        wait_time = 2 ** attempt
                        logger.warning(f"Batch {i//batch_size + 1} attempt {attempt + 1}/{max_retries} failed: {e}")
                        
                        if attempt < max_retries - 1:
                            logger.info(f"Retrying batch in {wait_time}s...")
                            time.sleep(wait_time)
                        else:
                            logger.error(f"Batch failed after {max_retries} attempts")
                            raise
                
                # Small delay between batches to avoid rate limits
                if i + batch_size < len(texts):
                    time.sleep(0.1)
            
            logger.info(f"✓ Generated {len(all_embeddings)} embeddings")
            return all_embeddings
            
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise
    
    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text
        
        Args:
            text: Text string to embed
            
        Returns:
            Embedding vector
        """
        embeddings = self.embed_texts([text])
        return embeddings[0] if embeddings else []
    
    def embed_query(self, query: str, max_retries: int = 3) -> List[float]:
        """
        Generate embedding for a search query with retry logic
        
        Args:
            query: Query string
            max_retries: Maximum number of retry attempts
            
        Returns:
            Query embedding vector
        """
        for attempt in range(max_retries):
            try:
                response = self.pc.inference.embed(
                    model=self.embedding_model,
                    inputs=[query],
                    parameters={
                        "input_type": "query"  # Optimized for search queries
                    }
                )
                
                embedding = response.data[0]['values']
                logger.debug(f"✓ Generated query embedding (dim={len(embedding)})")
                return embedding
                
            except Exception as e:
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {e}")
                
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Error generating query embedding after {max_retries} attempts: {e}")
                    raise
    
    def embed_chunks(self, chunks: List[Dict]) -> List[Dict]:
        """
        Add embeddings to text chunks
        
        Args:
            chunks: List of chunk dictionaries with 'text' field
            
        Returns:
            Chunks with added 'embedding' field
        """
        try:
            # Extract texts from chunks
            texts = [chunk['text'] for chunk in chunks]
            
            logger.info(f"Embedding {len(texts)} text chunks...")
            
            # Generate embeddings
            embeddings = self.embed_texts(texts)
            
            # Add embeddings to chunks
            for chunk, embedding in zip(chunks, embeddings):
                chunk['embedding'] = embedding
                chunk['embedding_model'] = self.embedding_model
                chunk['embedding_dimensions'] = len(embedding)
            
            logger.info(f"✓ Added embeddings to {len(chunks)} chunks")
            return chunks
            
        except Exception as e:
            logger.error(f"Error embedding chunks: {e}")
            raise


# Singleton instance
_embedder = None

def get_embedder() -> PineconeEmbedder:
    """Get or create embedder singleton"""
    global _embedder
    if _embedder is None:
        _embedder = PineconeEmbedder()
    return _embedder


def embed_text(text: str) -> List[float]:
    """Quick function to embed a single text"""
    embedder = get_embedder()
    return embedder.embed_text(text)


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Quick function to embed multiple texts"""
    embedder = get_embedder()
    return embedder.embed_texts(texts)


def embed_query(query: str) -> List[float]:
    """Quick function to embed a query"""
    embedder = get_embedder()
    return embedder.embed_query(query)
