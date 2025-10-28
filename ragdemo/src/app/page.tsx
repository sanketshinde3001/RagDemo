'use client';

import { useState, useRef, useEffect } from 'react';
import { uploadPDF, chatWithDocuments, PDFUploadResponse, ChatResponse, SourceDocument } from '@/lib/api';
import VoiceInput from '@/components/VoiceInput';

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
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Generate session ID on mount
  useEffect(() => {
    const newSessionId = generateSessionId();
    setSessionId(newSessionId);
    setMessages([{
      role: 'system',
      content: '👋 Welcome! Upload a PDF document to start chatting with it.',
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
      content: `📤 Uploading ${file.name}...`,
      timestamp: new Date()
    }]);

    try {
      const response = await uploadPDF(file, sessionId);
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
          content: `✅ **PDF Uploaded Successfully!**

📄 **File:** ${response.filename}
📊 **Pages:** ${response.total_pages}
🖼️ **Images:** ${response.total_images}
🔑 **Session ID:** ${response.session_id}
${vectorInfo ? `🔢 **Vectors Stored:** ${vectorInfo.total_vectors} (${vectorInfo.chunks_stored} text chunks + ${vectorInfo.images_stored} images)` : ''}

💬 You can now ask questions about this document!`,
          timestamp: new Date()
        }
      ]);
    } catch (error) {
      setMessages(prev => [
        ...prev,
        {
          role: 'system',
          content: `❌ **Upload Error:** ${error instanceof Error ? error.message : 'Upload failed'}`,
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
        content: '⚠️ Please upload a PDF document first before asking questions.',
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
        top_k: 5
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
        content: `❌ **Error:** ${error instanceof Error ? error.message : 'Failed to get response'}`,
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
        return newText;
      });
    }
    // Interim transcripts are shown in the VoiceInput component's blue pill (not in textbox)
  };

  return (
    <div className="flex flex-col h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              📚 RAG Chatbot
            </h1>
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
              Chat with your PDF documents using AI
            </p>
          </div>
          {uploadedDoc && (
            <div className="text-right">
              <div className="text-xs text-gray-500 dark:text-gray-400">Session</div>
              <div className="text-sm font-mono text-gray-700 dark:text-gray-300">{sessionId}</div>
            </div>
          )}
        </div>
      </header>

      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[80%] rounded-lg px-4 py-3 ${
                msg.role === 'user'
                  ? 'bg-blue-500 text-white'
                  : msg.role === 'assistant'
                  ? 'bg-white dark:bg-gray-800 text-gray-900 dark:text-white border border-gray-200 dark:border-gray-700 shadow-sm'
                  : 'bg-amber-50 dark:bg-amber-900/20 text-amber-900 dark:text-amber-200 border border-amber-200 dark:border-amber-800'
              }`}
            >
              {/* Message content */}
              <div className="whitespace-pre-wrap mb-2">{msg.content}</div>
              
              {/* Sources */}
              {msg.sources && msg.sources.length > 0 && (
                <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-600">
                  <div className="text-xs font-semibold text-gray-600 dark:text-gray-400 mb-2">
                    📎 Sources:
                  </div>
                  <div className="space-y-1">
                    {msg.sources.map((source, sidx) => (
                      <div key={sidx} className="text-xs">
                        <a
                          href={source.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1"
                        >
                          <span>🔗</span>
                          <span>{source.filename || 'Document'}</span>
                          {source.pages.length > 0 && (
                            <span className="text-gray-500 dark:text-gray-400">
                              (Pages: {source.pages.join(', ')})
                            </span>
                          )}
                        </a>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {/* Timestamp */}
              <div className="text-xs opacity-50 mt-2">
                {msg.timestamp.toLocaleTimeString()}
              </div>
            </div>
          </div>
        ))}

        {chatting && (
          <div className="flex justify-start">
            <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg px-4 py-3 shadow-sm">
              <div className="flex items-center gap-2">
                <div className="animate-spin h-4 w-4 border-2 border-blue-500 border-t-transparent rounded-full" />
                <span className="text-gray-600 dark:text-gray-400">Thinking...</span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Extracted Text Panel (Collapsible) */}
      {showExtractedText && uploadedDoc?.extraction_result && (
        <div className="border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 px-6 py-4 max-h-64 overflow-y-auto">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-gray-900 dark:text-white flex items-center gap-2">
              📝 Extracted Text from PDF
            </h3>
            <button
              onClick={() => setShowExtractedText(false)}
              className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
            >
              ✕
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
      )}

      {/* Input Area */}
      <div className="border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-6 py-4 shadow-lg">
        {/* PDF Upload Button */}
        <div className="mb-3 flex items-center gap-3 flex-wrap">
          <label className="inline-flex items-center gap-2 px-4 py-2 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-lg cursor-pointer transition-colors">
            <span className="text-xl">📎</span>
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
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
              <span className="text-sm text-green-600 dark:text-green-400 flex items-center gap-1">
                <span>✓</span>
                <span className="font-medium">{uploadedDoc.filename}</span>
              </span>
              <button
                onClick={() => setShowExtractedText(!showExtractedText)}
                className="px-3 py-1.5 text-xs bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 hover:bg-blue-200 dark:hover:bg-blue-800 rounded-md transition-colors"
              >
                {showExtractedText ? '🔼 Hide' : '🔽 Show'} Extracted Text
              </button>
              
              <button
                onClick={() => {
                  const newSessionId = generateSessionId();
                  setSessionId(newSessionId);
                  setUploadedDoc(null);
                  setShowExtractedText(false);
                  setMessages([{
                    role: 'system',
                    content: '🔄 New session started. Upload a PDF to begin.',
                    timestamp: new Date()
                  }]);
                }}
                className="px-3 py-1.5 text-xs bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-md transition-colors ml-auto"
              >
                🔄 New Session
              </button>
            </>
          )}
        </div>

        {/* Voice + Message Input */}
        <div className="space-y-3">
          {/* Voice Input */}
          <VoiceInput 
            onTranscript={handleVoiceTranscript}
            disabled={!uploadedDoc || chatting}
          />
          
          {/* Text Input */}
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && handleSendMessage()}
              placeholder={uploadedDoc ? "Ask a question about your document..." : "Upload a PDF first..."}
              disabled={!uploadedDoc || chatting}
              className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white disabled:opacity-50 disabled:cursor-not-allowed"
            />
            <button
              onClick={() => handleSendMessage()}
              disabled={!input.trim() || !uploadedDoc || chatting}
              className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
            >
              {chatting ? '⏳' : '➤'} Send
            </button>
          </div>
        </div>
        
        <div className="mt-2 text-xs text-gray-500 dark:text-gray-400 text-center">
          🎤 Click mic to speak (transcript goes to textbox) • Edit if needed • Press Enter or click Send • Powered by Gemini 2.0 Flash + Deepgram + Pinecone
        </div>
      </div>
    </div>
  );
}
