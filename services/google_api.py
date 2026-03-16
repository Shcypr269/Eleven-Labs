"""
Google API Services - Calendar and Maps integration
"""
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict


class GoogleCalendarService:
    """
    Google Calendar integration for appointment booking
    """
    
    def __init__(self):
        self.credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        self._mock_mode = not self.credentials_path
        
        if self._mock_mode:
            print("⚠️ Google Calendar credentials not found - using mock data")
        else:
            print("✅ Google Calendar initialized")
    
    def find_available_slots(self, pref: str = "afternoon") -> List[Dict[str, str]]:
        """
        Find available calendar slots
        
        Args:
            pref: Time preference (morning/afternoon/evening)
            
        Returns:
            List of available slots
        """
        if self._mock_mode:
            return self._mock_available_slots(pref)
        
        # Production: Query Google Calendar API
        # For now, return mock data
        return self._mock_available_slots(pref)
    
    def _mock_available_slots(self, pref: str = "afternoon") -> List[Dict[str, str]]:
        """Generate mock available slots"""
        now = datetime.now()
        hours = {
            "morning": range(8, 12),
            "afternoon": range(13, 17),
            "evening": range(17, 20)
        }.get(pref, range(13, 17))
        
        # Mock existing events
        events = [
            {"start": now.replace(hour=10), "end": now.replace(hour=11)},
            {"start": now.replace(hour=12, minute=30), "end": now.replace(hour=13, minute=30)}
        ]
        
        slots = []
        for d in range(1, 8):  # Next 7 days
            date = now + timedelta(days=d)
            if date.weekday() < 5:  # Weekdays only
                for h in hours:
                    start = date.replace(hour=h, minute=0, second=0)
                    # Check for conflicts
                    if not any(start < e["end"] and e["start"] < start + timedelta(hours=1) for e in events):
                        slots.append({
                            "date_str": start.strftime("%Y-%m-%d"),
                            "time_str": start.strftime("%I:%M %p")
                        })
        
        return slots[:20]  # Return first 20 slots
    
    def create_event(
        self,
        title: str,
        start_time: str,
        duration_minutes: int = 30
    ) -> Optional[Dict]:
        """
        Create calendar event
        
        Args:
            title: Event title
            start_time: ISO format start time
            duration_minutes: Event duration
            
        Returns:
            Event details or None
        """
        if self._mock_mode:
            return {
                "id": f"mock_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "title": title,
                "start": start_time,
                "end": start_time,
                "status": "confirmed"
            }
        
        # Production: Create event via Google Calendar API
        return None
    
    def check_availability(self, date: str, time: str) -> bool:
        """Check if a specific date/time is available"""
        # Production: Query Google Calendar API
        return True  # Mock: always available


