"""
Pinecone Vector Storage Utility
Stores document chunks and image metadata with embeddings in Pinecone
"""

from pinecone import Pinecone, ServerlessSpec
from app.core.config import settings
from app.utils.pinecone_embedder import get_embedder
import logging
from typing import List, Dict, Optional
import time
import uuid

logger = logging.getLogger(__name__)


class PineconeStorage:
    """
    Manage vector storage in Pinecone
    """
    
    def __init__(self):
        """Initialize Pinecone client and index"""
        self.pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        self.index_name = settings.PINECONE_INDEX_NAME
        self.embedding_dimensions = settings.EMBEDDING_DIMENSIONS
        
        # Get or create index
        self._ensure_index_exists()
        self.index = self.pc.Index(self.index_name)
        
        logger.info(f"Pinecone storage initialized with index: {self.index_name}")
    
    def _ensure_index_exists(self):
        """Ensure the Pinecone index exists"""
        try:
            # Check if index exists
            existing_indexes = [idx.name for idx in self.pc.list_indexes()]
            
            if self.index_name not in existing_indexes:
                logger.info(f"Creating Pinecone index: {self.index_name}")
                
                # Create index
                self.pc.create_index(
                    name=self.index_name,
                    dimension=self.embedding_dimensions,
                    metric='cosine',
                    spec=ServerlessSpec(
                        cloud='aws',
                        region=settings.PINECONE_ENVIRONMENT
                    )
                )
                
                # Wait for index to be ready
                logger.info("Waiting for index to be ready...")
                time.sleep(5)
                
                logger.info(f"✓ Index created: {self.index_name}")
            else:
                logger.info(f"Using existing index: {self.index_name}")
                
        except Exception as e:
            logger.error(f"Error ensuring index exists: {e}")
            raise
    
    def store_chunks(
        self,
        chunks: List[Dict],
        doc_id: str,
        namespace: Optional[str] = None,
        pdf_url: Optional[str] = None,
        session_id: Optional[str] = None,
        filename: Optional[str] = None
    ) -> Dict:
        """
        Store text chunks with embeddings in Pinecone
        
        Args:
            chunks: List of chunk dictionaries with 'embedding' and metadata
            doc_id: Document identifier
            namespace: Optional namespace for organizing vectors
            pdf_url: URL of the source PDF in Supabase
            session_id: Session ID for chat-based filtering
            filename: Original filename
            
        Returns:
            Storage result dictionary
        """
        try:
            if not chunks:
                logger.warning("No chunks to store")
                return {'stored': 0, 'doc_id': doc_id}
            
            # Prepare vectors for upsert
            vectors = []
            
            for i, chunk in enumerate(chunks):
                # Generate unique vector ID
                vector_id = f"{doc_id}_chunk_{i}"
                
                # Get embedding
                embedding = chunk.get('embedding')
                if not embedding:
                    logger.warning(f"Chunk {i} has no embedding, skipping")
                    continue
                
                # Prepare metadata
                metadata = {
                    'doc_id': doc_id,
                    'chunk_id': i,
                    'text': chunk.get('text', ''),
                    'type': 'text_chunk',
                    'page_num': chunk.get('page_num'),
                    'length': chunk.get('length'),
                    'start_pos': chunk.get('start_pos')
                }
                
                # Add PDF URL and session tracking
                if pdf_url:
                    metadata['pdf_url'] = pdf_url
                if session_id:
                    metadata['session_id'] = session_id
                if filename:
                    metadata['filename'] = filename
                
                # Add any additional metadata from chunk
                for key, value in chunk.items():
                    if key not in ['embedding', 'text', 'embedding_model', 'embedding_dimensions']:
                        if value is not None and key not in metadata:
                            metadata[key] = value
                
                vectors.append({
                    'id': vector_id,
                    'values': embedding,
                    'metadata': metadata
                })
            
            if not vectors:
                logger.warning("No valid vectors to store")
                return {'stored': 0, 'doc_id': doc_id}
            
            # Upsert vectors to Pinecone in batches
            batch_size = 100
            total_stored = 0
            
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i:i + batch_size]
                self.index.upsert(vectors=batch, namespace=namespace or "")
                total_stored += len(batch)
                logger.debug(f"Stored batch {i//batch_size + 1}: {len(batch)} vectors")
            
            logger.info(f"✓ Stored {total_stored} text chunks in Pinecone")
            
            return {
                'stored': total_stored,
                'doc_id': doc_id,
                'namespace': namespace
            }
            
        except Exception as e:
            logger.error(f"Error storing chunks in Pinecone: {e}")
            raise
    
    def store_images(
        self,
        images: List[Dict],
        doc_id: str,
        namespace: Optional[str] = None,
        pdf_url: Optional[str] = None,
        session_id: Optional[str] = None,
        filename: Optional[str] = None
    ) -> Dict:
        """
        Store image metadata with embeddings in Pinecone
        
        Args:
            images: List of image dictionaries with metadata
            doc_id: Document identifier
            namespace: Optional namespace
            pdf_url: URL of the source PDF
            session_id: Session ID for filtering
            filename: Original filename
            
        Returns:
            Storage result dictionary
        """
        try:
            if not images:
                logger.info("No images to store")
                return {'stored': 0, 'doc_id': doc_id}
            
            # For images, we'll use Gemini's analysis text as the searchable content
            # and generate embeddings from that
            embedder = get_embedder()
            vectors = []
            
            for i, img in enumerate(images):
                # Generate unique vector ID
                vector_id = f"{doc_id}_image_{i}"
                
                # Get text for embedding (from Gemini analysis or description)
                text_for_embedding = img.get('gemini_analysis', '') or img.get('caption', '') or f"Image {i+1}"
                
                # Generate embedding
                try:
                    embedding = embedder.embed_text(text_for_embedding)
                except Exception as e:
                    logger.warning(f"Could not generate embedding for image {i}: {e}")
                    continue
                
                # Prepare metadata
                metadata = {
                    'doc_id': doc_id,
                    'image_id': i,
                    'type': 'image',
                    'filename': img.get('filename'),
                    'url': img.get('url'),
                    'storage_path': img.get('storage_path'),
                    'page_num': img.get('page_num'),
                    'width': img.get('width'),
                    'height': img.get('height'),
                    'image_type': img.get('type'),
                    'analysis': text_for_embedding[:1000]  # Store first 1000 chars
                }
                
                # Add PDF URL and session tracking
                if pdf_url:
                    metadata['pdf_url'] = pdf_url
                if session_id:
                    metadata['session_id'] = session_id
                if filename:
                    metadata['source_filename'] = filename
                
                # Add bounding box if available
                if img.get('bbox'):
                    metadata['bbox'] = str(img['bbox'])
                
                vectors.append({
                    'id': vector_id,
                    'values': embedding,
                    'metadata': metadata
                })
            
            if not vectors:
                logger.warning("No valid image vectors to store")
                return {'stored': 0, 'doc_id': doc_id}
            
            # Upsert vectors
            self.index.upsert(vectors=vectors, namespace=namespace or "")
            
            logger.info(f"✓ Stored {len(vectors)} image vectors in Pinecone")
            
            return {
                'stored': len(vectors),
                'doc_id': doc_id,
                'namespace': namespace
            }
            
        except Exception as e:
            logger.error(f"Error storing images in Pinecone: {e}")
            raise
    
    def store_document(
        self,
        extraction_result: Dict,
        namespace: Optional[str] = None
    ) -> Dict:
        """
        Store complete document (chunks + images) in Pinecone
        
        Args:
            extraction_result: Complete extraction result with chunks and images
            namespace: Optional namespace
            
        Returns:
            Combined storage result
        """
        doc_id = extraction_result['doc_id']
        pdf_url = extraction_result.get('pdf_url')
        session_id = extraction_result.get('session_id')
        filename = extraction_result.get('filename')
        
        # Store text chunks with PDF metadata
        chunks = extraction_result.get('chunks', [])
        chunk_result = self.store_chunks(
            chunks, 
            doc_id, 
            namespace,
            pdf_url=pdf_url,
            session_id=session_id,
            filename=filename
        )
        
        # Store images from all pages with PDF metadata
        all_images = []
        for page in extraction_result.get('pages', []):
            for img in page.get('images', []):
                img['page_num'] = page['page_num']  # Add page number
                all_images.append(img)
        
        image_result = self.store_images(
            all_images, 
            doc_id, 
            namespace,
            pdf_url=pdf_url,
            session_id=session_id,
            filename=filename
        )
        
        result = {
            'doc_id': doc_id,
            'session_id': session_id,
            'chunks_stored': chunk_result['stored'],
            'images_stored': image_result['stored'],
            'total_vectors': chunk_result['stored'] + image_result['stored'],
            'namespace': namespace,
            'pdf_url': pdf_url
        }
        
        logger.info(f"✓ Document {doc_id} stored: {result['total_vectors']} vectors (session: {session_id})")
        
        return result
    
    def query(
        self,
        query_text: str,
        top_k: int = 5,
        namespace: Optional[str] = None,
        filter_dict: Optional[Dict] = None,
        session_id: Optional[str] = None,
        include_text: bool = True
    ) -> List[Dict]:
        """
        Query Pinecone for similar vectors
        
        Args:
            query_text: Query text
            top_k: Number of results to return
            namespace: Optional namespace to search
            filter_dict: Optional metadata filter
            session_id: If provided, only search within this session's documents
            include_text: Include full text content in results (default: True)
            
        Returns:
            List of matching results with metadata and similarity scores
        """
        try:
            # Generate query embedding
            embedder = get_embedder()
            query_embedding = embedder.embed_query(query_text)
            
            # Add session_id to filter if provided
            if session_id and not filter_dict:
                filter_dict = {'session_id': session_id}
            elif session_id and filter_dict:
                filter_dict['session_id'] = session_id
            
            # Query Pinecone
            results = self.index.query(
                vector=query_embedding,
                top_k=top_k,
                namespace=namespace or "",
                filter=filter_dict,
                include_metadata=True
            )
            
            # Format results with enhanced information
            matches = []
            for match in results.matches:
                result = {
                    'id': match.id,
                    'score': float(match.score),
                    'text': match.metadata.get('text', '') if include_text else None,
                    'type': match.metadata.get('type', 'unknown'),
                    'page_num': match.metadata.get('page_num'),
                    'pdf_url': match.metadata.get('pdf_url'),
                    'filename': match.metadata.get('filename') or match.metadata.get('source_filename'),
                    'metadata': match.metadata
                }
                matches.append(result)
            
            logger.info(f"✓ Query returned {len(matches)} results (session: {session_id or 'all'})")
            if matches:
                logger.info(f"  Top score: {matches[0]['score']:.4f}, Type: {matches[0]['type']}")
            
            return matches
            
        except Exception as e:
            logger.error(f"Error querying Pinecone: {e}")
            raise
    
    def delete_document(self, doc_id: str, namespace: Optional[str] = None):
        """Delete all vectors for a document"""
        try:
            self.index.delete(
                filter={'doc_id': doc_id},
                namespace=namespace or ""
            )
            logger.info(f"✓ Deleted vectors for document {doc_id}")
        except Exception as e:
            logger.error(f"Error deleting document: {e}")
            raise


# Singleton instance
_storage = None

def get_pinecone_storage() -> PineconeStorage:
    """Get or create Pinecone storage singleton"""
    global _storage
    if _storage is None:
        _storage = PineconeStorage()
    return _storage
