import os
import asyncio
import uuid
import math
import requests
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from fastapi import FastAPI, HTTPException, BackgroundTasks, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Import from services package
from services import (
    # State Machine
    CallStateMachine,
    CallState,
    CallEvent,
    CallContext,
    # Swarm
    SwarmOrchestrator,
    SwarmCampaign,
    get_swarm_orchestrator,
    # Voice Agent
    ElevenLabsVoiceAgent,
    HallucinationValidator,
    # Vision
    get_vision_service,
    # WebSocket
    get_websocket_handler,
    # Google API
    GoogleCalendarService,
    OpenStreetMapService,
    # Twilio
    TwilioPhoneService,
    # Ranking
    rank_providers,
    UserPreferences,
)

try:
    from twilio.rest import Client
    from twilio.twiml.voice_response import VoiceResponse
except:
    Client = None
    VoiceResponse = None


# ============================================================================
# Request/Response Models
# ============================================================================

class BookingRequest(BaseModel):
    service_type: str
    location: str
    time_preference: str = "afternoon"
    max_budget: Optional[float] = None
    user_name: str = "User"


class SwarmRequest(BaseModel):
    service_type: str
    location: str
    time_preference: str = "afternoon"
    max_budget: Optional[float] = None
    max_providers: int = 5
    user_name: str = "User"


class VoiceCallRequest(BaseModel):
    provider_phone: str
    provider_name: str
    service_type: str
    user_name: str = "User"


class VisionExtractRequest(BaseModel):
    image_url: str
    extract_type: str = "all"  # all, business_hours, price_list, contact


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    services: Dict[str, bool]


# ============================================================================
# Application State
# ============================================================================

class AppState:
    def __init__(self):
        self.twilio: Optional[TwilioPhoneService] = None
        self.calendar: Optional[GoogleCalendarService] = None
        self.places: Optional[OpenStreetMapService] = None
        self.swarm: Optional[SwarmOrchestrator] = None
        self.voice_agent: Optional[ElevenLabsVoiceAgent] = None
        self.validator: Optional[HallucinationValidator] = None
        self.vision: Optional = None
        self.websocket: Optional = None
        self.redis_initialized: bool = False


