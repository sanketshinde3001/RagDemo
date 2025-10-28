"""
Gemini 2.5 Flash Vision Integration
Analyzes extracted images from PDFs using Google's Gemini model
Also handles RAG chat with context and history
"""

import google.generativeai as genai
from pathlib import Path
from typing import Dict, List, Optional
import logging
from PIL import Image

logger = logging.getLogger(__name__)


class GeminiVisionAnalyzer:
    """
    Use Gemini 2.5 Flash to analyze images extracted from PDFs
    """
    
    def __init__(self, api_key: str):
        """
        Initialize Gemini Vision Analyzer
        
        Args:
            api_key: Google API key for Gemini
        """
        genai.configure(api_key=api_key)
        # Use Gemini 2.5 Flash as specified
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
        logger.info("Gemini 2.5 Flash Vision Analyzer initialized")
    
    def chat_with_context(
        self,
        query: str,
        context_chunks: List[Dict],
        chat_history: Optional[List[Dict]] = None,
        max_context_length: int = 8000
    ) -> Dict[str, any]:
        """
        Generate chat response with RAG context and conversation history
        
        Args:
            query: User's question
            context_chunks: Retrieved chunks from Pinecone
            chat_history: Previous conversation messages [{'role': 'user'|'assistant', 'message': '...'}]
            max_context_length: Maximum context length in characters
            
        Returns:
            Response dictionary with answer, sources, and metadata
        """
        try:
            # Build context from chunks
            context_text = self._build_context(context_chunks, max_context_length)
            
            # Build conversation history
            history_text = self._build_history(chat_history) if chat_history else ""
            
            # Create RAG prompt
            prompt = self._create_rag_prompt(query, context_text, history_text)
            
            logger.info(f"Generating response for query: {query[:100]}...")
            logger.info(f"  Context chunks: {len(context_chunks)}")
            logger.info(f"  History messages: {len(chat_history) if chat_history else 0}")
            
            # Generate response
            response = self.model.generate_content(prompt)
            
            # Extract sources from chunks
            sources = self._extract_sources(context_chunks)
            
            return {
                'success': True,
                'answer': response.text,
                'sources': sources,
                'num_chunks': len(context_chunks),
                'model': 'gemini-2.0-flash-exp'
            }
            
        except Exception as e:
            logger.error(f"Error generating chat response: {e}")
            return {
                'success': False,
                'answer': f"I apologize, but I encountered an error: {str(e)}",
                'sources': [],
                'num_chunks': 0,
                'model': 'gemini-2.0-flash-exp'
            }
    
    def _build_context(self, chunks: List[Dict], max_length: int) -> str:
        """Build context string from retrieved chunks"""
        context_parts = []
        total_length = 0
        
        for i, chunk in enumerate(chunks, 1):
            # Get chunk info
            text = chunk.get('text', '')
            score = chunk.get('score', 0)
            chunk_type = chunk.get('type', 'text')
            page = chunk.get('page_num', 'unknown')
            filename = chunk.get('filename', 'unknown')
            
            # Format chunk with metadata
            chunk_text = f"\n[Source {i}] (Page {page}, {filename}, Relevance: {score:.2f})\n{text}\n"
            
            # Check length
            if total_length + len(chunk_text) > max_length:
                break
            
            context_parts.append(chunk_text)
            total_length += len(chunk_text)
        
        return "\n".join(context_parts)
    
    def _build_history(self, history: List[Dict]) -> str:
        """Build conversation history string"""
        if not history:
            return ""
        
        history_parts = ["Previous conversation:"]
        
        for msg in history[-10:]:  # Last 10 messages
            role = msg.get('role', 'user')
            message = msg.get('message', '')
            
            if role == 'user':
                history_parts.append(f"User: {message}")
            else:
                history_parts.append(f"Assistant: {message}")
        
        return "\n".join(history_parts)
    
    def _create_rag_prompt(self, query: str, context: str, history: str) -> str:
        """Create RAG prompt with context and history"""
        
        prompt_parts = []
        
        # System instruction
        prompt_parts.append("""You are a helpful AI assistant that answers questions based on the provided document context.

IMPORTANT INSTRUCTIONS:
- Answer based ONLY on the information in the context below
- If the context doesn't contain relevant information, say "I don't have enough information to answer that question based on the provided documents."
- Cite sources by mentioning page numbers and document names when possible
- Be concise but comprehensive
- If there's conversation history, use it to understand context but prioritize the latest question
""")
        
        # Add conversation history if present
        if history:
            prompt_parts.append(f"\n{history}\n")
        
        # Add context
        prompt_parts.append(f"\nRELEVANT CONTEXT FROM DOCUMENTS:\n{context}\n")
        
        # Add current query
        prompt_parts.append(f"\nCURRENT QUESTION: {query}\n")
        prompt_parts.append("\nANSWER:")
        
        return "\n".join(prompt_parts)
    
    def _extract_sources(self, chunks: List[Dict]) -> List[Dict]:
        """Extract unique sources from chunks"""
        sources = {}
        
        for chunk in chunks:
            pdf_url = chunk.get('pdf_url')
            filename = chunk.get('filename')
            page = chunk.get('page_num')
            
            if pdf_url and pdf_url not in sources:
                sources[pdf_url] = {
                    'url': pdf_url,
                    'filename': filename,
                    'pages': [page] if page else []
                }
            elif pdf_url and page:
                if page not in sources[pdf_url]['pages']:
                    sources[pdf_url]['pages'].append(page)
        
        # Convert to list and sort pages
        result = []
        for source in sources.values():
            source['pages'] = sorted(set(source['pages']))
            result.append(source)
        
        return result
    
    def analyze_image(self, image_path: str, context: str = "") -> Dict[str, str]:
        """
        Analyze a single image using Gemini Vision
        
        Args:
            image_path: Path to the image file
            context: Optional context about the image (e.g., page text)
            
        Returns:
            Dictionary with analysis results
        """
        try:
            # Load the image
            img = Image.open(image_path)
            
            # Create prompt for image analysis
            prompt = self._create_analysis_prompt(context)
            
            # Generate content using Gemini
            response = self.model.generate_content([prompt, img])
            
            return {
                'success': True,
                'description': response.text,
                'model': 'gemini-2.0-flash-exp'
            }
            
        except Exception as e:
            logger.error(f"Error analyzing image {image_path}: {e}")
            return {
                'success': False,
                'description': f"Error: {str(e)}",
                'model': 'gemini-2.0-flash-exp'
            }
    
    def analyze_multiple_images(
        self, 
        images: List[Dict], 
        page_text: str = ""
    ) -> List[Dict]:
        """
        Analyze multiple images from a page
        
        Args:
            images: List of image info dicts with 'filepath' key
            page_text: Text from the same page for context
            
        Returns:
            List of analysis results
        """
        results = []
        
        for img_info in images:
            image_path = img_info.get('filepath')
            if not image_path or not Path(image_path).exists():
                logger.warning(f"Image not found: {image_path}")
                continue
            
            logger.info(f"Analyzing image: {img_info.get('filename')}")
            
            analysis = self.analyze_image(image_path, context=page_text)
            
            # Add analysis to image info
            result = {
                **img_info,
                'gemini_analysis': analysis['description'],
                'analysis_success': analysis['success']
            }
            results.append(result)
        
        return results
    
    def _create_analysis_prompt(self, context: str = "") -> str:
        """
        Create a prompt for image analysis
        
        Args:
            context: Optional context text
            
        Returns:
            Prompt string
        """
        base_prompt = """Analyze this image in detail. Provide:
1. What type of visual is this? (chart, diagram, graph, table, photo, illustration, etc.)
2. What is the main subject or purpose?
3. Key information or data shown
4. Any text visible in the image
5. How this relates to the document context

Be concise but thorough."""
        
        if context:
            # Truncate context if too long
            context_preview = context[:500] if len(context) > 500 else context
            base_prompt += f"\n\nDocument context: {context_preview}"
        
        return base_prompt
    
    def analyze_chart_data(self, image_path: str) -> Dict:
        """
        Specialized analysis for charts and graphs
        
        Args:
            image_path: Path to chart image
            
        Returns:
            Extracted data and insights
        """
        try:
            img = Image.open(image_path)
            
            prompt = """This appears to be a chart or graph. Please extract:
1. Chart type (bar, line, pie, scatter, etc.)
2. Title (if visible)
3. Axis labels and ranges
4. Data points or trends
5. Key insights or conclusions
6. Any legends or annotations

Provide the information in a structured format."""
            
            response = self.model.generate_content([prompt, img])
            
            return {
                'success': True,
                'chart_data': response.text,
                'model': 'gemini-2.0-flash-exp'
            }
            
        except Exception as e:
            logger.error(f"Error analyzing chart {image_path}: {e}")
            return {
                'success': False,
                'chart_data': f"Error: {str(e)}",
                'model': 'gemini-2.0-flash-exp'
            }


def analyze_pdf_images(
    extraction_result: Dict,
    api_key: str
) -> Dict:
    """
    Convenience function to analyze all images in a PDF extraction result
    
    Args:
        extraction_result: PDF extraction result from pdf_extractor
        api_key: Google API key
        
    Returns:
        Updated extraction result with Gemini analysis
    """
    analyzer = GeminiVisionAnalyzer(api_key)
    
    for page in extraction_result['pages']:
        if page['images']:
            logger.info(f"Analyzing {len(page['images'])} images on page {page['page_num']}")
            page['images'] = analyzer.analyze_multiple_images(
                page['images'],
                page_text=page['text']
            )
    
    return extraction_result
