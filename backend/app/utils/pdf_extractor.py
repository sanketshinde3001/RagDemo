"""
PDF Extraction Utility Module
Uses PyMuPDF (fitz) to extract text and images from PDF documents
Uploads images to Supabase Storage instead of local disk
"""

import fitz  # PyMuPDF
from PIL import Image
import io
import os
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging
from app.utils.supabase_storage import get_storage_client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PDFExtractor:
    """
    Extract text and images from PDF documents using PyMuPDF
    Uploads images to Supabase Storage
    """
    
    def __init__(self, use_supabase: bool = True):
        """
        Initialize the PDF extractor
        
        Args:
            use_supabase: If True, upload images to Supabase; if False, save locally
        """
        self.use_supabase = use_supabase
        self.storage_client = get_storage_client() if use_supabase else None
    
    def extract_text_and_images(self, pdf_path: str, doc_id: str) -> Dict:
        """
        Extract text and images from a PDF file
        
        Args:
            pdf_path: Path to the PDF file
            doc_id: Unique document identifier
            
        Returns:
            Dictionary containing extraction results with structure:
            {
                'doc_id': str,
                'total_pages': int,
                'pages': [
                    {
                        'page_num': int,
                        'text': str,
                        'images': [
                            {
                                'img_num': int,
                                'filename': str,
                                'bbox': [x0, y0, x1, y1],
                                'width': int,
                                'height': int,
                                'type': str  # 'chart', 'diagram', 'photo', 'unknown'
                            }
                        ]
                    }
                ]
            }
        """
        logger.info(f"Processing PDF: {pdf_path}")
        
        # Open the PDF
        pdf_document = fitz.open(pdf_path)
        
        result = {
            'doc_id': doc_id,
            'total_pages': len(pdf_document),
            'pages': []
        }
        
        # Process each page
        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]
            
            page_data = {
                'page_num': page_num + 1,  # 1-indexed for user-friendliness
                'text': '',
                'images': []
            }
            
            # Extract text
            page_data['text'] = self._extract_text_from_page(page)
            
            # Extract images
            page_data['images'] = self._extract_images_from_page(
                page, 
                doc_id, 
                page_num + 1
            )
            
            result['pages'].append(page_data)
            
            logger.info(f"Processed page {page_num + 1}/{len(pdf_document)}: "
                       f"{len(page_data['text'])} chars, {len(page_data['images'])} images")
        
        pdf_document.close()
        
        logger.info(f"Extraction complete: {result['total_pages']} pages processed")
        return result
    
    def _extract_text_from_page(self, page: fitz.Page) -> str:
        """
        Extract text from a single page
        
        Args:
            page: PyMuPDF page object
            
        Returns:
            Extracted text as string
        """
        return page.get_text()
    
    def _extract_images_from_page(
        self, 
        page: fitz.Page, 
        doc_id: str, 
        page_num: int
    ) -> List[Dict]:
        """
        Extract images from a single page with intelligent filtering
        
        Args:
            page: PyMuPDF page object
            doc_id: Document identifier
            page_num: Page number (1-indexed)
            
        Returns:
            List of image metadata dictionaries (filtered to meaningful images only)
        """
        images = []
        image_list = page.get_images(full=True)
        
        for img_num, img_info in enumerate(image_list, start=1):
            try:
                # Get image reference
                xref = img_info[0]
                
                # Extract image
                base_image = page.parent.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                
                # Get image bounding box (where it appears on the page)
                bbox = self._get_image_bbox(page, xref)
                
                # Open image with PIL to get dimensions and analyze
                pil_image = Image.open(io.BytesIO(image_bytes))
                width, height = pil_image.size
                
                # FILTER OUT USELESS IMAGES
                if self._is_useless_image(pil_image, bbox, page):
                    logger.debug(f"Skipping useless image on page {page_num} (img {img_num}): {width}x{height}")
                    continue
                
                # Determine image type (chart/diagram vs photo)
                img_type = self._classify_image_type(pil_image, image_bytes)
                
                # Generate filename
                filename = f"{doc_id}_page_{page_num}_img_{img_num}.png"
                
                # Convert to PNG bytes
                img_byte_arr = io.BytesIO()
                pil_image.save(img_byte_arr, format='PNG')
                img_byte_arr.seek(0)
                png_bytes = img_byte_arr.getvalue()
                
                # Upload to Supabase Storage or save locally
                if self.use_supabase and self.storage_client:
                    # Upload to Supabase
                    storage_path = f"images/{doc_id}/{filename}"
                    upload_result = self.storage_client.upload_bytes(
                        file_bytes=png_bytes,
                        storage_path=storage_path,
                        content_type='image/png'
                    )
                    
                    image_data = {
                        'img_num': img_num,
                        'filename': filename,
                        'storage_path': upload_result['path'],
                        'url': upload_result['url'],
                        'bbox': bbox,
                        'width': width,
                        'height': height,
                        'type': img_type,
                        'original_ext': image_ext
                    }
                    logger.info(f"✓ Uploaded to Supabase: {filename} ({width}x{height}, type={img_type})")
                else:
                    # Save locally (fallback)
                    local_dir = Path("uploads/extracted")
                    local_dir.mkdir(parents=True, exist_ok=True)
                    save_path = local_dir / filename
                    pil_image.save(save_path, "PNG")
                    
                    image_data = {
                        'img_num': img_num,
                        'filename': filename,
                        'filepath': str(save_path),
                        'bbox': bbox,
                        'width': width,
                        'height': height,
                        'type': img_type,
                        'original_ext': image_ext
                    }
                    logger.info(f"✓ Saved locally: {filename} ({width}x{height}, type={img_type})")
                
                images.append(image_data)
                
            except Exception as e:
                logger.error(f"Error extracting image {img_num} from page {page_num}: {e}")
                continue
        
        return images
    
    def _get_image_bbox(self, page: fitz.Page, xref: int) -> List[float]:
        """
        Get bounding box coordinates for an image on a page
        
        Args:
            page: PyMuPDF page object
            xref: Image reference number
            
        Returns:
            Bounding box as [x0, y0, x1, y1] or None if not found
        """
        try:
            # Get all image instances on the page
            image_instances = page.get_image_rects(xref)
            
            if image_instances:
                # Return the first instance's bounding box
                rect = image_instances[0]
                return [rect.x0, rect.y0, rect.x1, rect.y1]
            else:
                return None
        except Exception as e:
            logger.warning(f"Could not get bbox for image xref {xref}: {e}")
            return None
    
    def _is_useless_image(self, pil_image: Image.Image, bbox: List[float], page: fitz.Page) -> bool:
        """
        Determine if an image is useless (watermark, background, gradient, etc.)
        
        Args:
            pil_image: PIL Image object
            bbox: Bounding box [x0, y0, x1, y1] or None
            page: PyMuPDF page object
            
        Returns:
            True if image should be filtered out, False if it's meaningful
        """
        try:
            width, height = pil_image.size
            
            # Filter 1: Extremely small images (likely icons, bullets, decorations)
            MIN_SIZE = 50
            if width < MIN_SIZE or height < MIN_SIZE:
                logger.debug(f"Filter: Too small ({width}x{height})")
                return True
            
            # Filter 2: Check if image covers full page (likely background/watermark)
            if bbox:
                page_width = page.rect.width
                page_height = page.rect.height
                img_width = bbox[2] - bbox[0]
                img_height = bbox[3] - bbox[1]
                
                coverage_x = img_width / page_width
                coverage_y = img_height / page_height
                
                # If covers >80% of page in both dimensions, likely background
                if coverage_x > 0.8 and coverage_y > 0.8:
                    logger.debug(f"Filter: Full page coverage ({coverage_x:.1%} x {coverage_y:.1%})")
                    return True
            
            # Filter 3: Check for gradients (very few colors but smooth transitions)
            # Convert to RGB for analysis
            if pil_image.mode != 'RGB':
                analysis_image = pil_image.convert('RGB')
            else:
                analysis_image = pil_image
            
            # Get unique colors
            colors = analysis_image.getcolors(maxcolors=256*256)
            
            if colors is not None:
                unique_colors = len(colors)
                total_pixels = width * height
                
                # Filter 3a: Very few colors (1-20) = likely gradient, watermark, or solid color
                if unique_colors < 20:
                    logger.debug(f"Filter: Too few colors ({unique_colors})")
                    return True
                
                # Filter 3b: Check color dominance - if one color is >90%, likely useless
                if colors:
                    max_color_count = max(count for count, _ in colors)
                    dominance = max_color_count / total_pixels
                    if dominance > 0.90:
                        logger.debug(f"Filter: Single color dominance ({dominance:.1%})")
                        return True
            
            # Filter 4: Check for very low contrast (gradients often have low contrast)
            # Sample pixels and check variance
            import numpy as np
            
            # Resize to small size for quick analysis
            small_img = analysis_image.resize((32, 32), Image.Resampling.LANCZOS)
            img_array = np.array(small_img)
            
            # Calculate standard deviation across all channels
            std_dev = np.std(img_array)
            
            # Low std dev = low contrast = likely gradient/watermark
            if std_dev < 15:  # Threshold for low variance
                logger.debug(f"Filter: Low contrast/variance (std={std_dev:.1f})")
                return True
            
            # Filter 5: Check edge density (meaningful images have more edges)
            # Simple edge detection using color differences
            gray = small_img.convert('L')
            gray_array = np.array(gray)
            
            # Calculate horizontal and vertical gradients
            h_grad = np.abs(np.diff(gray_array, axis=1))
            v_grad = np.abs(np.diff(gray_array, axis=0))
            
            edge_density = (np.sum(h_grad > 20) + np.sum(v_grad > 20)) / (32 * 32)
            
            # Very low edge density = smooth gradient or plain background
            if edge_density < 0.05:
                logger.debug(f"Filter: Low edge density ({edge_density:.3f})")
                return True
            
            # Image passed all filters - it's likely meaningful!
            logger.debug(f"✓ Image passed filters: {width}x{height}, colors={unique_colors if colors else 'many'}, std={std_dev:.1f}, edges={edge_density:.3f}")
            return False
            
        except Exception as e:
            logger.warning(f"Error in image filtering: {e}")
            # On error, keep the image (conservative approach)
            return False
    
    def _classify_image_type(self, pil_image: Image.Image, image_bytes: bytes) -> str:
        """
        Classify image as chart/diagram vs photo
        
        This is a simple heuristic-based classification.
        For better results, you could use ML models.
        
        Args:
            pil_image: PIL Image object
            image_bytes: Raw image bytes
            
        Returns:
            'chart', 'diagram', 'photo', or 'unknown'
        """
        try:
            # Simple heuristics:
            # 1. Check color mode
            # 2. Check color diversity
            # 3. Check size
            
            width, height = pil_image.size
            mode = pil_image.mode
            
            # Convert to RGB if needed for analysis
            if mode != 'RGB':
                analysis_image = pil_image.convert('RGB')
            else:
                analysis_image = pil_image
            
            # Get color statistics
            colors = analysis_image.getcolors(maxcolors=256*256)
            
            # Heuristics:
            # - Charts/diagrams typically have fewer unique colors
            # - Photos have more color diversity
            # - Small images are often icons/logos (classify as diagram)
            
            if width < 100 or height < 100:
                return 'diagram'
            
            if colors is not None and len(colors) < 100:
                # Low color diversity -> likely chart/diagram
                return 'chart'
            
            if colors is None or len(colors) > 10000:
                # High color diversity -> likely photo
                return 'photo'
            
            if len(colors) < 1000:
                return 'diagram'
            
            return 'photo'
            
        except Exception as e:
            logger.warning(f"Error classifying image type: {e}")
            return 'unknown'


# Convenience function for simple usage
def extract_pdf(pdf_path: str, doc_id: str, use_supabase: bool = True) -> Dict:
    """
    Convenience function to extract text and images from a PDF
    
    Args:
        pdf_path: Path to PDF file
        doc_id: Document identifier
        use_supabase: If True, upload to Supabase; if False, save locally
        
    Returns:
        Extraction results dictionary
    """
    extractor = PDFExtractor(use_supabase=use_supabase)
    return extractor.extract_text_and_images(pdf_path, doc_id)
    return extractor.extract_text_and_images(pdf_path, doc_id)
