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
  const [transcript, setTranscript] = useState('');
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
      setTranscript('');

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

        ws.onopen = () => {
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

        processor.onaudioprocess = (e) => {
          if (ws.readyState === WebSocket.OPEN) {
            const inputData = e.inputBuffer.getChannelData(0);
            
            // Convert float32 to int16
            const int16Data = new Int16Array(inputData.length);
            for (let i = 0; i < inputData.length; i++) {
              const s = Math.max(-1, Math.min(1, inputData[i]));
              int16Data[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
            }
            
            // Send to backend
            ws.send(int16Data.buffer);
          }
        };

        source.connect(processor);
        processor.connect(audioContext.destination);
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === 'transcript') {
          console.log(`Transcript (${data.is_final ? 'final' : 'interim'}):`, data.text);
          
          // Always call callback with text and final status
          // This allows parent to decide what to do with interim vs final
          onTranscript(data.text.trim(), data.is_final);
          
          // Show transcript in component (for visual feedback)
          if (!data.is_final) {
            setTranscript(data.text);
          } else {
            // Clear after final (parent will handle it)
            setTranscript('');
          }
        } else if (data.type === 'error') {
          console.error('Transcription error:', data.message);
          setError(data.message);
        } else if (data.type === 'ready') {
          console.log('Transcription service ready');
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setError('WebSocket not supported on this platform. Voice input disabled.');
        setWsSupported(false);
        stopRecording();
      };

      ws.onclose = () => {
        console.log('WebSocket closed');
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
    setTranscript('');
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
        className={`p-3 rounded-lg transition-all shadow-sm ${
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

      {/* Live transcript display */}
      {transcript && (
        <div className="flex-1 px-4 py-2 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg text-sm text-gray-700 dark:text-gray-300 font-medium">
          <span className="text-blue-600 dark:text-blue-400 font-semibold mr-2">Listening...</span>
          {transcript}
        </div>
      )}

      {/* Error display */}
      {error && (
        <div className="flex-1 px-4 py-2 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-300 font-medium">
          Error: {error}
        </div>
      )}
    </div>
  );
}
