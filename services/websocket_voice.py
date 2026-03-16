"""
WebSocket Voice Streaming Service
Implements full-duplex audio streaming for low-latency voice calls
"""
import asyncio
import json
import base64
from typing import Optional, Dict, Any, Callable
from datetime import datetime
from dataclasses import dataclass, field
import websockets
from websockets.server import WebSocketServerProtocol


@dataclass
class AudioChunk:
    """Audio chunk for streaming"""
    data: bytes
    sample_rate: int = 24000
    channels: int = 1
    bit_depth: int = 16
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class StreamSession:
    """Represents an active WebSocket streaming session"""
    session_id: str
    websocket: WebSocketServerProtocol
    call_sid: Optional[str] = None
    provider_id: Optional[str] = None
    user_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    is_active: bool = True
    audio_buffer: asyncio.Queue = field(default_factory=asyncio.Queue)
    
    async def send_audio(self, audio_data: bytes):
        """Send audio chunk to client"""
        message = {
            "type": "audio",
            "data": base64.b64encode(audio_data).decode('utf-8'),
            "sample_rate": 24000,
            "timestamp": datetime.now().isoformat()
        }
        await self.websocket.send(json.dumps(message))
        self.last_activity = datetime.now()
    
    async def receive_audio(self) -> Optional[bytes]:
        """Receive audio chunk from client"""
        try:
            message = await asyncio.wait_for(
                self.websocket.recv(),
                timeout=5.0
            )
            data = json.loads(message)
            if data.get("type") == "audio":
                self.last_activity = datetime.now()
                return base64.b64decode(data["data"])
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            print(f"Error receiving audio: {e}")
        return None
    
    async def send_text(self, text: str):
        """Send text message (e.g., transcription) to client"""
        message = {
            "type": "text",
            "text": text,
            "timestamp": datetime.now().isoformat()
        }
        await self.websocket.send(json.dumps(message))
    
    async def send_event(self, event: str, data: Dict[str, Any]):
        """Send event message to client"""
        message = {
            "type": "event",
            "event": event,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        await self.websocket.send(json.dumps(message))


class VoiceWebSocketHandler:
    """
    WebSocket handler for real-time voice streaming
    Implements stream-to-stream processing for < 500ms latency
    """
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self.host = host
        self.port = port
        self.sessions: Dict[str, StreamSession] = {}
        self.elevenlabs_api_key: Optional[str] = None
        self._server = None
        self._running = False
    
    async def start(self):
        """Start WebSocket server"""
        self._server = await websockets.serve(
            self._handle_connection,
            self.host,
            self.port,
            subprotocols=["audio"],
            ping_interval=30,
            ping_timeout=10
        )
        self._running = True
        print(f"✅ Voice WebSocket server started on ws://{self.host}:{self.port}")
    
    async def stop(self):
        """Stop WebSocket server"""
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        print("✅ Voice WebSocket server stopped")
    
    async def _handle_connection(self, websocket: WebSocketServerProtocol, path: str):
        """Handle new WebSocket connection"""
        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{id(websocket)}"
        session = StreamSession(session_id=session_id, websocket=websocket)
        
        self.sessions[session_id] = session
        print(f"📞 New WebSocket connection: {session_id}")
        
        try:
            # Send connection acknowledgment
            await session.send_event("connected", {
                "session_id": session_id,
                "sample_rate": 24000,
                "format": "pcm_s16le"
            })
            
            # Start bidirectional streaming
            await self._stream_audio(session)
            
        except websockets.exceptions.ConnectionClosed:
            print(f"📞 WebSocket connection closed: {session_id}")
        except Exception as e:
            print(f"❌ WebSocket error: {e}")
        finally:
            # Cleanup
            session.is_active = False
            del self.sessions[session_id]
            print(f"📞 Session cleaned up: {session_id}")
    
    async def _stream_audio(self, session: StreamSession):
        """
        Bidirectional audio streaming loop
        
        Implements full-duplex processing:
        - Receive audio from provider (via Twilio)
        - Send to ElevenLabs for transcription
        - Process with AI agent
        - Send response audio back via ElevenLabs TTS
        """
        from .voice_agent import ElevenLabsVoiceAgent
        
        voice_agent = ElevenLabsVoiceAgent()
        
        # Create tasks for concurrent send/receive
        receive_task = asyncio.create_task(self._receive_loop(session, voice_agent))
        send_task = asyncio.create_task(self._send_loop(session))
        
        # Wait for either task to complete (connection closed)
        done, pending = await asyncio.wait(
            [receive_task, send_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Cancel pending tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    
    async def _receive_loop(
        self,
        session: StreamSession,
        voice_agent: "ElevenLabsVoiceAgent"
    ):
        """Receive and process incoming audio"""
        audio_buffer = bytearray()
        buffer_duration = 0.5  # 500ms chunks
        
        while session.is_active:
            try:
                # Receive audio chunk
                audio_data = await session.receive_audio()
                if audio_data:
                    audio_buffer.extend(audio_data)
                    
                    # Process when buffer has enough data
                    if len(audio_buffer) >= int(24000 * 2 * buffer_duration):
                        # Send to transcription service
                        # In production: call ElevenLabs speech-to-text
                        transcript = await self._transcribe_audio(bytes(audio_buffer))
                        
                        if transcript:
                            # Process with AI agent
                            response = await voice_agent.process_response(
                                ctx=None,  # Would pass call context
                                user_input=transcript
                            )
                            
                            # Queue response for sending
                            # In production: generate TTS and send
                            await session.send_text(f"AI: {response}")
                        
                        # Clear buffer
                        audio_buffer.clear()
                        
            except Exception as e:
                if session.is_active:
                    print(f"Receive loop error: {e}")
                break
    
    async def _send_loop(self, session: StreamSession):
        """Send outgoing audio from queue"""
        while session.is_active:
            try:
                # Get audio from queue (with timeout)
                try:
                    audio_data = await asyncio.wait_for(
                        session.audio_buffer.get(),
                        timeout=1.0
                    )
                    await session.send_audio(audio_data)
                except asyncio.TimeoutError:
                    pass
                    
            except Exception as e:
                if session.is_active:
                    print(f"Send loop error: {e}")
                break
    
    async def _transcribe_audio(self, audio_data: bytes) -> Optional[str]:
        """
        Transcribe audio using ElevenLabs or other STT service
        
        In production, this would call ElevenLabs speech-to-text API
        """
        # Placeholder - in production, call actual STT service
        return None
    
    async def broadcast_to_call(self, call_sid: str, audio_data: bytes):
        """Broadcast audio to all sessions in a call"""
        for session in self.sessions.values():
            if session.call_sid == call_sid and session.is_active:
                await session.audio_buffer.put(audio_data)
    
    def get_active_sessions(self) -> int:
        """Get count of active sessions"""
        return sum(1 for s in self.sessions.values() if s.is_active)


class ElevenLabsWebSocketClient:
    """
    Client for ElevenLabs WebSocket streaming API
    Handles real-time TTS streaming
    """
    
    def __init__(self, api_key: str, voice_id: str = "Rachel"):
        self.api_key = api_key
        self.voice_id = voice_id
        self.websocket: Optional[WebSocketServerProtocol] = None
        self._connected = False
    
    async def connect(self):
        """Connect to ElevenLabs WebSocket API"""
        url = f"wss://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}/stream"
        
        self.websocket = await websockets.connect(
            url,
            additional_headers={
                "xi-api-key": self.api_key
            }
        )
        self._connected = True
        
        # Send initial configuration
        config = {
            "text": " ",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            },
            "generation_config": {
                "chunk_length_schedule": [80, 120, 200, 260]
            }
        }
        await self.websocket.send(json.dumps(config))
        
        print("✅ Connected to ElevenLabs WebSocket")
    
    async def disconnect(self):
        """Disconnect from ElevenLabs"""
        if self.websocket:
            await self.websocket.close()
        self._connected = False
    
    async def send_text(self, text: str):
        """Send text for streaming TTS"""
        if not self._connected:
            raise RuntimeError("Not connected to ElevenLabs")
        
        message = {
            "text": text,
            "try_trigger_generation": True
        }
        await self.websocket.send(json.dumps(message))
    
    async def receive_audio(self) -> Optional[bytes]:
        """Receive generated audio chunk"""
        if not self._connected:
            return None
        
        try:
            message = await asyncio.wait_for(
                self.websocket.recv(),
                timeout=1.0
            )
            data = json.loads(message)
            
            if "audio" in data:
                return base64.b64decode(data["audio"])
        except asyncio.TimeoutError:
            pass
        
        return None
    
    async def stream(self, text: str):
        """Stream text and yield audio chunks"""
        await self.send_text(text)
        
        while True:
            audio = await self.receive_audio()
            if audio:
                yield audio
            else:
                # Check if generation is complete
                break


# Singleton instance
_websocket_handler: Optional[VoiceWebSocketHandler] = None


def get_websocket_handler(host: str = "0.0.0.0", port: int = 8765) -> VoiceWebSocketHandler:
    """Get or create WebSocket handler singleton"""
    global _websocket_handler
    if _websocket_handler is None:
        _websocket_handler = VoiceWebSocketHandler(host=host, port=port)
    return _websocket_handler
