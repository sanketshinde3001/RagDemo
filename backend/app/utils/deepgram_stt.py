"""
Deepgram Speech-to-Text Integration
Real-time transcription with WebSocket streaming
"""

from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    LiveTranscriptionEvents,
    LiveOptions,
)
from app.core.config import settings
import logging
from typing import Callable, Optional
import asyncio

logger = logging.getLogger(__name__)


class DeepgramTranscriber:
    """
    Handles real-time speech-to-text with Deepgram
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Deepgram client"""
        self.api_key = api_key or settings.DEEPGRAM_API_KEY
        if not self.api_key:
            raise ValueError("DEEPGRAM_API_KEY not configured")
        
        # Initialize Deepgram client
        config = DeepgramClientOptions(
            options={"keepalive": "true"}
        )
        self.deepgram = DeepgramClient(self.api_key, config)
        self.dg_connection = None
        self.is_connected = False
        self.loop = None  # Store event loop reference
        
        logger.info("Deepgram transcriber initialized")
    
    async def start_transcription(
        self,
        on_transcript: Callable,
        on_error: Optional[Callable] = None,
        language: str = "en",
        model: str = "nova-2",
        smart_format: bool = True
    ) -> bool:
        """
        Start real-time transcription
        """
        try:
            # Store the current event loop
            self.loop = asyncio.get_event_loop()
            
            # Get live transcription connection
            self.dg_connection = self.deepgram.listen.live.v("1")
            
            # Event handlers (non-async for v3.4.0)
            def on_open(self_inner, open_event, **kwargs):
                logger.info("✓ Deepgram connection opened")
                self.is_connected = True
                
            def on_message(self_inner, result, **kwargs):
                try:
                    sentence = result.channel.alternatives[0].transcript
                    
                    if len(sentence) == 0:
                        return
                    
                    is_final = result.is_final
                    
                    logger.info(f"Transcript ({'final' if is_final else 'interim'}): {sentence}")
                    
                    # Schedule async callback in the stored event loop
                    if self.loop and self.loop.is_running():
                        asyncio.run_coroutine_threadsafe(
                            on_transcript(sentence, is_final),
                            self.loop
                        )
                    else:
                        logger.error("Event loop not available")
                        
                except Exception as e:
                    logger.error(f"Error in message handler: {e}")
            
            def on_metadata(self_inner, metadata, **kwargs):
                logger.debug(f"Metadata: {metadata}")
            
            def on_speech_started(self_inner, speech_started, **kwargs):
                logger.info("🎤 Speech started")
            
            def on_utterance_end(self_inner, utterance_end, **kwargs):
                logger.info("🔇 Utterance ended")
            
            def on_close(self_inner, close_event, **kwargs):
                logger.info("Deepgram connection closed")
                self.is_connected = False
            
            def on_error_event(self_inner, error, **kwargs):
                error_msg = f"Deepgram error: {error}"
                logger.error(error_msg)
                if on_error and self.loop and self.loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        on_error(error_msg),
                        self.loop
                    )
            
            def on_unhandled(self_inner, unhandled, **kwargs):
                logger.debug(f"Unhandled event: {unhandled}")
            
            # Register event handlers
            self.dg_connection.on(LiveTranscriptionEvents.Open, on_open)
            self.dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
            self.dg_connection.on(LiveTranscriptionEvents.Metadata, on_metadata)
            self.dg_connection.on(LiveTranscriptionEvents.SpeechStarted, on_speech_started)
            self.dg_connection.on(LiveTranscriptionEvents.UtteranceEnd, on_utterance_end)
            self.dg_connection.on(LiveTranscriptionEvents.Close, on_close)
            self.dg_connection.on(LiveTranscriptionEvents.Error, on_error_event)
            self.dg_connection.on(LiveTranscriptionEvents.Unhandled, on_unhandled)
            
            # Configure transcription options
            options = LiveOptions(
                model=model,
                language=language,
                smart_format=smart_format,
                encoding="linear16",
                sample_rate=16000,
                channels=1,
                interim_results=True,
                punctuate=True,
                utterance_end_ms="1000",
                vad_events=True,
                endpointing=300
            )
            
            # Start connection (returns True on success)
            result = self.dg_connection.start(options)
            
            if result:
                self.is_connected = True
                logger.info("✓ Deepgram transcription started successfully")
                return True
            else:
                logger.error("❌ Failed to start Deepgram connection")
                return False
            
        except Exception as e:
            logger.error(f"❌ Error starting transcription: {e}")
            import traceback
            logger.error(traceback.format_exc())
            if on_error:
                asyncio.run_coroutine_threadsafe(on_error(str(e)), self.loop)
            return False
    
    async def send_audio(self, audio_data: bytes):
        """Send audio data to Deepgram"""
        try:
            if self.dg_connection and self.is_connected:
                self.dg_connection.send(audio_data)
            else:
                logger.warning("No active Deepgram connection")
        except Exception as e:
            logger.error(f"Error sending audio: {e}")
    
    async def stop_transcription(self):
        """Stop transcription and close connection"""
        try:
            if self.dg_connection:
                self.dg_connection.finish()
                self.dg_connection = None
                self.is_connected = False
                logger.info("✓ Deepgram transcription stopped")
        except Exception as e:
            logger.error(f"Error stopping transcription: {e}")
    
    def check_connection(self) -> bool:
        """Check if connection is active"""
        return self.is_connected


def create_deepgram_transcriber() -> DeepgramTranscriber:
    """Create new Deepgram transcriber instance"""
    return DeepgramTranscriber()
