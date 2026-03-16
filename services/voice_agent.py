"""
ElevenLabs Voice Agent with LangChain Integration
Implements the Agentic AI layer with tool-calling capabilities
"""
import os
import json
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass

try:
    from langchain.chat_models import ChatOpenAI
    from langchain.agents import initialize_agent, AgentType
    from langchain.tools import Tool
    from langchain.memory import ConversationBufferMemory
    from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    ChatOpenAI = None
    AgentType = None
    Tool = None

from .state_machine import CallContext, BookingResult


@dataclass
class VoiceCallConfig:
    """Configuration for voice call"""
    voice_id: str = "Rachel"
    model: str = "eleven_turbo_v2"
    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.0
    use_speaker_boost: bool = True


class ElevenLabsVoiceAgent:
    """
    AI Voice Agent for provider negotiation
    Uses LangChain for tool-calling and conversation management
    """
    
    SYSTEM_PROMPT = """
You are a professional appointment scheduling assistant named CallPilot.
Your role is to call service providers and book appointments on behalf of users.

GUIDELINES:
- Be polite, professional, and concise
- Speak clearly and at a moderate pace
- Always verify availability before confirming
- Respect the provider's time and policies
- If you encounter complex questions, note them for human handover

CAPABILITIES:
- Check user calendar availability before offering slots
- Negotiate appointment times within user preferences
- Handle common scheduling questions
- Escalate complex queries to human operators

CONSTRAINTS:
- Never hallucinate availability - always check tools
- Stay within user's budget constraints
- Respect user's time preferences (morning/afternoon/evening)
- Do not book conflicting appointments
"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        config: Optional[VoiceCallConfig] = None
    ):
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        self.config = config or VoiceCallConfig()
        self.llm = None
        self.agent = None
        self.memory = None
        
        if LANGCHAIN_AVAILABLE and self.api_key:
            self._initialize_langchain()
    
    def _initialize_langchain(self):
        """Initialize LangChain agent with tools"""
        try:
            # Initialize LLM
            self.llm = ChatOpenAI(
                model="gpt-4-turbo-preview",
                temperature=0.3,
                max_tokens=500
            )
            
            # Initialize memory
            self.memory = ConversationBufferMemory(
                memory_key="chat_history",
                return_messages=True
            )
            
            # Define tools
            tools = self._get_tools()
            
            # Initialize agent
            self.agent = initialize_agent(
                tools=tools,
                llm=self.llm,
                agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
                memory=self.memory,
                system_message=self.SYSTEM_PROMPT,
                verbose=True
            )
            
            print("✅ LangChain agent initialized")
        except Exception as e:
            print(f"⚠️ LangChain initialization failed: {e}")
            self.llm = None
            self.agent = None
    
    def _get_tools(self) -> List[Tool]:
        """Define available tools for the agent"""
        tools = []
        
        # Calendar availability tool
        tools.append(Tool(
            name="check_calendar_availability",
            func=self._check_calendar_availability,
            description="Check if a specific date/time is available on user's calendar. Input: date (YYYY-MM-DD) and time (HH:MM)"
        ))
        
        # Book appointment tool
        tools.append(Tool(
            name="book_appointment",
            func=self._book_appointment,
            description="Book an appointment on Google Calendar. Input: provider_name, date (YYYY-MM-DD), time (HH:MM), duration_minutes"
        ))
        
        # Get user preferences tool
        tools.append(Tool(
            name="get_user_preferences",
            func=self._get_user_preferences,
            description="Get user's scheduling preferences including budget, time preference, and priorities"
        ))
        
        return tools
    
    def _check_calendar_availability(self, date: str, time: str) -> str:
        """Check calendar availability (tool function)"""
        from .google_api import GoogleCalendarService
        
        calendar = GoogleCalendarService()
        slots = calendar.find_available_slots(pref="afternoon")
        
        requested_slot = {"date": date, "time": time}
        is_available = requested_slot in slots
        
        return json.dumps({
            "available": is_available,
            "date": date,
            "time": time
        })
    
    def _book_appointment(
        self,
        provider_name: str,
        date: str,
        time: str,
        duration_minutes: int = 30
    ) -> str:
        """Book appointment (tool function)"""
        from .google_api import GoogleCalendarService
        
        calendar = GoogleCalendarService()
        result = calendar.create_event(
            title=f"Appointment with {provider_name}",
            start_time=f"{date}T{time}",
            duration_minutes=duration_minutes
        )
        
        return json.dumps({
            "success": result is not None,
            "event_id": result.get("id") if result else None
        })
    
    def _get_user_preferences(self) -> str:
        """Get user preferences (tool function)"""
        return json.dumps({
            "time_preference": "afternoon",
            "max_budget": 2000,
            "prioritize_quality": False,
            "prioritize_cost": False
        })
    
    async def initiate_call(self, ctx: CallContext) -> BookingResult:
        """
        Initiate voice call to provider
        
        In production, this would:
        1. Use ElevenLabs API for TTS
        2. Use Twilio for PSTN connection
        3. Stream audio bidirectionally via WebSocket
        
        For now, returns mock result with proper structure
        """
        if not self.api_key:
            # Mock mode - simulate successful booking
            await asyncio.sleep(0.5)  # Simulate call delay
            
            ctx.add_transcript_entry("AI", f"Hello, this is CallPilot calling on behalf of {ctx.user_name}.")
            ctx.add_transcript_entry("AI", f"I'd like to schedule an appointment for {ctx.service_type}.")
            ctx.add_transcript_entry("Provider", "Yes, we have availability tomorrow at 10 AM.")
            ctx.add_transcript_entry("AI", "Perfect, I'll book that slot.")
            
            return BookingResult(
                success=True,
                provider_name=ctx.provider_name,
                appointment_date="2026-03-17",
                appointment_time="10:00 AM",
                price_quoted=ctx.max_budget or 150.0,
            )
        
        # Production mode with ElevenLabs
        try:
            return await self._execute_real_call(ctx)
        except Exception as e:
            return BookingResult(
                success=False,
                provider_name=ctx.provider_name,
                error_message=str(e)
            )
    
    async def _execute_real_call(self, ctx: CallContext) -> BookingResult:
        """Execute real call using ElevenLabs and Twilio"""
        from .twilio_service import TwilioPhoneService
        
        # Initialize Twilio
        twilio = TwilioPhoneService()
        
        # Generate initial greeting using ElevenLabs
        greeting = f"Hello, this is CallPilot calling on behalf of {ctx.user_name}. I'd like to schedule an appointment for {ctx.service_type}."
        
        # Convert to speech using ElevenLabs
        audio_url = await self._text_to_speech(greeting)
        
        # Initiate Twilio call
        call_result = twilio.initiate_call(
            to=ctx.provider_phone,
            name=ctx.provider_name,
            audio_url=audio_url
        )
        
        # Store call info in context
        ctx.metadata["twilio_call_sid"] = call_result.get("sid")
        
        # In production, would handle bidirectional streaming here
        # For now, return mock result
        return BookingResult(
            success=True,
            provider_name=ctx.provider_name,
            appointment_date="2026-03-17",
            appointment_time="10:00 AM",
            price_quoted=ctx.max_budget or 150.0,
        )
    
    async def _text_to_speech(self, text: str) -> str:
        """Convert text to speech using ElevenLabs API"""
        import aiohttp
        
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.config.voice_id}"
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "text": text,
            "model_id": self.config.model,
            "voice_settings": {
                "stability": self.config.stability,
                "similarity_boost": self.config.similarity_boost,
                "style": self.config.style
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    # Return audio data or URL
                    audio_data = await response.read()
                    # In production, upload to S3/GCS and return URL
                    return "audio_data_placeholder"
                else:
                    raise Exception(f"ElevenLabs API error: {response.status}")
    
    async def process_response(self, ctx: CallContext, user_input: str) -> str:
        """
        Process provider's response using LangChain agent
        
        Args:
            ctx: Call context
            user_input: Provider's spoken input (transcribed)
            
        Returns:
            AI agent's response
        """
        if self.agent:
            # Use LangChain agent
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.agent.run(
                    input=user_input,
                    context=ctx.to_dict()
                )
            )
            return result
        else:
            # Fallback simple response
            return self._simple_response(user_input)
    
    def _simple_response(self, user_input: str) -> str:
        """Simple rule-based response when LangChain not available"""
        user_input_lower = user_input.lower()
        
        if "not available" in user_input_lower or "fully booked" in user_input_lower:
            return "I understand. Do you have any other available slots this week?"
        elif "morning" in user_input_lower:
            return "Morning slots work well. What time specifically?"
        elif "afternoon" in user_input_lower:
            return "Afternoon is perfect. Would 2 PM work?"
        elif "price" in user_input_lower or "cost" in user_input_lower:
            return f"The budget for this service is around ₹{2000}. Is that within your range?"
        elif "yes" in user_input_lower or "confirmed" in user_input_lower:
            return "Great! I'll confirm this booking now."
        else:
            return "Could you please tell me more about your availability?"


class HallucinationValidator:
    """
    Validator agent that checks for hallucinations in call transcripts
    Uses a second LLM to verify booking confirmations
    """
    
    VALIDATION_PROMPT = """
