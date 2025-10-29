"""
Semantic Text Chunking for RAG
Intelligently splits text into meaningful chunks while preserving context
Integrates with Pinecone embeddings
"""

from typing import List, Dict, Optional
import re
import logging
from app.utils.pinecone_embedder import get_embedder

logger = logging.getLogger(__name__)


class SemanticChunker:
    """
    Semantic text chunking that preserves meaning and context
    """
    
    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        min_chunk_size: int = 100
    ):
        """
        Initialize semantic chunker
        
        Args:
            chunk_size: Target size for each chunk (in characters)
            chunk_overlap: Overlap between chunks to preserve context
            min_chunk_size: Minimum size for a chunk
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
    
    def chunk_text(
        self,
        text: str,
        metadata: Dict = None
    ) -> List[Dict]:
        """
        Chunk text semantically
        
        Args:
            text: Text to chunk
            metadata: Optional metadata to attach to each chunk
            
        Returns:
            List of chunk dictionaries with text and metadata
        """
        if not text or len(text.strip()) == 0:
            return []
        
        # Split into paragraphs first
        paragraphs = self._split_into_paragraphs(text)
        
        chunks = []
        current_chunk = ""
        current_chunk_start = 0
        
        for para in paragraphs:
            # If paragraph alone is too large, split it further
            if len(para) > self.chunk_size:
                # If we have a current chunk, save it first
                if current_chunk:
                    chunks.append(self._create_chunk(
                        current_chunk,
                        metadata,
                        current_chunk_start,
                        len(current_chunk)
                    ))
                    current_chunk = ""
                
                # Split large paragraph into sentences
                sentences = self._split_into_sentences(para)
                temp_chunk = ""
                
                for sentence in sentences:
                    if len(temp_chunk) + len(sentence) <= self.chunk_size:
                        temp_chunk += sentence + " "
                    else:
                        if temp_chunk:
                            chunks.append(self._create_chunk(
                                temp_chunk.strip(),
                                metadata,
                                current_chunk_start,
                                len(temp_chunk)
                            ))
                            # Add overlap
                            current_chunk_start += len(temp_chunk) - self.chunk_overlap
                        temp_chunk = sentence + " "
                
                if temp_chunk:
                    current_chunk = temp_chunk
                    
            else:
                # Add paragraph to current chunk
                if len(current_chunk) + len(para) <= self.chunk_size:
                    current_chunk += para + "\n\n"
                else:
                    # Save current chunk and start new one
                    if current_chunk:
                        chunks.append(self._create_chunk(
                            current_chunk.strip(),
                            metadata,
                            current_chunk_start,
                            len(current_chunk)
                        ))
                        # Add overlap from end of previous chunk
                        overlap_text = current_chunk[-self.chunk_overlap:] if len(current_chunk) > self.chunk_overlap else current_chunk
                        current_chunk = overlap_text + para + "\n\n"
                        current_chunk_start += len(current_chunk) - len(overlap_text)
                    else:
                        current_chunk = para + "\n\n"
        
        # Add final chunk
        if current_chunk and len(current_chunk.strip()) >= self.min_chunk_size:
            chunks.append(self._create_chunk(
                current_chunk.strip(),
                metadata,
                current_chunk_start,
                len(current_chunk)
            ))
        
        return chunks
    
    def chunk_pdf_pages(
        self,
        extraction_result: Dict,
        page_wise: bool = False,
        overlap_pages: int = 0
    ) -> List[Dict]:
        """
        Chunk PDF pages with metadata
        
        Args:
            extraction_result: PDF extraction result from pdf_extractor
            page_wise: If True, create one chunk per page (with optional overlap)
            overlap_pages: Number of pages to overlap (0 = no overlap, 1 = include previous page, etc.)
            
        Returns:
            List of chunks with metadata (page number, doc_id, etc.)
        """
        all_chunks = []
        
        doc_id = extraction_result.get('doc_id', 'unknown')
        pages = extraction_result['pages']
        
        if page_wise:
            # PAGE-WISE CHUNKING: One chunk per page (with optional overlap)
            logger.info(f"Using PAGE-WISE chunking (overlap_pages={overlap_pages})")
            
            for idx, page in enumerate(pages):
                page_num = page['page_num']
                text = page['text']
                images = page['images']
                
                # Build chunk text with overlap from previous pages
                chunk_text = text
                overlapped_pages = [page_num]
                
                # Add overlap from previous pages if requested
                if overlap_pages > 0 and idx > 0:
                    for overlap_idx in range(1, min(overlap_pages + 1, idx + 1)):
                        prev_page = pages[idx - overlap_idx]
                        prev_text = prev_page['text']
                        
                        # Add last 30% of previous page for context
                        overlap_length = int(len(prev_text) * 0.3)
                        overlap_text = prev_text[-overlap_length:] if overlap_length > 0 else ""
                        
                        if overlap_text:
                            chunk_text = f"[...from previous page]\n{overlap_text}\n\n{chunk_text}"
                            overlapped_pages.insert(0, prev_page['page_num'])
                
                # Create metadata for this page
                # Convert page numbers to integers and then to comma-separated string for Pinecone
                page_nums_int = [int(p) for p in overlapped_pages]
                pages_str = ','.join(map(str, page_nums_int))  # "1,2,3"
                
                page_metadata = {
                    'doc_id': doc_id,
                    'page_num': int(page_num),  # Single page number as integer
                    'pages': pages_str,  # Comma-separated string of all pages in chunk
                    'has_images': len(images) > 0,
                    'num_images': len(images),
                    'image_types': [img.get('type') for img in images] if images else [],
                    'chunk_strategy': 'page_wise'
                }
                
                # Add image descriptions if available
                if images:
                    image_descriptions = []
                    for img in images:
                        if 'gemini_analysis' in img:
                            image_descriptions.append({
                                'filename': img['filename'],
                                'type': img['type'],
                                'description': img['gemini_analysis']
                            })
                    if image_descriptions:
                        page_metadata['images'] = image_descriptions
                
                # Create the chunk
                chunk = {
                    'text': chunk_text,
                    'length': len(chunk_text),
                    'chunk_id': idx,
                    'start_pos': 0,  # Page-wise chunks start at position 0
                    **page_metadata
                }
                
                all_chunks.append(chunk)
            
            logger.info(f"Created {len(all_chunks)} PAGE-WISE chunks from {len(pages)} pages")
            
        else:
            # CHARACTER-BASED CHUNKING (old method)
            logger.info(f"Using CHARACTER-BASED chunking (chunk_size={self.chunk_size})")
            
            for page in pages:
                page_num = page['page_num']
                text = page['text']
                images = page['images']
                
                # Create metadata for this page
                page_metadata = {
                    'doc_id': doc_id,
                    'page_num': int(page_num),  # Convert to integer
                    'has_images': len(images) > 0,
                    'num_images': len(images),
                    'image_types': [img.get('type') for img in images] if images else [],
                    'chunk_strategy': 'character_based'
                }
                
                # Add image descriptions if available
                if images:
                    image_descriptions = []
                    for img in images:
                        if 'gemini_analysis' in img:
                            image_descriptions.append({
                                'filename': img['filename'],
                                'type': img['type'],
                                'description': img['gemini_analysis']
                            })
                    if image_descriptions:
                        page_metadata['images'] = image_descriptions
                
                # Chunk the page text
                page_chunks = self.chunk_text(text, metadata=page_metadata)
                all_chunks.extend(page_chunks)
            
            # Add global chunk IDs
            for idx, chunk in enumerate(all_chunks):
                chunk['chunk_id'] = idx
            
            logger.info(f"Created {len(all_chunks)} CHARACTER-BASED chunks from {len(pages)} pages")
        
        return all_chunks
    
    def _split_into_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs"""
        # Split on double newlines or more
        paragraphs = re.split(r'\n\s*\n', text)
        return [p.strip() for p in paragraphs if p.strip()]
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        # Simple sentence splitting (can be improved with NLP libraries)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _create_chunk(
        self,
        text: str,
        metadata: Dict,
        start_pos: int,
        length: int
    ) -> Dict:
        """Create a chunk dictionary"""
        chunk = {
            'text': text,
            'length': len(text),
            'start_pos': start_pos
        }
        
        if metadata:
            chunk.update(metadata)
        
        return chunk


