
"""
Distributed Swarm Orchestrator with Redis
Manages parallel provider calls with distributed locking
"""
import asyncio
import uuid
import json
import redis.asyncio as redis
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

from .state_machine import CallStateMachine, CallState, CallEvent, CallContext


class CampaignStatus(Enum):
    INITIATED = "initiated"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class CallStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    NO_ANSWER = "no_answer"
    UNAVAILABLE = "unavailable"
    PRICE_MISMATCH = "price_mismatch"
    HANDED_OVER = "handed_over"


@dataclass
class ProviderTarget:
    """Target provider for swarm call"""
    id: str
    name: str
    phone: str
    rating: float
    price_range: float
    address: str
    service_type: str


@dataclass
class SwarmCallResult:
    """Result of individual provider call"""
    provider_id: str
    provider_name: str
    status: CallStatus
    success: bool = False
    booking_result: Optional[Dict[str, Any]] = None
    transcript: List[Dict[str, str]] = field(default_factory=list)
    error_message: Optional[str] = None
    call_duration: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SwarmCampaign:
    """
    Swarm campaign orchestrating multiple parallel provider calls
    """
    campaign_id: str
    user_id: str
    service_type: str
    location: str
    time_preference: str
    max_budget: Optional[float]
    targets: List[ProviderTarget]
    status: CampaignStatus = CampaignStatus.INITIATED
    results: Dict[str, SwarmCallResult] = field(default_factory=dict)
    best_booking: Optional[SwarmCallResult] = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    @property
    def success_rate(self) -> float:
        if not self.results:
            return 0.0
        successful = sum(1 for r in self.results.values() if r.success)
        return successful / len(self.results)
    
    @property
    def calls_made(self) -> int:
        return len(self.results)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "user_id": self.user_id,
            "service_type": self.service_type,
            "location": self.location,
            "time_preference": self.time_preference,
            "max_budget": self.max_budget,
            "status": self.status.value,
            "targets": [
                {
                    "id": t.id,
                    "name": t.name,
                    "phone": t.phone,
                    "rating": t.rating,
                    "price_range": t.price_range,
                }
                for t in self.targets
            ],
            "results": {
                k: {
                    "provider_id": v.provider_id,
                    "provider_name": v.provider_name,
                    "status": v.status.value,
                    "success": v.success,
                    "booking_result": v.booking_result,
                    "error_message": v.error_message,
                    "call_duration": v.call_duration,
                }
                for k, v in self.results.items()
            },
            "best_booking": {
                "provider_name": self.best_booking.provider_name,
                "booking_result": self.best_booking.booking_result,
            } if self.best_booking else None,
            "success_rate": self.success_rate,
            "calls_made": self.calls_made,
            "total_targets": len(self.targets),
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class DistributedLockManager:
    """
    Manages distributed locks using Redis
    Prevents double-booking when multiple calls target same slot
    """
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.lock_timeout = 300  # 5 minutes
    
    async def acquire_lock(self, resource: str, timeout: Optional[int] = None) -> bool:
        """
        Acquire a distributed lock for a resource
        
        Args:
            resource: Resource identifier (e.g., "calendar:2026-03-17T10:00")
            timeout: Lock timeout in seconds
            
        Returns:
            True if lock acquired, False otherwise
        """
        lock_key = f"lock:{resource}"
        lock_value = str(uuid.uuid4())
        timeout = timeout or self.lock_timeout
        
        acquired = await self.redis.set(
            lock_key,
            lock_value,
            nx=True,  # Only set if not exists
            ex=timeout
        )
        
        return bool(acquired)
    
    async def release_lock(self, resource: str) -> bool:
        """Release a distributed lock"""
        lock_key = f"lock:{resource}"
        return bool(await self.redis.delete(lock_key))
    
    async def lock_calendar_slot(self, date: str, time: str) -> bool:
        """Lock a specific calendar time slot"""
        slot_key = f"calendar:{date}:{time}"
        return await self.acquire_lock(slot_key, timeout=120)  # 2 min for booking


