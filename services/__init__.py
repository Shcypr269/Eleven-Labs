"""
CallPilot Services - India-First Agentic Swarm Architecture

This package provides the core services for the CallPilot voice AI system:
- State Machine: Call lifecycle management
- Swarm Orchestrator: Distributed parallel calling
- Exotel Service: India-compliant telephony (TRAI compliant)
- Deepgram Service: Hinglish speech-to-text
- Gnani.ai Service: Indian language TTS
- Voice Agent: LangChain + ElevenLabs AI agent
- Vision Service: OpenCV + OCR for provider images
- WebSocket Voice: Real-time audio streaming
- India Ranking: India-specific provider ranking
- Google API: Calendar and Maps integration
- Twilio Service: International phone connectivity
"""

from .state_machine import (
    CallState,
    CallEvent,
    CallStateMachine,
    CallContext,
    StateTransition,
    BookingResult,
)

from .swarm import (
    SwarmOrchestrator,
    SwarmCampaign,
    SwarmCallResult,
    ProviderTarget,
    CampaignStatus,
    CallStatus,
    DistributedLockManager,
    get_swarm_orchestrator,
)

from .voice_agent import (
    ElevenLabsVoiceAgent,
    HallucinationValidator,
    VoiceCallConfig,
)

from .exotel_service import (
    ExotelPhoneService,
    TRAIComplianceChecker,
    ExotelCall,
    get_exotel_service,
    get_dnd_checker,
)

from .deepgram_service import (
    DeepgramSTTService,
    GnaniAIService,
    TranscriptionResult,
    get_deepgram_service,
    get_gnani_service,
)

from .vision_service import (
    ProviderVisionService,
    OpenCVService,
    OCRService,
    BusinessHours,
    PriceListItem,
    ExtractedInfo,
    get_vision_service,
)

from .websocket_voice import (
    VoiceWebSocketHandler,
    StreamSession,
    ElevenLabsWebSocketClient,
    get_websocket_handler,
)

from .google_api import (
    GoogleCalendarService,
    OpenStreetMapService,
)

from .twilio_service import (
    TwilioPhoneService,
)

from .india_ranking import (
    IndiaRankingEngine,
    IndiaRankingConfig,
    MedicineAvailabilityChecker,
    rank_providers,
    UserPreferences,
)

__all__ = [
    # State Machine
    "CallState",
    "CallEvent",
    "CallStateMachine",
    "CallContext",
    "StateTransition",
    "BookingResult",
    # Swarm
    "SwarmOrchestrator",
    "SwarmCampaign",
    "SwarmCallResult",
    "ProviderTarget",
    "CampaignStatus",
    "CallStatus",
    "DistributedLockManager",
    "get_swarm_orchestrator",
    # Voice Agent
    "ElevenLabsVoiceAgent",
    "HallucinationValidator",
    "VoiceCallConfig",
    # Exotel (India)
    "ExotelPhoneService",
    "TRAIComplianceChecker",
    "ExotelCall",
    "get_exotel_service",
    "get_dnd_checker",
    # Deepgram (India STT)
    "DeepgramSTTService",
    "GnaniAIService",
    "TranscriptionResult",
    "get_deepgram_service",
    "get_gnani_service",
    # Vision
    "ProviderVisionService",
    "OpenCVService",
    "OCRService",
    "BusinessHours",
    "PriceListItem",
    "ExtractedInfo",
    "get_vision_service",
    # WebSocket
    "VoiceWebSocketHandler",
    "StreamSession",
    "ElevenLabsWebSocketClient",
    "get_websocket_handler",
    # Google API
    "GoogleCalendarService",
    "OpenStreetMapService",
    # Twilio
    "TwilioPhoneService",
    # India Ranking
    "IndiaRankingEngine",
    "IndiaRankingConfig",
    "MedicineAvailabilityChecker",
    "rank_providers",
    "UserPreferences",
]