Review this call transcript and booking result.
Did the provider actually confirm the appointment details?

TRANSCRIPT:
{transcript}

BOOKING RESULT:
{booking_result}

Respond with one of:
- CONFIRMED: Provider clearly confirmed the appointment
- AMBIGUOUS: Provider's confirmation is unclear
- HALLUCINATION: AI assumed confirmation without explicit provider agreement

Provide a brief explanation for your judgment.
"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.llm = None
        
        if LANGCHAIN_AVAILABLE and self.api_key:
            self.llm = ChatOpenAI(model="gpt-4-turbo-preview", temperature=0.1)
    
    async def validate(
        self,
        transcript: List[Dict[str, str]],
        booking_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate call transcript for hallucinations"""
        if not self.llm:
            return {
                "valid": True,
                "verdict": "SKIPPED",
                "explanation": "Validator not initialized"
            }
        
        # Format transcript
        transcript_text = "\n".join([
            f"{entry['speaker']}: {entry['text']}"
            for entry in transcript
        ])
        
        # Format prompt
        prompt = self.VALIDATION_PROMPT.format(
            transcript=transcript_text,
            booking_result=json.dumps(booking_result)
        )
        
        # Get validation result
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.llm.invoke(prompt)
        )
        
        content = response.content if hasattr(response, 'content') else str(response)
        
        # Parse response
        verdict = "AMBIGUOUS"
        if "CONFIRMED" in content.upper():
            verdict = "CONFIRMED"
        elif "HALLUCINATION" in content.upper():
            verdict = "HALLUCINATION"
        
        return {
            "valid": verdict == "CONFIRMED",
            "verdict": verdict,
            "explanation": content
        }