app_state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup"""
    print("🚀 Initializing CallPilot Agentic Swarm...")
    
    # Initialize Twilio
    app_state.twilio = TwilioPhoneService()
    print(f"✅ Twilio: {'Connected' if app_state.twilio.client else 'Mock Mode'}")
    
    # Initialize Google Calendar
    app_state.calendar = GoogleCalendarService()
    print("✅ Google Calendar initialized")
    
    # Initialize OpenStreetMap
    app_state.places = OpenStreetMapService()
    print("✅ OpenStreetMap initialized")
    
    # Initialize Swarm Orchestrator (with Redis if available)
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    app_state.swarm = get_swarm_orchestrator(redis_url=redis_url)
    try:
        await app_state.swarm.initialize()
        app_state.redis_initialized = True
        print(f"✅ Swarm Orchestrator connected to Redis")
    except Exception as e:
        print(f"⚠️ Redis not available, using in-memory swarm: {e}")
        app_state.redis_initialized = False
    
    # Initialize Voice Agent
    app_state.voice_agent = ElevenLabsVoiceAgent()
    print(f"✅ Voice Agent: {'Connected' if app_state.voice_agent.api_key else 'Mock Mode'}")
    
    # Initialize Hallucination Validator
    app_state.validator = HallucinationValidator()
    print("✅ Hallucination Validator initialized")
    
    # Initialize Vision Service
    tessdata_path = os.getenv("TESSDATA_PATH")
    app_state.vision = get_vision_service(tessdata_path=tessdata_path)
    print("✅ Vision Service initialized")
    
    # Initialize WebSocket Handler (optional)
    if os.getenv("ENABLE_WEBSOCKET", "false").lower() == "true":
        app_state.websocket = get_websocket_handler(port=8765)
        asyncio.create_task(app_state.websocket.start())
        print("✅ WebSocket Voice Streaming enabled")
    
    yield
    
    # Cleanup on shutdown
    print("\n🛑 Shutting down CallPilot...")
    if app_state.swarm:
        await app_state.swarm.close()
    if app_state.websocket:
        await app_state.websocket.stop()


app = FastAPI(
    title="CallPilot - Agentic Swarm",
    description="Production-grade Voice AI Appointment Scheduler with Distributed Swarm Architecture",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Core Endpoints
# ============================================================================

@app.get("/", response_model=HealthResponse)
def home():
    """Health check endpoint"""
    return HealthResponse(
        status="online",
        app="CallPilot - Agentic Swarm",
        version="2.0.0",
        services={
            "twilio": app_state.twilio is not None,
            "swarm": app_state.swarm is not None,
            "voice_agent": app_state.voice_agent is not None,
            "redis": app_state.redis_initialized,
            "websocket": app_state.websocket is not None,
        }
    )


@app.get("/places/search")
def search_places(service_type: str, location: str):
    """Search for service providers near a location"""
    results = app_state.places.search_nearby(location, service_type)
    return {
        "count": len(results),
        "location": location,
        "service_type": service_type,
        "providers": results
    }


@app.get("/places/details/{place_id}")
def get_place_details(place_id: str):
    """Get detailed information about a provider"""
    details = app_state.places.get_place_details(place_id)
    if details:
        return {"place_id": place_id, "details": details}
    raise HTTPException(status_code=404, detail="Provider not found")


@app.post("/book")
async def book_appointment(req: BookingRequest):
    """
    Book an appointment with intelligent provider selection
    
    This endpoint:
    1. Searches for providers matching criteria
    2. Ranks providers based on rating, distance, price
    3. Checks calendar availability
    4. Initiates voice call to best provider
    """
    # Search providers
    providers = app_state.places.search_nearby(req.location, req.service_type)
    if not providers:
        return {
            "success": False,
            "message": f"No {req.service_type} providers found in {req.location}"
        }
    
    # Filter by budget
    if req.max_budget:
        providers = [p for p in providers if p.get("price_range", 0) <= req.max_budget]
        if not providers:
            return {"success": False, "message": "No providers within budget"}
    
    # Rank providers
    ranked = rank_providers(
        providers,
        req.location,
        req.time_preference,
        req.max_budget,
        UserPreferences(
            time_preference=req.time_preference,
            max_budget=req.max_budget
        )
    )
    
    # Get available slots
    slots = app_state.calendar.find_available_slots(req.time_preference)
    if not ranked or not slots:
        return {"success": False, "message": "No available options"}
    
    # Initiate voice call to best provider
    best = ranked[0]
    voice_result = await app_state.voice_agent.initiate_call(
        CallContext(
            call_id=str(uuid.uuid4()),
            provider_id=str(best.get("id", "")),
            provider_name=best["name"],
            provider_phone=best["phone"],
            service_type=req.service_type,
            user_name=req.user_name,
            user_id="user_001",
            preferred_times=[req.time_preference],
            max_budget=best.get("price_range", 0)
        )
    )
    
    if voice_result.success:
        return {
            "success": True,
            "provider": best["name"],
            "time": f"{slots[0]['date_str']} at {slots[0]['time_str']}",
            "price": best.get("price_range", 0),
            "rating": best.get("rating", 0),
            "address": best.get("address", ""),
            "phone": best.get("phone", ""),
            "booking_details": {
                "date": voice_result.appointment_date,
                "time": voice_result.appointment_time,
                "price": voice_result.price_quoted
            }
        }
    
    return {
        "success": False,
        "message": "Failed to confirm appointment with provider"
    }


# ============================================================================
# Swarm Mode Endpoints
# ============================================================================

@app.post("/swarm")
async def start_swarm(req: SwarmRequest, background_tasks: BackgroundTasks):
    """
    Start a swarm campaign - call multiple providers simultaneously
    
    This is the core "Agentic Swarm" feature that parallelizes provider calls
    using distributed state management and locking.
    """
    # Search providers
    providers = app_state.places.search_nearby(req.location, req.service_type)
    if not providers:
        raise HTTPException(status_code=404, detail="No providers found")
    
    # Filter by budget
    if req.max_budget:
        providers = [p for p in providers if p.get("price_range", 0) <= req.max_budget]
    
    if not providers:
        raise HTTPException(status_code=400, detail="No providers within budget")
    
    # Create campaign
    campaign = app_state.swarm.create_campaign(
        user_id="user_001",
        service_type=req.service_type,
        location=req.location,
        time_preference=req.time_preference,
        max_budget=req.max_budget,
        providers=providers,
        max_providers=req.max_providers
    )
    
    # Execute swarm in background
    async def run_swarm():
        await app_state.swarm.execute_swarm(
            campaign_id=campaign.campaign_id,
            user_name=req.user_name
        )
    
    background_tasks.add_task(run_swarm)
    
    return {
        "campaign_id": campaign.campaign_id,
        "status": "initiated",
        "targets": len(campaign.targets),
        "message": f"Swarm campaign started with {len(campaign.targets)} providers"
    }


@app.get("/swarm/{campaign_id}")
async def get_swarm_status(campaign_id: str):
    """Get real-time status of a swarm campaign"""
    campaign = await app_state.swarm.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    stats = await app_state.swarm.get_campaign_stats(campaign_id)
    
    return {
        **stats,
        "campaign": campaign.to_dict()
    }


@app.get("/swarm/{campaign_id}/results")
async def get_swarm_results(campaign_id: str):
    """Get detailed results of completed swarm campaign"""
    campaign = await app_state.swarm.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    return {
        "campaign_id": campaign_id,
        "status": campaign.status.value,
        "best_booking": {
            "provider_name": campaign.best_booking.provider_name,
            "appointment": campaign.best_booking.booking_result
        } if campaign.best_booking else None,
        "all_results": [
            {
                "provider_id": r.provider_id,
                "provider_name": r.provider_name,
                "status": r.status.value,
                "success": r.success,
                "booking": r.booking_result,
                "error": r.error_message,
                "duration": r.call_duration
            }
            for r in campaign.results.values()
        ]
    }


# ============================================================================
# Voice Call Endpoints
# ============================================================================

@app.post("/voice/call")
async def voice_call(
    provider_phone: str,
    provider_name: str,
    service_type: str,
    user_name: str = "User"
):
    """Initiate a voice call to a provider"""
    result = await app_state.voice_agent.initiate_call(
        CallContext(
            call_id=str(uuid.uuid4()),
            provider_id=str(uuid.uuid4()),
            provider_name=provider_name,
            provider_phone=provider_phone,
            service_type=service_type,
            user_name=user_name,
            user_id="user_001"
        )
    )
    
    return {
        "success": result.success,
        "provider": result.provider_name,
        "appointment_date": result.appointment_date,
        "appointment_time": result.appointment_time,
        "price": result.price_quoted
    }


@app.websocket("/ws/voice")
async def websocket_voice(websocket: WebSocket):
    """
    WebSocket endpoint for real-time voice streaming
    
    Implements full-duplex audio for < 500ms latency
    """
    await websocket.accept()
    session_id = str(uuid.uuid4())
    
    try:
        # Send connection acknowledgment
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id
        })
        
        # Handle bidirectional audio streaming
        while True:
            data = await websocket.receive_json()
            
            if data.get("type") == "audio":
                # Process incoming audio
                # In production: transcribe and respond
                await websocket.send_json({
                    "type": "ack",
                    "status": "processing"
                })
                
    except WebSocketDisconnect:
        print(f"📞 WebSocket disconnected: {session_id}")
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })


# ============================================================================
# Vision/OCR Endpoints
# ============================================================================

@app.post("/vision/extract")
async def vision_extract(req: VisionExtractRequest):
    """
    Extract information from provider images using OpenCV + OCR
    
    Can extract:
    - Business hours
    - Price lists
    - Contact information
    """
    info = app_state.vision.extract_from_url(req.image_url)
    
    result = {
        "raw_text": info.raw_text,
        "confidence": info.confidence
    }
    
    if req.extract_type in ["all", "business_hours"] and info.business_hours:
        result["business_hours"] = info.business_hours.to_dict()
    
    if req.extract_type in ["all", "contact"]:
        result["contact"] = {
            "phone": info.phone_number,
            "email": info.email,
            "website": info.website,
            "address": info.address
        }
    
    if req.extract_type in ["all", "price_list"]:
        result["price_list"] = [
            {
                "service": item.service_name,
                "price": item.price,
                "currency": item.currency
            }
            for item in info.price_list
        ]
    
    return result


# ============================================================================
# Call Management Endpoints
# ============================================================================

@app.get("/calls/history")
def get_call_history():
    """Get recent call history"""
    if app_state.twilio:
        calls = list(app_state.twilio.active_calls.values())[-10:]
        return {"calls": calls}
    return {"calls": []}


@app.post("/calls/twiml")
def handle_twiml():
    """Handle Twilio webhook for call control"""
    if VoiceResponse:
        response = VoiceResponse()
        response.say(
            "Thank you for calling. This is CallPilot scheduling assistant.",
            voice="alice"
        )
        response.pause(length=2)
        return Response(content=str(response), media_type="application/xml")
    return Response(
        content="<?xml version='1.0'?><Response><Say>Service unavailable</Say></Response>",
        media_type="application/xml"
    )


@app.post("/calls/status")
def handle_status(CallSid: str, CallStatus: str):
    """Handle Twilio call status callbacks"""
    if app_state.twilio and CallSid in app_state.twilio.active_calls:
        app_state.twilio.active_calls[CallSid]["status"] = CallStatus
    return {"status": "ok", "call_sid": CallSid, "call_status": CallStatus}


# ============================================================================
# Calendar Endpoints
# ============================================================================

@app.get("/calendar/slots")
def calendar_slots(pref: str = "afternoon"):
    """Get available calendar slots"""
    slots = app_state.calendar.find_available_slots(pref)
    return {"slots": slots, "preference": pref}


@app.get("/providers")
def get_providers(service_type: str = None, location: str = "KIIT Bhubaneswar"):
    """Get list of mock providers for testing"""
    if service_type:
        return app_state.places.search_nearby(location, service_type)
    return {
        "dentists": app_state.places.search_nearby(location, "dentist"),
        "doctors": app_state.places.search_nearby(location, "doctor"),
        "hospitals": app_state.places.search_nearby(location, "hospital")
    }


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
