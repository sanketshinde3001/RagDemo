// API configuration and service functions for backend communication

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Types
export interface ImageInfo {
  img_num: number;
  filename: string;
  filepath: string;
  bbox: number[] | null;
  width: number;
  height: number;
  type: string;
  original_ext: string;
}

export interface PageInfo {
  page_num: number;
  text: string;
  images: ImageInfo[];
}

export interface PDFExtractionResult {
  doc_id: string;
  total_pages: number;
  pages: PageInfo[];
  pinecone_storage?: {
    total_vectors: number;
    chunks_stored: number;
    images_stored: number;
    doc_id: string;
    session_id: string;
  };
}

export interface PDFUploadResponse {
  success: boolean;
  message: string;
  doc_id: string;
  session_id: string;  // Session ID returned from backend
  filename: string;
  total_pages: number;
  total_images: number;
  extraction_result?: PDFExtractionResult;
}

export interface ProcessingStatus {
  doc_id: string;
  status: string;
  progress?: number;
  message?: string;
}

export interface ContextChunk {
  text: string;
  score: number;
  doc_id: string;
  page_num?: number;
  pdf_url?: string;
  type: string;
}

export interface SourceDocument {
  url: string;
  filename?: string;
  pages: number[];
}

export interface ChatRequest {
  query: string;
  session_id: string;
  top_k?: number;
}

export interface ChatResponse {
  answer: string;
  context: ContextChunk[];
  session_id: string;
  query: string;
  sources?: SourceDocument[];
}

// Upload PDF to backend
export async function uploadPDF(file: File, sessionId?: string): Promise<PDFUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  if (sessionId) {
    formData.append('session_id', sessionId);
  }

  const response = await fetch(`${API_BASE_URL}/api/v1/upload-pdf`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(error.detail || 'Failed to upload PDF');
  }

  return response.json();
}

// Get processing status
export async function getProcessingStatus(docId: string): Promise<ProcessingStatus> {
  const response = await fetch(`${API_BASE_URL}/api/v1/processing-status/${docId}`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Status check failed' }));
    throw new Error(error.detail || 'Failed to get status');
  }

  return response.json();
}

// Health check
export async function healthCheck(): Promise<{ status: string }> {
  const response = await fetch(`${API_BASE_URL}/health`);
  return response.json();
}

// Chat with documents
export async function chatWithDocuments(request: ChatRequest): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Chat failed' }));
    throw new Error(error.detail || 'Failed to get answer');
  }

  return response.json();
}
