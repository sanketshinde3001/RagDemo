'use client';

import { useState, useRef, useEffect } from 'react';
import { uploadPDF, chatWithDocuments, PDFUploadResponse, ChatResponse, SourceDocument } from '@/lib/api';
import VoiceInput from '@/components/VoiceInput';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  sources?: SourceDocument[];
  timestamp: Date;
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [uploading, setUploading] = useState(false);
  const [chatting, setChatting] = useState(false);
  const [sessionId, setSessionId] = useState<string>('');
  const [uploadedDoc, setUploadedDoc] = useState<PDFUploadResponse | null>(null);
  const [showExtractedText, setShowExtractedText] = useState(false);
  const [webSearchEnabled, setWebSearchEnabled] = useState(false);
  const [searchMode, setSearchMode] = useState<'vector' | 'keyword' | 'hybrid'>('hybrid');
  const [chunkingStrategy, setChunkingStrategy] = useState<'page_wise' | 'semantic'>('page_wise');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Helper function to resize textarea
  const resizeTextarea = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 120) + 'px';
    }
  };

  // Generate session ID on mount
  useEffect(() => {
    const newSessionId = generateSessionId();
    setSessionId(newSessionId);
    setMessages([{
      role: 'system',
      content: 'Welcome! Upload a PDF document to start chatting with it.',
      timestamp: new Date()
    }]);
  }, []);

  const generateSessionId = () => {
    return Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
  };

  // Handle PDF upload
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.name.endsWith('.pdf')) {
      alert('Please upload a PDF file');
      return;
    }

    setUploading(true);
    setMessages(prev => [...prev, { 
      role: 'system', 
      content: `Uploading ${file.name}...`,
      timestamp: new Date()
    }]);

    try {
      const response = await uploadPDF(file, sessionId, chunkingStrategy);
      setUploadedDoc(response);
      setShowExtractedText(false);
      
      // CRITICAL: Update session ID to match what backend returned
      const backendSessionId = response.session_id || response.extraction_result?.pinecone_storage?.session_id;
      if (backendSessionId) {
        setSessionId(backendSessionId);
        console.log('✅ Session ID updated:', {
          old: sessionId,
          new: backendSessionId
        });
      } else {
        console.error('⚠️ Backend did not return session_id!', response);
      }
      
      const vectorInfo = response.extraction_result?.pinecone_storage;
      
      setMessages(prev => [
        ...prev,
        {
          role: 'system',
          content: `**PDF Uploaded Successfully**

**File:** ${response.filename}
**Pages:** ${response.total_pages}
**Images:** ${response.total_images}
**Session ID:** ${response.session_id}
${vectorInfo ? `**Vectors Stored:** ${vectorInfo.total_vectors} (${vectorInfo.chunks_stored} text chunks + ${vectorInfo.images_stored} images)` : ''}

You can now ask questions about this document.`,
          timestamp: new Date()
        }
      ]);
    } catch (error) {
      setMessages(prev => [
        ...prev,
        {
          role: 'system',
          content: `**Upload Error:** ${error instanceof Error ? error.message : 'Upload failed'}`,
          timestamp: new Date()
        }
      ]);
    } finally {
      setUploading(false);
    }
  };

  // Handle chat message
  const handleSendMessage = async (messageText?: string) => {
    const textToSend = messageText || input.trim();
    
    if (!textToSend || chatting) return;

    if (!uploadedDoc) {
      setMessages(prev => [...prev, {
        role: 'system',
        content: 'Please upload a PDF document first before asking questions.',
        timestamp: new Date()
      }]);
      return;
    }

    // Clear input only if using text input
    if (!messageText) {
      setInput('');
    }
    
    console.log('💬 Sending chat with session_id:', sessionId);
    
    // Add user message
    setMessages(prev => [...prev, {
      role: 'user',
      content: textToSend,
      timestamp: new Date()
    }]);

    setChatting(true);

    try {
      const response: ChatResponse = await chatWithDocuments({
        query: textToSend,
        session_id: sessionId,
        top_k: 5,
        enable_web_search: webSearchEnabled,
        search_mode: searchMode
      });

      // Add assistant response with sources
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: response.answer,
        sources: response.sources,
        timestamp: new Date()
      }]);

    } catch (error) {
      setMessages(prev => [...prev, {
        role: 'system',
        content: `**Error:** ${error instanceof Error ? error.message : 'Failed to get response'}`,
        timestamp: new Date()
      }]);
    } finally {
      setChatting(false);
    }
  };

  // Handle voice transcript - just update the input field
  const handleVoiceTranscript = (text: string, isFinal: boolean) => {
    console.log('🎤 Voice transcript:', text, 'Final:', isFinal);
    
    // Only update on final transcripts to avoid duplicates
    if (isFinal && text.trim()) {
      // Append to existing input (in case there were multiple utterances)
      setInput(prev => {
        // If there's existing text, add a space before appending
        const newText = prev.trim() ? `${prev.trim()} ${text.trim()}` : text.trim();
        
        // Trigger textarea resize after state update
        setTimeout(() => resizeTextarea(), 0);
        
        return newText;
      });
    }
    // Interim transcripts are shown in the VoiceInput component's floating pill (not in textbox)
  };

  return (
    <div className="flex flex-col h-screen bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800">
      {/* Header - Mobile Optimized */}
      <header className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700 px-3 sm:px-6 py-3 sm:py-4">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 sm:gap-0">
          <div>
            <h1 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-white">
              RAG Chatbot
            </h1>
            <p className="text-xs sm:text-sm text-gray-600 dark:text-gray-400 mt-1">
              Intelligent document analysis powered by AI
            </p>
          </div>
          {uploadedDoc && (
            <div className="text-left sm:text-right bg-blue-50 dark:bg-blue-900/20 px-3 sm:px-4 py-2 rounded-lg border border-blue-200 dark:border-blue-800 w-full sm:w-auto">
              <div className="text-xs text-blue-600 dark:text-blue-400 font-medium">Active Session</div>
              <div className="text-xs font-mono text-gray-700 dark:text-gray-300 mt-0.5 truncate">{sessionId}</div>
            </div>
          )}
        </div>
      </header>

      {/* Chat Area - Mobile Optimized */}
      <div className="flex-1 overflow-y-auto px-3 sm:px-6 py-4 sm:py-8">
        <div className="max-w-4xl mx-auto space-y-4 sm:space-y-6">
          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[90%] sm:max-w-[85%] rounded-xl px-4 sm:px-5 py-3 sm:py-4 ${
                  msg.role === 'user'
                    ? 'bg-blue-600 text-white shadow-md'
                    : msg.role === 'assistant'
                    ? 'bg-white dark:bg-gray-800 text-gray-900 dark:text-white border border-gray-200 dark:border-gray-700 shadow-md'
                    : 'bg-amber-50 dark:bg-amber-900/20 text-amber-900 dark:text-amber-200 border border-amber-200 dark:border-amber-800'
                }`}
              >
              {/* Message content */}
              <div className="prose prose-sm max-w-none dark:prose-invert prose-headings:font-bold prose-h1:text-lg sm:prose-h1:text-xl prose-h2:text-base sm:prose-h2:text-lg prose-h3:text-sm sm:prose-h3:text-base prose-p:my-2 prose-ul:my-2 prose-ol:my-2 prose-li:my-1 prose-strong:font-semibold prose-code:bg-gray-100 dark:prose-code:bg-gray-700 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-xs sm:prose-code:text-sm">
                {msg.role === 'assistant' || msg.role === 'system' ? (
                  <ReactMarkdown 
                    remarkPlugins={[remarkGfm]}
                    components={{
                      a: ({ node, ...props }) => (
                        <a 
                          {...props} 
                          target="_blank" 
                          rel="noopener noreferrer" 
                          className="inline-flex items-center px-1.5 py-0.5 mx-0.5 text-xs font-semibold text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30 hover:bg-blue-100 dark:hover:bg-blue-900/50 rounded border border-blue-200 dark:border-blue-700 no-underline cursor-pointer transition-colors"
                        />
                      )
                    }}
                  >
                    {msg.content}
                  </ReactMarkdown>
                ) : (
                  msg.content
                )}
              </div>
              
              {/* Sources */}
              {msg.sources && msg.sources.length > 0 && (
                <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-600">
                  <div className="text-xs font-semibold text-gray-600 dark:text-gray-400 mb-2 uppercase tracking-wide">
                    Sources
                  </div>
                  <div className="space-y-2">
                    {msg.sources.map((source, sidx) => (
                      <div key={sidx} className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3 text-xs border border-gray-200 dark:border-gray-600">
                        <a
                          href={source.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 font-medium flex items-center gap-2 transition-colors mb-2"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                          <span>{source.filename || 'Document'}</span>
                        </a>
                        {source.pages.length > 0 && (
                          <div className="flex flex-wrap gap-1 ml-6">
                            <span className="text-gray-600 dark:text-gray-400 text-xs mr-1">Pages:</span>
                            {source.pages.map((page: number, pidx: number) => (
                              <a
                                key={pidx}
                                href={`${source.url}#page=${page}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center px-2 py-0.5 rounded bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 hover:bg-blue-200 dark:hover:bg-blue-900/50 transition-colors text-xs font-medium"
                                title={`Open page ${page}`}
                              >
                                {page}
                              </a>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {/* Timestamp */}
              <div className="text-xs text-gray-500 dark:text-gray-400 mt-3">
                {msg.timestamp.toLocaleTimeString()}
              </div>
            </div>
          </div>
        ))}

        {chatting && (
          <div className="flex justify-start">
            <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl px-5 py-4 shadow-md">
              <div className="flex items-center gap-3">
                <div className="animate-spin h-5 w-5 border-2 border-blue-600 border-t-transparent rounded-full" />
                <span className="text-gray-600 dark:text-gray-400 font-medium">Analyzing your question...</span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Extracted Text Panel (Collapsible) */}
      {showExtractedText && uploadedDoc?.extraction_result && (
        <div className="border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-6 py-4 max-h-64 overflow-y-auto">
          <div className="max-w-4xl mx-auto">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-gray-900 dark:text-white">
                Extracted Text from PDF
              </h3>
              <button
                onClick={() => setShowExtractedText(false)}
                className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="space-y-4">
              {uploadedDoc.extraction_result.pages.map((page) => (
                <div key={page.page_num} className="border-b border-gray-200 dark:border-gray-700 pb-3 last:border-b-0">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs font-semibold bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 px-2 py-1 rounded">
                      Page {page.page_num}
                    </span>
                    <span className="text-xs text-gray-500 dark:text-gray-400">
                      {page.text.length} characters
                    </span>
                    {page.images.length > 0 && (
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        • {page.images.length} image{page.images.length > 1 ? 's' : ''}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap font-mono">
                    {page.text || '(No text on this page)'}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Input Area - Centered */}
      <div className="border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-6 py-5 shadow-sm">
        <div className="max-w-4xl mx-auto">
          {/* PDF Upload Button */}
          <div className="mb-4 flex items-center gap-3 flex-wrap">
            {/* Chunking Strategy Selector */}
            <div className="flex items-center gap-2 px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg">
              <span className="text-xs font-medium text-gray-700 dark:text-gray-300">Chunking:</span>
              <button
                type="button"
                onClick={() => setChunkingStrategy('page_wise')}
                disabled={uploading}
                className={`px-3 py-1 text-xs rounded transition-colors ${
                  chunkingStrategy === 'page_wise' 
                    ? 'bg-green-600 text-white' 
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
                } disabled:opacity-50`}
                title="⚡ Fast: 1 chunk per page, instant indexing"
              >
                ⚡ Fast
              </button>
              <button
                type="button"
                onClick={() => setChunkingStrategy('semantic')}
                disabled={uploading}
                className={`px-3 py-1 text-xs rounded transition-colors ${
                  chunkingStrategy === 'semantic' 
                    ? 'bg-purple-600 text-white' 
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
                } disabled:opacity-50`}
                title="🧠 Smart: 3-5 chunks per page, better context (10-30s wait)"
              >
                🧠 Smart
              </button>
            </div>
            
            <label className="inline-flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg cursor-pointer transition-all shadow-sm">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
              <span className="text-sm font-semibold">
                {uploading ? 'Uploading...' : 'Upload PDF'}
              </span>
              <input
                type="file"
              accept=".pdf"
              onChange={handleFileUpload}
              disabled={uploading}
              className="hidden"
            />
          </label>
          
          {uploadedDoc && (
            <>
              <div className="flex items-center gap-2 px-4 py-2 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
                <svg className="w-5 h-5 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                <span className="text-sm font-medium text-green-700 dark:text-green-300">{uploadedDoc.filename}</span>
              </div>
              <button
                onClick={() => setShowExtractedText(!showExtractedText)}
                className="px-4 py-2 text-xs font-medium bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 hover:bg-blue-100 dark:hover:bg-blue-900/30 rounded-lg transition-all border border-blue-200 dark:border-blue-800"
              >
                {showExtractedText ? 'Hide' : 'Show'} Extracted Text
              </button>
              
              <button
                onClick={() => {
                  const newSessionId = generateSessionId();
                  setSessionId(newSessionId);
                  setUploadedDoc(null);
                  setShowExtractedText(false);
                  setMessages([{
                    role: 'system',
                    content: 'New session started. Upload a PDF to begin.',
                    timestamp: new Date()
                  }]);
                }}
                className="px-4 py-2 text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-lg transition-all ml-auto"
              >
                New Session
              </button>
            </>
          )}
        </div>

        {/* Voice + Message Input - Mobile Optimized */}
        <div className="flex flex-col sm:flex-row gap-2 sm:gap-3 items-stretch sm:items-center">
          {/* Row 1: Voice + Text Input + Send (Mobile stacks vertically on small screens) */}
          <div className="flex gap-2 items-center flex-1">
            {/* Voice Input - Wrapped in relative container for floating transcript */}
            <div className="relative">
              <VoiceInput 
                onTranscript={handleVoiceTranscript}
                disabled={!uploadedDoc || chatting}
              />
            </div>
            
            {/* Text Input - Enhanced Responsiveness with Ref */}
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                resizeTextarea();
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSendMessage();
                }
              }}
              placeholder={uploadedDoc ? "Ask a question..." : "Upload PDF first..."}
              disabled={!uploadedDoc || chatting}
              rows={1}
              className="flex-1 px-3 sm:px-4 py-2 sm:py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-all text-sm resize-none overflow-hidden"
              style={{ minHeight: '42px', maxHeight: '120px' }}
            />
            
            {/* Send Button */}
            <button
              onClick={() => handleSendMessage()}
              disabled={!input.trim() || !uploadedDoc || chatting}
              className="px-4 sm:px-8 py-2 sm:py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-all font-semibold shadow-sm text-sm whitespace-nowrap"
            >
              {chatting ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  <span className="hidden sm:inline">Sending</span>
                </span>
              ) : 'Send'}
            </button>
          </div>
          
          {/* Row 2: Web Search + Search Modes (Horizontal on mobile, stays together) */}
          <div className="flex gap-2 items-center justify-between sm:justify-start">
            {/* Web Search Toggle - Compact */}
            <div className="flex items-center gap-1.5 px-2 sm:px-3 py-1.5 sm:py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg">
              <span className="text-xs text-gray-600 dark:text-gray-400 whitespace-nowrap hidden sm:inline">Web Search</span>
              <span className="text-xs text-gray-600 dark:text-gray-400 whitespace-nowrap sm:hidden">Web</span>
              <button
                type="button"
                onClick={() => setWebSearchEnabled(!webSearchEnabled)}
                className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                  webSearchEnabled ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600'
                }`}
              >
                <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                  webSearchEnabled ? 'translate-x-5' : 'translate-x-0.5'
                }`} />
              </button>
            </div>
            
            {/* Search Mode Selector - Compact */}
            <div className="flex items-center gap-0.5 sm:gap-1 px-1.5 sm:px-2 py-1 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg">
              <button
                type="button"
                onClick={() => setSearchMode('vector')}
                className={`px-1.5 sm:px-2 py-1 text-base sm:text-xs rounded transition-colors ${
                  searchMode === 'vector' 
                    ? 'bg-blue-600 text-white' 
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
                }`}
                title="Semantic search using embeddings"
              >
                🧠
              </button>
              <button
                type="button"
                onClick={() => setSearchMode('keyword')}
                className={`px-1.5 sm:px-2 py-1 text-base sm:text-xs rounded transition-colors ${
                  searchMode === 'keyword' 
                    ? 'bg-blue-600 text-white' 
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
                }`}
                title="Keyword search using BM25"
              >
                🔍
              </button>
              <button
                type="button"
                onClick={() => setSearchMode('hybrid')}
                className={`px-1.5 sm:px-2 py-1 text-base sm:text-xs rounded transition-colors ${
                  searchMode === 'hybrid' 
                    ? 'bg-blue-600 text-white' 
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
                }`}
                title="Hybrid: BM25 + Vector (Best)"
              >
                ⚡
              </button>
            </div>
          </div>
        </div>
        
        <div className="mt-3 sm:mt-4 text-xs text-gray-500 dark:text-gray-400 text-center px-2">
          <span className="hidden sm:inline">Click mic to speak (transcript goes to textbox) • Edit if needed • Press Enter or click Send • Choose Fast⚡ or Smart🧠 chunking before upload • </span>
          <span className="font-semibold">Powered by Gemini 2.0 Flash + Deepgram + Pinecone + FREE BM25</span>
        </div>
        </div>
      </div>
    </div>
  );
}
