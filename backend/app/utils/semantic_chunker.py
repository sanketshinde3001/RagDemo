"""
Semantic Text Chunking for RAG
Intelligently splits text based on document structure and meaning
"""

from typing import List, Dict, Optional
import re
import logging

logger = logging.getLogger(__name__)


class SemanticChunker:
    """
    Smart chunking that respects document structure:
    - Headings and sections
    - Paragraph boundaries
    - Sentence boundaries for overlap
    """
    
    def __init__(
        self,
        max_chunk_size: int = 1500,
        min_chunk_size: int = 300,
        overlap_sentences: int = 2
    ):
        """
        Initialize semantic chunker
        
        Args:
            max_chunk_size: Maximum characters per chunk
            min_chunk_size: Minimum characters per chunk
            overlap_sentences: Number of sentences to overlap between chunks
        """
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size
        self.overlap_sentences = overlap_sentences
        
        # Common section heading patterns
        self.heading_patterns = [
            r'^#+\s+.+$',  # Markdown headings
            r'^[A-Z][A-Z\s]{2,}:?\s*$',  # ALL CAPS HEADINGS
            r'^\d+\.\s+[A-Z].+$',  # 1. Numbered Headings
            r'^[A-Z][a-z]+(\s+[A-Z][a-z]+)*:\s*$',  # Title Case Headings:
        ]
    
    def chunk_text(
        self,
        text: str,
        metadata: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Chunk text semantically with smart boundaries
        
        Args:
            text: Text to chunk
            metadata: Metadata to attach to chunks
            
        Returns:
            List of chunk dictionaries
        """
        if not text or len(text.strip()) == 0:
            return []
        
        # Split into sections by headings
        sections = self._split_into_sections(text)
        
        chunks = []
        previous_overlap = ""
        
        for section in sections:
            section_text = section['text']
            section_heading = section.get('heading', '')
            
            # If section is small enough, make it one chunk
            if len(section_text) <= self.max_chunk_size:
                chunk_text = previous_overlap + section_text
                
                if len(chunk_text) >= self.min_chunk_size:
                    chunks.append(self._create_chunk(
                        chunk_text,
                        metadata,
                        section_heading
                    ))
                    previous_overlap = self._get_sentence_overlap(chunk_text)
                
            else:
                # Split large section by paragraphs
                paragraphs = self._split_into_paragraphs(section_text)
                current_chunk = previous_overlap
                
                for para in paragraphs:
                    # Try to add paragraph to current chunk
                    if len(current_chunk) + len(para) <= self.max_chunk_size:
                        current_chunk += para + "\n\n"
                    else:
                        # Save current chunk if it meets minimum size
                        if len(current_chunk.strip()) >= self.min_chunk_size:
                            chunks.append(self._create_chunk(
                                current_chunk.strip(),
                                metadata,
                                section_heading
                            ))
                            current_chunk = self._get_sentence_overlap(current_chunk) + para + "\n\n"
                        else:
                            current_chunk += para + "\n\n"
                
                # Save remaining chunk
                if len(current_chunk.strip()) >= self.min_chunk_size:
                    chunks.append(self._create_chunk(
                        current_chunk.strip(),
                        metadata,
                        section_heading
                    ))
                    previous_overlap = self._get_sentence_overlap(current_chunk)
        
        return chunks
    
    def chunk_pdf_pages(
        self,
        extraction_result: Dict,
        strategy: str = "semantic"
    ) -> List[Dict]:
        """
        Chunk PDF pages with semantic awareness
        
        Args:
            extraction_result: PDF extraction result
            strategy: "semantic" or "page_wise"
            
        Returns:
            List of chunks with metadata
        """
        all_chunks = []
        doc_id = extraction_result.get('doc_id', 'unknown')
        
        if strategy == "page_wise":
            # Page-wise chunking (one chunk per page with overlap)
            return self._chunk_page_wise(extraction_result)
        
        # Semantic chunking (across page boundaries)
        for page in extraction_result['pages']:
            page_num = page['page_num']
            text = page['text']
            images = page.get('images', [])
            
            # Add image descriptions to text if available
            enhanced_text = text
            if images:
                image_descriptions = []
                for img in images:
                    if 'gemini_analysis' in img:
                        desc = img['gemini_analysis'][:200]  # Truncate long descriptions
                        image_descriptions.append(f"[Image: {desc}]")
                
                if image_descriptions:
                    enhanced_text = text + "\n\n" + "\n".join(image_descriptions)
            
            # Create metadata
            page_metadata = {
                'doc_id': doc_id,
                'page_num': page_num,
                'has_images': len(images) > 0,
                'num_images': len(images)
            }
            
            # Chunk the enhanced text
            page_chunks = self.chunk_text(enhanced_text, metadata=page_metadata)
            all_chunks.extend(page_chunks)
        
        # Add global chunk IDs
        for idx, chunk in enumerate(all_chunks):
            chunk['chunk_id'] = idx
        
        logger.info(f"Created {len(all_chunks)} semantic chunks from {len(extraction_result['pages'])} pages")
        
        return all_chunks
    
    def _chunk_page_wise(self, extraction_result: Dict) -> List[Dict]:
        """
        Page-wise chunking with overlap
        """
        all_chunks = []
        doc_id = extraction_result.get('doc_id', 'unknown')
        pages = extraction_result['pages']
        
        for i, page in enumerate(pages):
            page_num = page['page_num']
            text = page['text']
            
            # Add overlap from previous page
            if i > 0 and len(pages[i-1]['text']) > 0:
                prev_text = pages[i-1]['text']
                overlap = self._get_sentence_overlap(prev_text)
                text = overlap + "\n\n" + text
            
            # Create chunk
            chunk = {
                'text': text,
                'doc_id': doc_id,
                'page_num': page_num,
                'pages': str(page_num),
                'has_images': len(page.get('images', [])) > 0,
                'num_images': len(page.get('images', [])),
                'chunk_id': i,
                'length': len(text),
                'start_pos': 0
            }
            
            all_chunks.append(chunk)
        
        logger.info(f"Created {len(all_chunks)} PAGE-WISE chunks from {len(pages)} pages")
        return all_chunks
    
    def _split_into_sections(self, text: str) -> List[Dict]:
        """
        Split text into sections based on headings
        """
        sections = []
        current_section = ""
        current_heading = ""
        
        lines = text.split('\n')
        
        for line in lines:
            # Check if line is a heading
            is_heading = False
            for pattern in self.heading_patterns:
                if re.match(pattern, line.strip(), re.MULTILINE):
                    is_heading = True
                    break
            
            if is_heading and current_section:
                # Save previous section
                sections.append({
                    'heading': current_heading,
                    'text': current_section.strip()
                })
                current_section = ""
                current_heading = line.strip()
            elif is_heading:
                current_heading = line.strip()
            else:
                current_section += line + "\n"
        
        # Add final section
        if current_section.strip():
            sections.append({
                'heading': current_heading,
                'text': current_section.strip()
            })
        
        # If no sections found, treat entire text as one section
        if not sections:
            sections = [{'heading': '', 'text': text}]
        
        return sections
    
    def _split_into_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs"""
        paragraphs = re.split(r'\n\s*\n', text)
        return [p.strip() for p in paragraphs if p.strip()]
    
    def _get_sentence_overlap(self, text: str) -> str:
        """
        Get last N sentences for overlap
        Smart overlap at sentence boundaries
        """
        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        # Get last N sentences
        overlap_sentences = sentences[-self.overlap_sentences:] if len(sentences) >= self.overlap_sentences else sentences
        
        return " ".join(overlap_sentences)
    
    def _create_chunk(
        self,
        text: str,
        metadata: Optional[Dict],
        section_heading: str = ""
    ) -> Dict:
        """Create a chunk dictionary"""
        chunk = {
            'text': text,
            'length': len(text),
            'start_pos': 0
        }
        
        if section_heading:
            chunk['section_heading'] = section_heading
        
        if metadata:
            chunk.update(metadata)
        
        return chunk


def chunk_pdf_extraction(
    extraction_result: Dict,
    strategy: str = "semantic",
    max_chunk_size: int = 1500,
    min_chunk_size: int = 300,
    generate_embeddings: bool = False
) -> Dict:
    """
    Convenience function to chunk PDF extraction result
    
    Args:
        extraction_result: PDF extraction result
        strategy: "semantic" or "page_wise"
        max_chunk_size: Maximum chunk size
        min_chunk_size: Minimum chunk size
        generate_embeddings: Generate embeddings for chunks
        
    Returns:
        Extraction result with 'chunks' added
    """
    chunker = SemanticChunker(
        max_chunk_size=max_chunk_size,
        min_chunk_size=min_chunk_size,
        overlap_sentences=2
    )
    
    chunks = chunker.chunk_pdf_pages(extraction_result, strategy=strategy)
    
    # Generate embeddings if requested
    if generate_embeddings:
        try:
            from app.utils.pinecone_embedder import get_embedder
            logger.info(f"Generating embeddings for {len(chunks)} chunks...")
            embedder = get_embedder()
            chunks = embedder.embed_chunks(chunks)
            logger.info(f"✓ Embeddings generated for all chunks")
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
    
    extraction_result['chunks'] = chunks
    extraction_result['total_chunks'] = len(chunks)
    
    return extraction_result
