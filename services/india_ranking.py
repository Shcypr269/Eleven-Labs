"""
India-First Ranking Engine
Ranking providers with India-specific factors:
- Open status
- DND compliance
- Hinglish sentiment analysis
- Distance-weighted scoring
"""
import math
import re
from typing import List, Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass


@dataclass
class UserPreferences:
    """User preferences for provider ranking"""
    time_preference: str = "afternoon"
    max_budget: Optional[float] = None
    prioritize_quality: bool = False
    prioritize_cost: bool = False
    prioritize_convenience: bool = False


@dataclass
class IndiaRankingConfig:
    """Configuration for India-specific ranking"""
    weight_rating: float = 0.30
    weight_distance: float = 0.25
    weight_price: float = 0.20
    weight_open_status: float = 0.15
    weight_sentiment: float = 0.10

    # India-specific preferences
    prefer_morning: bool = False
    prefer_afternoon: bool = False
    prefer_evening: bool = False
    max_budget: Optional[float] = None
    prioritize_quality: bool = False
    prioritize_cost: bool = False


class IndiaRankingEngine:
    """
    Ranking engine optimized for Indian context
    
    Scoring formula:
    Score = (Rating × 20 × w_r) + 
            (exp(-0.3 × distance) × 100 × w_d) +
            ((1 - price/max_budget) × 100 × w_p) +
            (open_bonus × w_o) +
            (sentiment_score × w_s)
    """
    
    # Hindi/Hinglish keywords for sentiment analysis
    POSITIVE_HINGLISH = {
        "available", "hai", "yes", "mil", "jayega", "perfect", "badhiya",
        "thik", "okay", "confirm", "pakka", "zaroor", "sahi", "accha"
    }
    
    NEGATIVE_HINGLISH = {
        "nahi", "nhi", "no", "not", "kabhi", "never", "khatam", "over",
        "busy", "occupied", "full", "nahi hai", "available nahi"
    }
    
    # Common Indian medicine/product names
    MEDICINE_KEYWORDS = {
        "dawa", "dawai", "medicine", "tablet", "capsule", "syrup",
        "injection", "bandage", "paracetamol", "crocin", "disprin"
    }
    
    def __init__(self, config: Optional[IndiaRankingConfig] = None):
        self.config = config or IndiaRankingConfig()
    
    def rank_providers(
        self,
        providers: List[Dict[str, Any]],
        user_location: Dict[str, float],
        time_preference: str = "afternoon"
    ) -> List[Dict[str, Any]]:
        """
        Rank providers with India-specific scoring
        
        Args:
            providers: List of provider dicts from Google Places
            user_location: {"lat": float, "lng": float}
            time_preference: morning/afternoon/evening
            
        Returns:
            Sorted list of providers with score and rank
        """
        # Update config with time preference
        self.config.prefer_morning = time_preference == "morning"
        self.config.prefer_afternoon = time_preference == "afternoon"
        self.config.prefer_evening = time_preference == "evening"
        
        # Calculate weights based on preference
        if self.config.prioritize_quality:
            self.config.weight_rating = 0.45
            self.config.weight_price = 0.15
        elif self.config.prioritize_cost:
            self.config.weight_rating = 0.20
            self.config.weight_price = 0.45
        
        scored_providers = []
        
        for provider in providers:
            # Calculate individual scores
            rating_score = self._calc_rating_score(provider)
            distance_score = self._calc_distance_score(provider, user_location)
            price_score = self._calc_price_score(provider)
            open_score = self._calc_open_status_score(provider)
            sentiment_score = self._calc_sentiment_score(provider)
            
            # Weighted total
            total_score = (
                rating_score * self.config.weight_rating +
                distance_score * self.config.weight_distance +
                price_score * self.config.weight_price +
                open_score * self.config.weight_open_status +
                sentiment_score * self.config.weight_sentiment
            )
            
            # Add scores to provider
            provider_copy = provider.copy()
            provider_copy["score"] = round(total_score, 2)
            provider_copy["score_breakdown"] = {
                "rating": round(rating_score, 2),
                "distance": round(distance_score, 2),
                "price": round(price_score, 2),
                "open_status": round(open_score, 2),
                "sentiment": round(sentiment_score, 2)
            }
            
            scored_providers.append(provider_copy)
        
        # Sort by score (descending)
        ranked = sorted(scored_providers, key=lambda x: x["score"], reverse=True)
        
        # Add rank
        for i, provider in enumerate(ranked):
            provider["rank"] = i + 1
        
        return ranked
    
    def _calc_rating_score(self, provider: Dict[str, Any]) -> float:
        """Calculate rating score (0-100)"""
        rating = provider.get("rating", 0)
        total_ratings = provider.get("total_ratings", 0)
        
        # Base score from rating (convert 5-star to 0-100)
        base_score = (rating / 5.0) * 100
        
        # Boost for high number of reviews (trust factor)
        review_boost = min(20, math.log10(max(1, total_ratings)) * 10)
        
        return min(100, base_score + review_boost)
    
    def _calc_distance_score(
        self,
        provider: Dict[str, Any],
        user_location: Dict[str, float]
    ) -> float:
        """Calculate distance score (0-100)"""
        distance = provider.get("distance_miles", 0)
        
        # If distance already calculated
        if distance > 0:
            return 100 * math.exp(-0.3 * distance)
        
        # Calculate distance from coordinates
        try:
            provider_lat = float(provider.get("lat", 0))
            provider_lng = float(provider.get("lng", 0))
            
            if provider_lat and provider_lng:
                distance_km = self._haversine_distance(
                    user_location["lat"],
                    user_location["lng"],
                    provider_lat,
                    provider_lng
                )
                distance_miles = distance_km * 0.621371
                return 100 * math.exp(-0.3 * distance_miles)
        except:
            pass
        
        return 50  # Default score if distance unknown
    
    def _calc_price_score(self, provider: Dict[str, Any]) -> float:
        """Calculate price score (0-100)"""
        price_range = provider.get("price_range", 0)
        max_budget = self.config.max_budget
        
        if not max_budget or price_range == 0:
            return 50  # Neutral if unknown
        
        if price_range > max_budget:
            return 0  # Out of budget
        
        # Score based on how much under budget
        ratio = price_range / max_budget
        return 100 * (1 - ratio)
    
    def _calc_open_status_score(self, provider: Dict[str, Any]) -> float:
        """Calculate open status score (0-100)"""
        is_open = provider.get("is_open", None)
        
        if is_open is None:
            # Check business hours
            business_hours = provider.get("business_hours", {})
            if business_hours:
                is_open = self._is_currently_open(business_hours)
            else:
                return 50  # Unknown
        
        if is_open:
            # Bonus for being open now
            return 100
        else:
            return 20  # Penalize closed shops
    
    def _calc_sentiment_score(self, provider: Dict[str, Any]) -> float:
        """
        Calculate sentiment score from reviews
        Analyzes for Hinglish sentiment
        """
        reviews = provider.get("reviews", [])
        if not reviews:
            return 50  # Neutral if no reviews
        
        total_sentiment = 0
        for review in reviews[:10]:  # Analyze last 10 reviews
            text = review.get("text", "").lower()
            sentiment = self._analyze_hinglish_sentiment(text)
            total_sentiment += sentiment
        
        avg_sentiment = total_sentiment / min(len(reviews), 10)
        
        # Convert -1 to 1 range to 0-100
        return (avg_sentiment + 1) * 50
    
    def _analyze_hinglish_sentiment(self, text: str) -> float:
        """
        Analyze sentiment of Hinglish text
        
        Returns:
            -1 (negative) to 1 (positive)
        """
        words = re.findall(r'\w+', text.lower())
        
        positive_count = sum(1 for w in words if w in self.POSITIVE_HINGLISH)
        negative_count = sum(1 for w in words if w in self.NEGATIVE_HINGLISH)
        
        total = positive_count + negative_count
        if total == 0:
            return 0  # Neutral
        
        # Calculate sentiment ratio
        ratio = (positive_count - negative_count) / total
        
        return max(-1, min(1, ratio))
    
    def _is_currently_open(self, business_hours: Dict[str, Any]) -> bool:
        """Check if business is currently open"""
        try:
            now = datetime.now()
            current_day = now.strftime("%A").lower()
            current_hour = now.hour
            
            day_hours = business_hours.get(current_day, {})
            if not day_hours:
                return False
            
            open_time = int(day_hours.get("open", "0900"))
            close_time = int(day_hours.get("close", "2100"))
            
            current_time = current_hour * 100 + now.minute
            
            return open_time <= current_time <= close_time
        except:
            return True  # Default to open if parsing fails
    
    def _haversine_distance(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float
    ) -> float:
        """
        Calculate distance between two coordinates in km
        
        Haversine formula for great-circle distance
        """
        R = 6371  # Earth's radius in km
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (
            math.sin(delta_lat / 2) ** 2 +
            math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    def filter_by_dnd(
        self,
        providers: List[Dict[str, Any]],
        dnd_checked_numbers: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Filter out providers whose numbers are on DND list
        
        Args:
            providers: List of providers
            dnd_checked_numbers: List of numbers cleared for calling
            
        Returns:
            Filtered list
        """
        return [
            p for p in providers
            if self._normalize_phone(p.get("phone", "")) in dnd_checked_numbers
        ]
    
    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number to Indian format"""
        # Remove all non-digits
        digits = re.sub(r'\D', '', phone)
        
        # Add 91 prefix if not present
        if not digits.startswith("91") and len(digits) == 10:
            digits = "91" + digits
        
        return "+" + digits


class MedicineAvailabilityChecker:
    """
    Check medicine availability using Hinglish NLP
    
    Identifies if a pharmacy has specific medicines
    """
    
    def __init__(self):
        self.medicine_keywords = IndiaRankingEngine.MEDICINE_KEYWORDS
    
    def extract_medicine_request(self, text: str) -> List[str]:
        """
        Extract medicine names from Hinglish text
        
        Example: "Mujhe paracetamol aur crocin chahiye"
        Returns: ["paracetamol", "crocin"]
        """
        text_lower = text.lower()
        found_medicines = []
        
        for medicine in self.medicine_keywords:
            if medicine in text_lower:
                found_medicines.append(medicine)
        
        return found_medicines
    
    def check_availability_response(
        self,
        response_text: str
    ) -> Dict[str, Any]:
        """
        Parse pharmacy's response about availability
        
        Returns:
            {
                "available": bool,
                "medicines": list,
                "alternative": str or None
            }
        """
        text_lower = response_text.lower()
        
        # Check for availability
        available_phrases = ["hai", "available hai", "mil jayega", "present hai"]
        unavailable_phrases = ["nahi hai", "khatam", "out of stock", "available nahi"]
        
        is_available = any(phrase in text_lower for phrase in available_phrases)
        is_unavailable = any(phrase in text_lower for phrase in unavailable_phrases)
        
        # Check for alternatives
        alternative = None
        if "alternative" in text_lower or "substitute" in text_lower:
            # Extract alternative medicine name (simplified)
            alternative = "Alternative available"
        
        return {
            "available": is_available and not is_unavailable,
            "medicines": self.extract_medicine_request(response_text),
            "alternative": alternative
        }


# Convenience function
def rank_providers(
    providers: List[Dict[str, Any]],
    location: str,
    time_preference: str = "afternoon",
    max_budget: Optional[float] = None,
    user_location: Optional[Dict[str, float]] = None,
    config: Optional[IndiaRankingConfig] = None
) -> List[Dict[str, Any]]:
    """
    Rank providers with India-specific scoring
    
    Backward-compatible with existing code
    """
    # Default location to KIIT Bhubaneswar if not provided
    if user_location is None:
        user_location = {"lat": 20.35, "lng": 85.82}
    
    if config is None:
        config = IndiaRankingConfig(max_budget=max_budget)
    
    engine = IndiaRankingEngine(config)
    return engine.rank_providers(providers, user_location, time_preference)