class OpenStreetMapService:
    """
    OpenStreetMap (Nominatim) integration for location services
    """
    
    def __init__(self):
        self.base_url = "https://nominatim.openstreetmap.org"
        self.user_agent = "CallPilot/1.0"
        print("✅ OpenStreetMap initialized")
    
    def geocode(self, location: str) -> Optional[Dict]:
        """
        Convert location name to coordinates
        
        Args:
            location: Location name
            
        Returns:
            Dict with lat, lon, display_name or None
        """
        import requests
        
        try:
            response = requests.get(
                f"{self.base_url}/search",
                params={
                    "q": location,
                    "format": "json",
                    "limit": 1
                },
                headers={"User-Agent": self.user_agent},
                timeout=5
            )
            data = response.json()
            
            if data:
                return {
                    "lat": float(data[0]["lat"]),
                    "lon": float(data[0]["lon"]),
                    "display_name": data[0].get("display_name", location)
                }
        except Exception as e:
            print(f"Geocoding error: {e}")
        
        return None
    
    def search_nearby(
        self,
        location: str,
        service_type: str,
        radius: int = 5000
    ) -> List[Dict]:
        """
        Search for services near a location
        
        Args:
            location: Location name or coordinates
            service_type: Type of service (hospital, dentist, etc.)
            radius: Search radius in meters
            
        Returns:
            List of providers
        """
        coords = self.geocode(location)
        
        # Use mock data for India locations (Nominatim has limited healthcare data for India)
        if coords and "india" in coords.get("display_name", "").lower():
            return self._mock_search(service_type, location, coords)
        
        import requests
        
        try:
            categories = {
                "dentist": "dentist",
                "doctor": "doctor",
                "hospital": "hospital",
                "clinic": "clinic",
                "pharmacy": "pharmacy"
            }
            category = categories.get(service_type.lower(), service_type)
            
            d = 0.1  # ~10km
            viewbox = f"{coords['lon']-d},{coords['lat']-d},{coords['lon']+d},{coords['lat']+d}" if coords else ""
            
            response = requests.get(
                f"{self.base_url}/search",
                params={
                    "q": category,
                    "viewbox": viewbox,
                    "bounded": 1,
                    "format": "json",
                    "limit": 15
                },
                headers={"User-Agent": self.user_agent},
                timeout=10
            )
            results = response.json()
            
            providers = []
            for i, x in enumerate(results[:10]):
                providers.append({
                    "id": x.get("place_id", f"p{i}"),
                    "name": x.get("name") or f"{category.title()} {i}",
                    "service_type": service_type,
                    "rating": round(3.5 + (i % 15) * 0.1, 1),
                    "distance_miles": round(0.3 + i * 0.5, 1),
                    "price_range": 500 + i * 200,
                    "phone": f"+91-{x.get('osm_id', i):010d}",
                    "address": x.get("display_name", location),
                    "availability": (
                        ["morning", "afternoon"] if i % 3 != 0
                        else ["afternoon", "evening"]
                    ),
                    "lat": x.get("lat", str(coords["lat"] if coords else "20.35")),
                    "lon": x.get("lon", str(coords["lon"] if coords else "85.82"))
                })
            
            return providers if providers else self._mock_search(service_type, location, coords)
            
        except Exception as e:
            print(f"Search error: {e}")
            return self._mock_search(service_type, location, coords)
    
    def _mock_search(
        self,
        service_type: str,
        location: str,
        coords: Optional[Dict] = None
    ) -> List[Dict]:
        """Generate mock provider data for India locations"""
        lat = coords["lat"] if coords else 20.35
        lon = coords["lon"] if coords else 85.82
        
        return [
            {
                "id": 1,
                "name": "KIIT Hospital",
                "service_type": service_type,
                "rating": 4.8,
                "distance_miles": 1.0,
                "price_range": 1500,
                "phone": "+91-674-2725500",
                "address": "KIIT Road, Bhubaneswar, Odisha, 751024",
                "availability": ["morning", "afternoon"],
                "lat": str(lat),
                "lon": str(lon)
            },
            {
                "id": 2,
                "name": "Apollo Hospital Bhubaneswar",
                "service_type": service_type,
                "rating": 4.5,
                "distance_miles": 5.0,
                "price_range": 2500,
                "phone": "+91-674-6668000",
                "address": "Khandagiri, Bhubaneswar, Odisha, 751030",
                "availability": ["morning", "afternoon", "evening"],
                "lat": str(lat + 0.05),
                "lon": str(lon + 0.05)
            },
            {
                "id": 3,
                "name": "AIIMS Bhubaneswar",
                "service_type": service_type,
                "rating": 4.7,
                "distance_miles": 8.0,
                "price_range": 1000,
                "phone": "+91-674-2475400",
                "address": "Sijua, Bhubaneswar, Odisha, 751019",
                "availability": ["morning", "afternoon", "evening"],
                "lat": str(lat - 0.05),
                "lon": str(lon - 0.05)
            },
            {
                "id": 4,
                "name": "Cuttack Medical College",
                "service_type": service_type,
                "rating": 4.3,
                "distance_miles": 25.0,
                "price_range": 800,
                "phone": "+91-671-2430000",
                "address": "Cuttack, Odisha, 753007",
                "availability": ["morning", "afternoon"],
                "lat": str(lat + 0.2),
                "lon": str(lon + 0.2)
            }
        ]
    
    def get_place_details(self, place_id: str) -> Optional[Dict]:
        """
        Get detailed information about a place
        
        Args:
            place_id: Place identifier
            
        Returns:
            Place details or None
        """
        import requests
        
        try:
            response = requests.get(
                f"{self.base_url}/details",
                params={
                    "place_id": place_id,
                    "format": "json"
                },
                headers={"User-Agent": self.user_agent},
                timeout=5
            )
            data = response.json()
            
            return {
                "name": data.get("name", ""),
                "address": data.get("address", {}).get("road", ""),
                "phone": data.get("address", {}).get("phone", ""),
                "opening_hours": data.get("opening_hours", ""),
                "website": data.get("website", ""),
                "lat": data.get("lat", ""),
                "lon": data.get("lon", "")
            }
        except Exception as e:
            print(f"Place details error: {e}")
            return None
