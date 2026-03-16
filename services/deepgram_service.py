"""
Deepgram Speech-to-Text Service
Optimized for Indian accents and Hinglish (Hindi + English code-switching)
Better than Whisper for Indian languages
"""
import os
import aiohttp
import base64
import json
from typing import Optional, Dict, Any, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TranscriptionResult:
    """Transcription result from Deepgram"""
    transcript: str
    language: str = "en-IN"
    confidence: float = 0.0
    duration: float = 0.0
    words: list = field(default_factory=list)
    is_final: bool = True


class DeepgramSTTService:
    """
    Deepgram Speech-to-Text for Indian Languages
    
    Features:
    - Nova-3 model: Enhanced India accent support
    - Hinglish code-switching detection
    - Real-time streaming transcription
    - < 300ms latency
    """
    
    # Supported Indian languages
    LANGUAGES = {
        "en-IN": "English (India)",
        "hi": "Hindi",
        "hi-Latn": "Hindi (Latin script)",
        "ta": "Tamil",
        "te": "Telugu",
        "kn": "Kannada",
        "ml": "Malayalam",
        "mr": "Marathi",
        "gu": "Gujarati",
        "bn": "Bengali",
        "pa": "Punjabi",
        "or": "Odia",
    }
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("DEEPGRAM_API_KEY")
        self._mock_mode = not self.api_key
        
        # Default to India-optimized model
        self.model = "nova-3"  # Best for Indian accents
        self.smart_format = True
        self.interim_results = True
        
        if self._mock_mode:
            print("⚠️ Deepgram API key not found - running in MOCK mode")
            print("   Get credentials: https://console.deepgram.com/")
        else:
            print(f"✅ Deepgram STT initialized (Model: {self.model})")
    
    async def transcribe(
        self,
        audio_data: bytes,
        language: str = "en-IN",
        sample_rate: int = 24000
    ) -> TranscriptionResult:
        """
        Transcribe audio file/buffer
        
        Args:
            audio_data: Raw PCM audio data (16-bit, mono)
            language: Language code (default: en-IN for Indian English)
            sample_rate: Audio sample rate in Hz
        """
        if self._mock_mode:
            return self._mock_transcribe(audio_data)
        
        url = "https://api.deepgram.com/v1/listen"
        params = {
            "model": self.model,
            "language": language,
            "smart_format": str(self.smart_format).lower(),
            "interim_results": str(self.interim_results).lower(),
            "encoding": "linear16",
            "sample_rate": str(sample_rate),
            "punctuate": "true",
            "profanity_filter": "true",
            "diarize": "false"
        }
        
        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "audio/*"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    params=params,
                    headers=headers,
                    data=audio_data
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_response(data)
                    else:
                        error = await response.text()
                        raise Exception(f"Deepgram API error: {response.status} - {error}")
                        
        except Exception as e:
            print(f"❌ Deepgram transcription failed: {e}")
            return self._mock_transcribe(audio_data)
    
    def _parse_response(self, data: Dict[str, Any]) -> TranscriptionResult:
        """Parse Deepgram API response"""
        result = data.get("results", {})
        channels = result.get("channels", [])
        
        if not channels:
            return TranscriptionResult(
                transcript="",
                language="en-IN",
                confidence=0.0
            )
        
        channel = channels[0]
        alternatives = channel.get("alternatives", [])
        
        if not alternatives:
            return TranscriptionResult(
                transcript="",
                language="en-IN",
                confidence=0.0
            )
        
        best = alternatives[0]
        
        return TranscriptionResult(
            transcript=best.get("transcript", ""),
            language="en-IN",
            confidence=best.get("confidence", 0.0),
            duration=result.get("duration", 0.0),
            words=best.get("words", []),
            is_final=True
        )
    
    def _mock_transcribe(self, audio_data: bytes) -> TranscriptionResult:
        """Mock transcription for testing"""
        # In mock mode, return placeholder
        return TranscriptionResult(
            transcript="[Mock transcription - Configure Deepgram API for real STT]",
            language="en-IN",
            confidence=0.95,
            duration=len(audio_data) / (24000 * 2)  # Estimate duration
        )
    
    async def transcribe_stream(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        language: str = "en-IN",
        sample_rate: int = 24000
    ) -> AsyncGenerator[TranscriptionResult, None]:
        """
        Real-time streaming transcription
        
        Yields interim results as they become available
        """
        if self._mock_mode:
            async for chunk in audio_stream:
                yield self._mock_transcribe(chunk)
            return
        
        url = "https://api.deepgram.com/v1/listen"
        params = {
            "model": self.model,
            "language": language,
            "smart_format": str(self.smart_format).lower(),
            "interim_results": "true",
            "encoding": "linear16",
            "sample_rate": str(sample_rate),
            "punctuate": "true",
            "vad_events": "true",
            "endpointing": 300  # 300ms silence = end of utterance
        }
        
        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "audio/*"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(
                    url,
                    params=params,
                    headers=headers
                ) as ws:
                    # Send audio chunks
                    async for chunk in audio_stream:
                        await ws.send_bytes(chunk)
                    
                    # Close sender
                    await ws.close()
                    
                    # Receive results
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            result = self._parse_stream_response(data)
                            if result:
                                yield result
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            break
                            
        except Exception as e:
            print(f"❌ Deepgram streaming failed: {e}")
    
    def _parse_stream_response(self, data: Dict[str, Any]) -> Optional[TranscriptionResult]:
        """Parse streaming response"""
        if data.get("type") == "Results":
            result = data.get("channel", {})
            alternatives = result.get("alternatives", [])
            
            if alternatives:
                best = alternatives[0]
                return TranscriptionResult(
                    transcript=best.get("transcript", ""),
                    language="en-IN",
                    confidence=best.get("confidence", 0.0),
                    is_final=data.get("is_final", False)
                )
        
        return None
    
    def detect_language(self, text: str) -> str:
        """
        Detect if text is Hindi, English, or Hinglish
        
        Simple heuristic based on Devanagari characters
        """
        # Check for Devanagari script (Hindi)
        devanagari_chars = sum(1 for c in text if '\u0900' <= c <= '\u097F')
        
        if devanagari_chars > len(text) * 0.3:
            return "hi"  # Hindi
        elif devanagari_chars > 0:
            return "hi-Latn"  # Hinglish (mixed)
        else:
            return "en-IN"  # Indian English


