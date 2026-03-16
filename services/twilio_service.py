"""
Twilio Phone Service
International telephony integration (fallback for non-India markets)
"""
import os
from datetime import datetime
from typing import Optional, Dict, List

try:
    from twilio.rest import Client
    from twilio.twiml.voice_response import VoiceResponse
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    Client = None
    VoiceResponse = None
    print("⚠️ Twilio not installed - pip install twilio")


class TwilioPhoneService:
    """
    Twilio integration for voice calls
    
    Note: For India, use Exotel service instead (better latency and compliance)
    """
    
    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        phone_number: Optional[str] = None
    ):
        self.account_sid = account_sid or os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = auth_token or os.getenv("TWILIO_AUTH_TOKEN")
        self.phone_number = phone_number or os.getenv("TWILIO_PHONE_NUMBER")
        
        self._client: Optional[Client] = None
        self.active_calls: Dict[str, Dict] = {}
        self._mock_mode = not all([self.account_sid, self.auth_token, self.phone_number])
        
        if self._mock_mode:
            print("⚠️ Twilio credentials not found - running in MOCK mode")
        else:
            print(f"✅ Twilio initialized: {self.phone_number}")
    
    @property
    def client(self) -> Optional[Client]:
        """Get Twilio client"""
        if not TWILIO_AVAILABLE:
            return None
        
        if self._client is None and self.account_sid and self.auth_token:
            self._client = Client(self.account_sid, self.auth_token)
        return self._client
    
    def initiate_call(
        self,
        to: str,
        name: str,
        callback_url: str = None
    ) -> Dict:
        """
        Initiate outbound call
        
        Args:
            to: Recipient phone number
            name: Provider name for display
            callback_url: TwiML webhook URL
            
        Returns:
            Call session info
        """
        if self._mock_mode or not self.client:
            return self._mock_call(to, name)
        
        try:
            call = self.client.calls.create(
                to=to,
                from_=self.phone_number,
                url=callback_url or f"http://localhost:8000/calls/twiml",
                status_callback=f"http://localhost:8000/calls/status",
                record=True
            )
            
            session = {
                "sid": call.sid,
                "phone": to,
                "name": name,
                "status": call.status,
                "started": datetime.now()
            }
            self.active_calls[session["sid"]] = session
            return session
            
        except Exception as e:
            print(f"Twilio call error: {e}")
            return self._mock_call(to, name)
    
    def _mock_call(self, to: str, name: str) -> Dict:
        """Mock call for testing"""
        import uuid
        session = {
            "sid": f"mock_{uuid.uuid4()}",
            "phone": to,
            "name": name,
            "status": "mock",
            "started": datetime.now()
        }
        self.active_calls[session["sid"]] = session
        print(f"📞 [MOCK] Calling {name} at {to}")
        return session
    
    def generate_twiml(self, message: str) -> str:
        """
        Generate TwiML for call flow
        
        Args:
            message: Message to speak
            
        Returns:
            TwiML XML string
        """
        if not VoiceResponse:
            return f'<?xml version="1.0"?><Response><Say>{message}</Say></Response>'
        
        response = VoiceResponse()
        response.say(message, voice="alice")
        response.pause(length=1)
        return str(response)
    
    def end_call(self, call_sid: str) -> bool:
        """End active call"""
        if call_sid not in self.active_calls:
            return False
        
        self.active_calls[call_sid]["status"] = "completed"
        
        if self.client and call_sid.startswith("CA"):
            try:
                self.client.calls(call_sid).update(status="completed")
            except:
                pass
        
        return True
    
    def get_call_status(self, call_sid: str) -> Optional[Dict]:
        """Get call status"""
        if call_sid in self.active_calls:
            return self.active_calls[call_sid].copy()
        return None
    
    def get_call_history(self, limit: int = 10) -> List[Dict]:
        """Get recent call history"""
        calls = list(self.active_calls.values())[-limit:]
        return [c.copy() for c in calls]


def create_twilio_service() -> TwilioPhoneService:
    """Factory function to create Twilio service"""
    return TwilioPhoneService()
