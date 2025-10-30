'use client';

import { useState, useRef, useEffect } from 'react';

interface VoiceInputProps {
  onTranscript: (text: string, isFinal: boolean) => void;
  disabled?: boolean;
}

// Get WebSocket URL from environment variable
const getWebSocketUrl = () => {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  // Convert HTTP(S) to WS(S) protocol
  const wsUrl = apiUrl.replace(/^http/, 'ws');
  return `${wsUrl}/api/v1/ws/transcribe`;
};

export default function VoiceInput({ onTranscript, disabled = false }: VoiceInputProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState('');
  const [wsSupported, setWsSupported] = useState(true);
  
  const wsRef = useRef<WebSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const startRecording = async () => {
    try {
      setIsConnecting(true);
      setError('');

      // Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
        } 
      });
      
      streamRef.current = stream;

      // Connect to WebSocket with dynamic URL
      const wsUrl = getWebSocketUrl();
      console.log('🔌 Connecting to WebSocket:', wsUrl);
      
      try {
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;
        
        // Connection timeout
        const connectionTimeout = setTimeout(() => {
          if (ws.readyState !== WebSocket.OPEN) {
            console.error('❌ WebSocket connection timeout');
            ws.close();
            setError('Connection timeout. Please try again.');
            setWsSupported(false);
            setIsConnecting(false);
            setIsRecording(false);
            stream.getTracks().forEach(track => track.stop());
          }
        }, 10000); // 10 second timeout

        ws.onopen = () => {
          clearTimeout(connectionTimeout);
          console.log('✓ WebSocket connected');
          setIsConnecting(false);
          setIsRecording(true);
          setWsSupported(true);
          setError('');

        // Create audio context for resampling
        const audioContext = new AudioContext({ sampleRate: 16000 });
        audioContextRef.current = audioContext;

        const source = audioContext.createMediaStreamSource(stream);
        const processor = audioContext.createScriptProcessor(4096, 1, 1);
        
        let audioChunksProcessed = 0;
        let lastSendTime = Date.now();

        processor.onaudioprocess = (e) => {
          if (ws.readyState === WebSocket.OPEN) {
            const inputData = e.inputBuffer.getChannelData(0);
            
            // Convert float32 to int16
            const int16Data = new Int16Array(inputData.length);
            for (let i = 0; i < inputData.length; i++) {
              const s = Math.max(-1, Math.min(1, inputData[i]));
              int16Data[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
            }
            
            // Send to backend with error handling
            try {
              ws.send(int16Data.buffer);
              audioChunksProcessed++;
              
              // Log progress every 5 seconds
              const now = Date.now();
              if (now - lastSendTime > 5000) {
                console.log(`📊 Audio streaming: ${audioChunksProcessed} chunks sent`);
                lastSendTime = now;
              }
            } catch (sendError) {
              console.error('Failed to send audio chunk:', sendError);
              setError('Audio streaming interrupted');
              stopRecording();
            }
          } else if (ws.readyState === WebSocket.CLOSED) {
            console.warn('⚠️  WebSocket closed, stopping audio processing');
            stopRecording();
          }
        };

        source.connect(processor);
        processor.connect(audioContext.destination);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
        
        if (data.type === 'transcript') {
          console.log(`📝 Transcript (${data.is_final ? 'FINAL' : 'interim'}):`, data.text);
          
          // Only send final transcripts to parent (skip interim for cleaner UX)
          if (data.is_final) {
            onTranscript(data.text.trim(), true);
            console.log('✅ Final transcript sent to input box');
          }
          // Note: Interim transcripts are logged but not displayed
        } else if (data.type === 'error') {
          console.error('❌ Transcription error:', data.message);
          setError(data.message);
          stopRecording();
        } else if (data.type === 'ready') {
          console.log('✅ Transcription service ready');
          } else if (data.type === 'pong') {
            console.log('💓 Pong received - connection alive');
          }
        } catch (parseError) {
          console.error('Failed to parse WebSocket message:', parseError);
        }
      };

      ws.onerror = (error) => {
        clearTimeout(connectionTimeout);
        console.error('❌ WebSocket error:', error);
        setError('WebSocket not supported on this platform. Voice input disabled.');
        setWsSupported(false);
        stopRecording();
      };

      ws.onclose = (event) => {
        clearTimeout(connectionTimeout);
        console.log(`🔌 WebSocket closed (code: ${event.code}, reason: ${event.reason || 'none'})`);
        
        if (!event.wasClean) {
          console.warn('⚠️  Connection closed unexpectedly');
          setError('Connection lost. Please try again.');
        }
        
        stopRecording();
      };
      
      } catch (wsError) {
        console.error('WebSocket connection failed:', wsError);
        setError('Voice input not available (WebSocket not supported on serverless platforms)');
        setWsSupported(false);
        setIsConnecting(false);
        setIsRecording(false);
        // Clean up stream
        if (stream) {
          stream.getTracks().forEach(track => track.stop());
        }
        return;
      }

    } catch (err) {
      console.error('Error starting recording:', err);
      setError(err instanceof Error ? err.message : 'Failed to start recording');
      setIsConnecting(false);
      setIsRecording(false);
    }
  };

  const stopRecording = () => {
    // Stop all audio tracks
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }

    // Close audio context
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }

    // Stop media recorder
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current = null;
    }

    // Close WebSocket
    if (wsRef.current) {
      if (wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ command: 'stop' }));
        wsRef.current.close();
      }
      wsRef.current = null;
    }

    setIsRecording(false);
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopRecording();
    };
  }, []);

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={isRecording ? stopRecording : startRecording}
        disabled={disabled || isConnecting || !wsSupported}
        className={`p-3 rounded-lg transition-all shadow-sm flex-shrink-0 ${
          !wsSupported
            ? 'bg-gray-400 cursor-not-allowed'
            : isRecording
            ? 'bg-red-600 hover:bg-red-700 animate-pulse'
            : isConnecting
            ? 'bg-gray-400 cursor-wait'
            : 'bg-blue-600 hover:bg-blue-700'
        } text-white disabled:opacity-50 disabled:cursor-not-allowed`}
        title={
          !wsSupported 
            ? 'Voice input not available (deploy backend with WebSocket support)' 
            : isRecording 
            ? 'Stop recording' 
            : 'Start voice input'
        }
      >
        {isConnecting ? (
          <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
        ) : isRecording ? (
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
            <rect x="6" y="6" width="12" height="12" rx="2" />
          </svg>
        ) : (
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
            <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
          </svg>
        )}
      </button>

      {/* Error display - Only show errors */}
      {error && !isRecording && (
        <div className="absolute left-16 px-3 py-1.5 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-xs text-red-700 dark:text-red-300 font-medium shadow-lg z-10 max-w-xs">
          ⚠️ {error}
        </div>
      )}
    </div>
  );
}