class GnaniAIService:
    """
    Gnani.ai - India-First Voice AI Platform
    
    Alternative to ElevenLabs with better Indian language support
    - Natural Hindi voices
    - Indian English accents
    - Lower latency for India
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GNANI_API_KEY")
        self._mock_mode = not self.api_key
        
        # Indian voice options
        self.voices = {
            "en-IN": ["ananya", "arjun", "priya"],
            "hi": ["ananya-hindi", "amit", "priya-hindi"],
            "hi-Latn": ["ananya", "amit"],
            "ta": ["tamil-female", "tamil-male"],
            "te": ["telugu-female", "telugu-male"],
        }
        
        if self._mock_mode:
            print("⚠️ Gnani.ai API key not found - running in MOCK mode")
            print("   Get credentials: https://gnani.ai/")
        else:
            print("✅ Gnani.ai TTS initialized")
    
    async def text_to_speech(
        self,
        text: str,
        voice: str = "ananya",
        language: str = "en-IN",
        speed: float = 1.0,
        pitch: float = 1.0
    ) -> bytes:
        """
        Convert text to speech with Indian voice
        
        Args:
            text: Text to synthesize
            voice: Voice name (from self.voices)
            language: Language code
            speed: Speech speed (0.5 - 2.0)
            pitch: Pitch (0.5 - 2.0)
        """
        if self._mock_mode:
            return b""  # Mock: return empty audio
        
        url = "https://apiservices.gnani.ai/synthesize"
        
        payload = {
            "text": text,
            "voice": voice,
            "language": language,
            "speed": speed,
            "pitch": pitch,
            "output_format": "pcm"
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        return await response.read()
                    else:
                        error = await response.text()
                        raise Exception(f"Gnani.ai error: {response.status}")
                        
        except Exception as e:
            print(f"❌ Gnani.ai TTS failed: {e}")
            return b""


# Singleton instances
_deepgram_service: Optional[DeepgramSTTService] = None
_gnani_service: Optional[GnaniAIService] = None


def get_deepgram_service() -> DeepgramSTTService:
    """Get or create Deepgram service singleton"""
    global _deepgram_service
    if _deepgram_service is None:
        _deepgram_service = DeepgramSTTService()
    return _deepgram_service


def get_gnani_service() -> GnaniAIService:
    """Get or create Gnani.ai service singleton"""
    global _gnani_service
    if _gnani_service is None:
        _gnani_service = GnaniAIService()
    return _gnani_service