def chunk_pdf_extraction(
    extraction_result: Dict,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    generate_embeddings: bool = False,
    page_wise: bool = False,
    overlap_pages: int = 0
) -> Dict:
    """
    Convenience function to add chunked text to extraction result
    
    Args:
        extraction_result: PDF extraction result
        chunk_size: Target chunk size (for character-based chunking)
        chunk_overlap: Overlap between chunks (for character-based chunking)
        generate_embeddings: If True, generate embeddings for each chunk
        page_wise: If True, use page-wise chunking (one chunk per page)
        overlap_pages: Number of pages to overlap (0 = no overlap, 1 = include 30% of previous page)
        
    Returns:
        Extraction result with added 'chunks' key
    """
    chunker = SemanticChunker(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    
    chunks = chunker.chunk_pdf_pages(
        extraction_result,
        page_wise=page_wise,
        overlap_pages=overlap_pages
    )
    
    # Optionally generate embeddings
    if generate_embeddings:
        try:
            logger.info(f"Generating embeddings for {len(chunks)} chunks...")
            embedder = get_embedder()
            chunks = embedder.embed_chunks(chunks)
            logger.info(f"✓ Embeddings generated for all chunks")
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            # Continue without embeddings
    
    extraction_result['chunks'] = chunks
    extraction_result['total_chunks'] = len(chunks)
    
    return extraction_result
