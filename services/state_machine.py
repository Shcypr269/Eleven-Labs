"""
CallPilot - Agentic Swarm Architecture
Advanced state machine for call lifecycle management
"""
from enum import Enum, auto
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
import uuid


class CallState(Enum):
    """Call state machine states"""
    INITIATED = auto()
    RINGING = auto()
    NEGOTIATING = auto()
    CONFIRMING = auto()
    COMPLETED = auto()
    FAILED = auto()
    HANDOVER = auto()
    RETRYING = auto()


class CallEvent(Enum):
    """Events that trigger state transitions"""
    CALL_INITIATED = auto()
    PROVIDER_ANSWERED = auto()
    SLOT_IDENTIFIED = auto()
    SLOT_CONFIRMED = auto()
    SLOT_DECLINED = auto()
    HANDOVER_REQUESTED = auto()
    ERROR_OCCURRED = auto()
    RETRY_SCHEDULED = auto()


@dataclass
class BookingResult:
    """Result of a booking attempt"""
    success: bool
    provider_name: str
    appointment_date: Optional[str] = None
    appointment_time: Optional[str] = None
    price_quoted: Optional[float] = None
    error_message: Optional[str] = None


@dataclass
class StateTransition:
    """Records a state transition with metadata"""
    from_state: CallState
    to_state: CallState
    event: CallEvent
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class CallStateMachine:
    """
    State machine for managing call lifecycle
    Implements the orchestration layer pattern from the architecture
    """
    
    # Define valid transitions
    TRANSITIONS = {
        (CallState.INITIATED, CallEvent.CALL_INITIATED): CallState.RINGING,
        (CallState.RINGING, CallEvent.PROVIDER_ANSWERED): CallState.NEGOTIATING,
        (CallState.NEGOTIATING, CallEvent.SLOT_IDENTIFIED): CallState.CONFIRMING,
        (CallState.CONFIRMING, CallEvent.SLOT_CONFIRMED): CallState.COMPLETED,
        (CallState.CONFIRMING, CallEvent.SLOT_DECLINED): CallState.NEGOTIATING,
        (CallState.NEGOTIATING, CallEvent.HANDOVER_REQUESTED): CallState.HANDOVER,
        (CallState.RINGING, CallEvent.ERROR_OCCURRED): CallState.FAILED,
        (CallState.NEGOTIATING, CallEvent.ERROR_OCCURRED): CallState.FAILED,
        (CallState.CONFIRMING, CallEvent.ERROR_OCCURRED): CallState.FAILED,
        (CallState.FAILED, CallEvent.RETRY_SCHEDULED): CallState.RETRYING,
        (CallState.RETRYING, CallEvent.CALL_INITIATED): CallState.RINGING,
    }
    
    def __init__(self, call_id: str, provider_id: str, campaign_id: Optional[str] = None):
        self.call_id = call_id
        self.provider_id = provider_id
        self.campaign_id = campaign_id
        self.current_state = CallState.INITIATED
        self.transition_history: List[StateTransition] = []
        self.metadata: Dict[str, Any] = {}
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
    
    def transition(self, event: CallEvent, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Attempt to transition to a new state based on an event
        
        Args:
            event: The event triggering the transition
            metadata: Optional metadata to record with the transition
            
        Returns:
            True if transition was successful, False otherwise
        """
        key = (self.current_state, event)
        
        if key not in self.TRANSITIONS:
            print(f"Invalid transition: {self.current_state.name} --[{event.name}]--> ?")
            return False
        
        new_state = self.TRANSITIONS[key]
        
        # Record transition
        transition = StateTransition(
            from_state=self.current_state,
            to_state=new_state,
            event=event,
            metadata=metadata or {}
        )
        self.transition_history.append(transition)
        
        # Update state
        self.current_state = new_state
        self.updated_at = datetime.now()
        
        print(f"Transition: {transition.from_state.name} --[{transition.event.name}]--> {transition.to_state.name}")
        return True
    
    def can_transition(self, event: CallEvent) -> bool:
        """Check if a transition is valid from current state"""
        return (self.current_state, event) in self.TRANSITIONS
    
    def get_state_duration(self) -> float:
        """Get duration in seconds since last state change"""
        if not self.transition_history:
            return (datetime.now() - self.created_at).total_seconds()
        last_transition = self.transition_history[-1]
        return (datetime.now() - last_transition.timestamp).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize state machine for storage/transmission"""
        return {
            "call_id": self.call_id,
            "provider_id": self.provider_id,
            "campaign_id": self.campaign_id,
            "current_state": self.current_state.name,
            "transition_history": [
                {
                    "from_state": t.from_state.name,
                    "to_state": t.to_state.name,
                    "event": t.event.name,
                    "timestamp": t.timestamp.isoformat(),
                    "metadata": t.metadata
                }
                for t in self.transition_history
            ],
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "state_duration": self.get_state_duration()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CallStateMachine":
        """Deserialize state machine from dict"""
        sm = cls(
            call_id=data["call_id"],
            provider_id=data["provider_id"],
            campaign_id=data.get("campaign_id")
        )
        sm.current_state = CallState[data["current_state"]]
        sm.metadata = data.get("metadata", {})
        sm.created_at = datetime.fromisoformat(data["created_at"])
        sm.updated_at = datetime.fromisoformat(data["updated_at"])
        
        for t in data.get("transition_history", []):
            sm.transition_history.append(StateTransition(
                from_state=CallState[t["from_state"]],
                to_state=CallState[t["to_state"]],
                event=CallEvent[t["event"]],
                timestamp=datetime.fromisoformat(t["timestamp"]),
                metadata=t.get("metadata", {})
            ))
        
        return sm


@dataclass
class CallContext:
    """
    Context object passed through state transitions
    Contains all data needed for the call lifecycle
    """
    call_id: str
    provider_id: str
    provider_name: str
    provider_phone: str
    service_type: str
    user_name: str
    user_id: str
    campaign_id: Optional[str] = None
    preferred_times: List[str] = field(default_factory=list)
    max_budget: Optional[float] = None
    transcript: List[Dict[str, str]] = field(default_factory=list)
    booking_result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    def add_transcript_entry(self, speaker: str, text: str):
        """Add entry to call transcript"""
        self.transcript.append({
            "speaker": speaker,
            "text": text,
            "timestamp": datetime.now().isoformat()
        })
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize context for storage"""
        return {
            "call_id": self.call_id,
            "provider_id": self.provider_id,
            "provider_name": self.provider_name,
            "provider_phone": self.provider_phone,
            "service_type": self.service_type,
            "user_name": self.user_name,
            "user_id": self.user_id,
            "campaign_id": self.campaign_id,
            "preferred_times": self.preferred_times,
            "max_budget": self.max_budget,
            "transcript": self.transcript,
            "booking_result": self.booking_result,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries
        }