class SwarmOrchestrator:
    """
    Orchestrates swarm calling campaigns with distributed state management
    Uses Redis for state caching and distributed locking
    """
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        max_concurrent: int = 5,
        voice_agent=None
    ):
        self.redis_url = redis_url
        self.max_concurrent = max_concurrent
        self.voice_agent = voice_agent
        self.redis: Optional[redis.Redis] = None
        self.lock_manager: Optional[DistributedLockManager] = None
        self.active_campaigns: Dict[str, SwarmCampaign] = {}
        self._initialized = False
    
    async def initialize(self):
        """Initialize Redis connection"""
        if not self._initialized:
            self.redis = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            self.lock_manager = DistributedLockManager(self.redis)
            self._initialized = True
            print(f"✅ SwarmOrchestrator connected to Redis: {self.redis_url}")
    
    async def close(self):
        """Close Redis connection"""
        if self.redis:
            await self.redis.close()
            self._initialized = False
    
    def create_campaign(
        self,
        user_id: str,
        service_type: str,
        location: str,
        time_preference: str,
        max_budget: Optional[float],
        providers: List[Dict[str, Any]],
        max_providers: int = 5
    ) -> SwarmCampaign:
        """Create a new swarm campaign"""
        targets = [
            ProviderTarget(
                id=p.get("id", f"p{i}"),
                name=p["name"],
                phone=p["phone"],
                rating=p.get("rating", 0),
                price_range=p.get("price_range", 0),
                address=p.get("address", ""),
                service_type=service_type,
            )
            for i, p in enumerate(providers[:max_providers])
        ]
        
        campaign = SwarmCampaign(
            campaign_id=str(uuid.uuid4()),
            user_id=user_id,
            service_type=service_type,
            location=location,
            time_preference=time_preference,
            max_budget=max_budget,
            targets=targets,
        )
        
        self.active_campaigns[campaign.campaign_id] = campaign
        return campaign
    
    async def execute_swarm(
        self,
        campaign_id: str,
        user_name: str = "User"
    ) -> SwarmCampaign:
        """
        Execute swarm campaign - call all providers in parallel
        
        Uses semaphore to limit concurrent calls
        """
        campaign = self.active_campaigns.get(campaign_id)
        if not campaign:
            raise ValueError(f"Campaign not found: {campaign_id}")
        
        campaign.status = CampaignStatus.IN_PROGRESS
        
        # Persist campaign start to Redis
        if self.redis:
            await self.redis.setex(
                f"campaign:{campaign_id}",
                3600,  # 1 hour TTL
                json.dumps(campaign.to_dict())
            )
        
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def call_provider(target: ProviderTarget) -> SwarmCallResult:
            async with semaphore:
                return await self._execute_provider_call(
                    campaign=campaign,
                    target=target,
                    user_name=user_name
                )
        
        # Execute all provider calls in parallel
        tasks = [call_provider(target) for target in campaign.targets]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Handle exception
                target = campaign.targets[i]
                campaign.results[target.id] = SwarmCallResult(
                    provider_id=target.id,
                    provider_name=target.name,
                    status=CallStatus.FAILED,
                    error_message=str(result)
                )
            else:
                campaign.results[result.provider_id] = result
        
        # Find best booking
        successful_results = [r for r in campaign.results.values() if r.success]
        if successful_results:
            # Select best based on price and rating
            campaign.best_booking = min(
                successful_results,
                key=lambda x: (
                    x.booking_result.get("price_quoted", float("inf")) if x.booking_result else 0,
                    -campaign.targets[int(x.provider_id[1:])].rating if x.provider_id.startswith("p") else 0
                )
            )
            campaign.status = CampaignStatus.COMPLETED
        else:
            campaign.status = CampaignStatus.PARTIAL if campaign.results else CampaignStatus.FAILED
        
        campaign.completed_at = datetime.now()
        
        # Update Redis
        if self.redis:
            await self.redis.setex(
                f"campaign:{campaign_id}",
                3600,
                json.dumps(campaign.to_dict())
            )
        
        return campaign
    
    async def _execute_provider_call(
        self,
        campaign: SwarmCampaign,
        target: ProviderTarget,
        user_name: str
    ) -> SwarmCallResult:
        """Execute single provider call with state machine"""
        from .voice_agent import ElevenLabsVoiceAgent
        
        call_id = str(uuid.uuid4())
        start_time = datetime.now()
        
        # Create state machine
        state_machine = CallStateMachine(
            call_id=call_id,
            provider_id=target.id,
            campaign_id=campaign.campaign_id
        )
        
        # Create call context
        context = CallContext(
            call_id=call_id,
            provider_id=target.id,
            provider_name=target.name,
            provider_phone=target.phone,
            service_type=campaign.service_type,
            user_name=user_name,
            user_id=campaign.user_id,
            campaign_id=campaign.campaign_id,
            preferred_times=[campaign.time_preference],
            max_budget=target.price_range,
        )
        
        try:
            # Initialize call
            state_machine.transition(CallEvent.CALL_INITIATED)
            
            # Execute voice call
            voice_agent = ElevenLabsVoiceAgent()
            booking_result = await voice_agent.initiate_call(context)
            
            if booking_result.success:
                state_machine.transition(CallEvent.PROVIDER_ANSWERED)
                state_machine.transition(CallEvent.SLOT_IDENTIFIED)
                state_machine.transition(CallEvent.SLOT_CONFIRMED)
                
                # Try to lock calendar slot (distributed locking)
                if self.lock_manager and booking_result.appointment_date:
                    locked = await self.lock_manager.lock_calendar_slot(
                        booking_result.appointment_date,
                        booking_result.appointment_time
                    )
                    if not locked:
                        # Slot already booked by another swarm call
                        state_machine.transition(CallEvent.SLOT_DECLINED)
                        return SwarmCallResult(
                            provider_id=target.id,
                            provider_name=target.name,
                            status=CallStatus.UNAVAILABLE,
                            error_message="Slot already booked"
                        )
                
                return SwarmCallResult(
                    provider_id=target.id,
                    provider_name=target.name,
                    status=CallStatus.SUCCESS,
                    success=True,
                    booking_result={
                        "appointment_date": booking_result.appointment_date,
                        "appointment_time": booking_result.appointment_time,
                        "price_quoted": booking_result.price_quoted,
                    },
                    transcript=context.transcript,
                    call_duration=(datetime.now() - start_time).total_seconds()
                )
            else:
                state_machine.transition(CallEvent.SLOT_DECLINED)
                return SwarmCallResult(
                    provider_id=target.id,
                    provider_name=target.name,
                    status=CallStatus.UNAVAILABLE,
                    success=False,
                    transcript=context.transcript,
                    call_duration=(datetime.now() - start_time).total_seconds()
                )
                
        except Exception as e:
            state_machine.transition(CallEvent.ERROR_OCCURRED, {"error": str(e)})
            return SwarmCallResult(
                provider_id=target.id,
                provider_name=target.name,
                status=CallStatus.FAILED,
                success=False,
                error_message=str(e),
                call_duration=(datetime.now() - start_time).total_seconds()
            )
    
    async def get_campaign(self, campaign_id: str) -> Optional[SwarmCampaign]:
        """Get campaign by ID (from cache or memory)"""
        # Check memory first
        if campaign_id in self.active_campaigns:
            return self.active_campaigns[campaign_id]
        
        # Check Redis
        if self.redis:
            data = await self.redis.get(f"campaign:{campaign_id}")
            if data:
                return self._dict_to_campaign(json.loads(data))
        
        return None
    
    async def get_campaign_stats(self, campaign_id: str) -> Dict[str, Any]:
        """Get campaign statistics"""
        campaign = await self.get_campaign(campaign_id)
        if not campaign:
            return {}
        
        successful = sum(1 for r in campaign.results.values() if r.success)
        return {
            "campaign_id": campaign_id,
            "status": campaign.status.value,
            "total_targets": len(campaign.targets),
            "calls_made": campaign.calls_made,
            "successful_calls": successful,
            "success_rate": campaign.success_rate,
            "has_booking": campaign.best_booking is not None,
        }
    
    def _dict_to_campaign(self, data: Dict[str, Any]) -> SwarmCampaign:
        """Deserialize campaign from dict"""
        campaign = SwarmCampaign(
            campaign_id=data["campaign_id"],
            user_id=data["user_id"],
            service_type=data["service_type"],
            location=data["location"],
            time_preference=data["time_preference"],
            max_budget=data.get("max_budget"),
            targets=[
                ProviderTarget(
                    id=t["id"],
                    name=t["name"],
                    phone=t["phone"],
                    rating=t["rating"],
                    price_range=t["price_range"],
                    address="",
                    service_type=data["service_type"],
                )
                for t in data.get("targets", [])
            ],
            status=CampaignStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
        )
        
        if data.get("completed_at"):
            campaign.completed_at = datetime.fromisoformat(data["completed_at"])
        
        return campaign


# Singleton instance
_swarm_orchestrator: Optional[SwarmOrchestrator] = None


def get_swarm_orchestrator(redis_url: str = "redis://localhost:6379") -> SwarmOrchestrator:
    """Get or create swarm orchestrator singleton"""
    global _swarm_orchestrator
    if _swarm_orchestrator is None:
        _swarm_orchestrator = SwarmOrchestrator(redis_url=redis_url)
    return _swarm_orchestrator
