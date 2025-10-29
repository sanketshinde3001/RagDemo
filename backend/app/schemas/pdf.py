"""
Pydantic schemas for PDF upload and processing
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict


class ImageInfo(BaseModel):
    """Information about an extracted image"""
    img_num: int
    filename: str
    filepath: str
    bbox: Optional[List[float]] = None
    width: int
    height: int
    type: str = Field(..., description="Image type: chart, diagram, photo, or unknown")
    original_ext: str


class PageInfo(BaseModel):
    """Information about a processed PDF page"""
    page_num: int
    text: str
    images: List[ImageInfo] = []


class PDFExtractionResult(BaseModel):
    """Complete PDF extraction result"""
    doc_id: str
    total_pages: int
    pages: List[PageInfo]


class PDFUploadResponse(BaseModel):
    """Response after PDF upload"""
    success: bool
    message: str
    doc_id: str
    session_id: str = Field(..., description="Session ID for this upload (use this for chat queries)")
    filename: str
    total_pages: int
    total_images: int
    extraction_result: Optional[PDFExtractionResult] = None


class ProcessingStatus(BaseModel):
    """Processing status response"""
    doc_id: str
    status: str = Field(..., description="Status: processing, completed, failed")
    progress: Optional[float] = Field(None, description="Progress percentage (0-100)")
    message: Optional[str] = None


class ChatRequest(BaseModel):
    """Request for chatting with documents"""
    query: str = Field(..., description="User's question")
    session_id: str = Field(..., description="Session ID to search within")
    top_k: int = Field(5, description="Number of context chunks to retrieve")
    enable_web_search: bool = Field(False, description="Enable web search for non-document queries")
    search_mode: str = Field("vector", description="Search mode: 'vector' (default), 'keyword' (BM25), or 'hybrid' (both)")


class ContextChunk(BaseModel):
    """A context chunk retrieved from vector store"""
    text: str
    score: float
    doc_id: str
    page_num: Optional[int] = None
    pdf_url: Optional[str] = None
    type: str = Field(..., description="Type: text_chunk or image")


class SourceDocument(BaseModel):
    """Source document information"""
    url: str = Field(..., description="Supabase public URL of the PDF")
    filename: Optional[str] = Field(None, description="Original filename")
    pages: List[int] = Field(default_factory=list, description="Relevant page numbers")


class ChatResponse(BaseModel):
    """Response from chat endpoint"""
    answer: str = Field(..., description="Generated answer")
    context: List[ContextChunk] = Field(..., description="Retrieved context chunks")
    session_id: str
    query: str
    sources: Optional[List[SourceDocument]] = Field(default_factory=list, description="Source documents cited")

