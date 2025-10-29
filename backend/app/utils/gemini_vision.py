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
            
            # Generate response with increased max_output_tokens
            generation_config = {
                "temperature": 0.7,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 2048,  # Increased from default 1024 to 2048
            }
            
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            # Extract sources from chunks
            sources = self._extract_sources(context_chunks)
            
            # Convert inline citations to clickable links
            answer = self._convert_citations_to_links(response.text, sources)
            
            return {
                'success': True,
                'answer': answer,
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
        """Build context string from retrieved chunks, grouped by page"""
        context_parts = []
        total_length = 0
        
        # Group chunks by page number
        pages_dict = {}
        for chunk in chunks:
            page = chunk.get('page_num', 'unknown')
            if page not in pages_dict:
                pages_dict[page] = []
            pages_dict[page].append(chunk)
        
        # Create context with page-based numbering
        page_num = 1
        for page, page_chunks in pages_dict.items():
            # Combine all chunks from the same page
            page_texts = [chunk.get('text', '') for chunk in page_chunks]
            combined_text = '\n'.join(page_texts)
            
            filename = page_chunks[0].get('filename', 'unknown')
            avg_score = sum(chunk.get('score', 0) for chunk in page_chunks) / len(page_chunks)
            
            # Format with page number as source
            chunk_text = f"\n[Source {page_num}] (Page {page}, {filename}, Relevance: {avg_score:.2f})\n{combined_text}\n"
            
            # Check length
            if total_length + len(chunk_text) > max_length:
                break
            
            context_parts.append(chunk_text)
            total_length += len(chunk_text)
            page_num += 1
        
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
- Provide comprehensive, detailed answers in a natural, conversational style
- Use **markdown formatting** sparingly and strategically:
  * Use **bold** ONLY for 2-3 most important terms or section titles
  * Use bullet points (- or numbers) for lists
  * Use ## for main section headings (use sparingly, 1-2 max)
- Write in clear, flowing paragraphs (3-5 paragraphs for complex questions)
- Answer based ONLY on the information in the context below

CRITICAL - CITATION RULES:
- When referencing information, cite the source number [1], [2], [3] etc.
- Each source number corresponds to a PAGE in the document (not individual chunks)
- Place citations strategically - NOT after every sentence
- Cite once per paragraph or when introducing new information from a specific page
- Multiple facts from the same page can share one citation at the end
- DO NOT over-cite - keep it clean and readable

CITATION EXAMPLES:

✅ CORRECT (minimal citations):
Sanket Rajendra Shinde is a Software Development Engineer seeking opportunities. He has experience at Neurolaw AI where he developed custom RAG pipelines, integrated Cloud OCR, and built real-time court scrapers [1]. 

His technical skills include Full Stack development, Cloud technologies, and AI/ML & GenAI [1]. He has several projects including Quickmed and InterviewAce [1].

❌ WRONG (too many citations):
Sanket [1] is a Software Development Engineer [1]. He works at Neurolaw AI [1]. He has skills [1].
""")
        
        # Add conversation history if present
        if history:
            prompt_parts.append(f"\n{history}\n")
        
        # Add context
        prompt_parts.append(f"\nRELEVANT CONTEXT FROM DOCUMENTS:\n{context}\n")
        
        # Add current query
        prompt_parts.append(f"\nCURRENT QUESTION: {query}\n")
        prompt_parts.append("\nANSWER (use markdown formatting):")
        
        return "\n".join(prompt_parts)
    
    def _convert_citations_to_links(self, text: str, sources: List[Dict]) -> str:
        """
        Convert citation numbers [1], [2] to clickable markdown links
        [1] -> [1](url#page=1)
        [2] -> [2](url#page=2)
        """
        import re
        
        # Find all [1], [2], [3] patterns
        def replace_citation(match):
            citation_num = int(match.group(1))
            
            # Get the corresponding source (1-indexed)
            if 0 < citation_num <= len(sources):
                source = sources[citation_num - 1]
                url = source['url']
                pages = source['pages']
                
                # Use first page for the link - convert to int to remove .0
                page = int(pages[0]) if pages else 1
                link = f"{url}#page={page}"
                
                # Create clickable citation - single brackets only
                return f'[{citation_num}]({link})'
            
            return match.group(0)  # Return original if source not found
        
        # Replace all [1], [2], [3] etc with clickable links
        converted_text = re.sub(r'\[(\d+)\]', replace_citation, text)
        
        return converted_text
    
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
