"""
Vision/Intelligence Layer with OpenCV and OCR
Extracts business hours, prices, and other info from provider images

Note: Requires Tesseract OCR installed on your system:
- Windows: https://github.com/UB-Mannheim/tesseract/wiki
- Linux: sudo apt-get install tesseract-ocr
- Mac: brew install tesseract
"""
import os
import cv2
import numpy as np
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from pathlib import Path

try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False
    pytesseract = None
    print("⚠️ pytesseract not installed. Run: pip install pytesseract")


@dataclass
class BusinessHours:
    """Extracted business hours"""
    monday: Optional[str] = None
    tuesday: Optional[str] = None
    wednesday: Optional[str] = None
    thursday: Optional[str] = None
    friday: Optional[str] = None
    saturday: Optional[str] = None
    sunday: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Optional[str]]:
        return {
            "monday": self.monday,
            "tuesday": self.tuesday,
            "wednesday": self.wednesday,
            "thursday": self.thursday,
            "friday": self.friday,
            "saturday": self.saturday,
            "sunday": self.sunday,
        }


@dataclass
class PriceListItem:
    """Single price list entry"""
    service_name: str
    price: float
    currency: str = "₹"
    duration_minutes: Optional[int] = None


@dataclass
class ExtractedInfo:
    """All extracted information from provider image"""
    business_hours: Optional[BusinessHours] = None
    price_list: List[PriceListItem] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    raw_text: str = ""
    confidence: float = 0.0
    
    def __post_init__(self):
        if self.price_list is None:
            self.price_list = []


class OpenCVService:
    """
    OpenCV-based image preprocessing for OCR
    """
    
    @staticmethod
    def preprocess_for_ocr(image: np.ndarray) -> np.ndarray:
        """
        Preprocess image for optimal OCR results
        
        Steps:
        1. Convert to grayscale
        2. Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
        3. Denoise
        4. Threshold (Otsu's binarization)
        """
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        # Denoise with median blur
        denoised = cv2.medianBlur(enhanced, 3)
        
        # Apply Otsu's thresholding
        _, binary = cv2.threshold(
            denoised,
            0,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        
        return binary
    
    @staticmethod
    def detect_text_regions(image: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        Detect text regions using contour analysis
        
        Returns list of (x, y, width, height) tuples
        """
        # Edge detection
        edges = cv2.Canny(image, 50, 150, apertureSize=3)
        
        # Find contours
        contours, _ = cv2.findContours(
            edges,
            cv2.RETR_TREE,
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        text_regions = []
        for contour in contours:
            # Approximate contour
            perimeter = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.01 * perimeter, True)
            
            # Get bounding rectangle
            x, y, w, h = cv2.boundingRect(approx)
            
            # Filter based on size (text-like regions)
            if 20 < w < 500 and 10 < h < 100:
                aspect_ratio = w / float(h)
                if 0.1 < aspect_ratio < 10:  # Reasonable aspect ratio
                    text_regions.append((x, y, w, h))
        
        return text_regions
    
    @staticmethod
    def download_image(image_url: str) -> Optional[np.ndarray]:
        """Download image from URL"""
        import requests
        
        try:
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            
            # Convert to numpy array
            image_array = np.frombuffer(response.content, np.uint8)
            image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            
            return image
        except Exception as e:
            print(f"Error downloading image: {e}")
            return None
    
    @staticmethod
    def crop_region(image: np.ndarray, region: Tuple[int, int, int, int]) -> np.ndarray:
        """Crop a region from image"""
        x, y, w, h = region
        return image[y:y+h, x:x+w]


class OCRService:
    """
    Tesseract OCR service for text extraction using pytesseract (Python wrapper)
    
    Requires Tesseract OCR installed on your system:
    - Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
    - Linux: sudo apt-get install tesseract-ocr
    - Mac: brew install tesseract
    """
    
    def __init__(self, tessdata_path: Optional[str] = None, lang: str = "eng"):
        self.lang = lang
        self.tessdata_path = tessdata_path
        
        # Set Tesseract path if provided (Windows)
        if tessdata_path and os.name == 'nt':
            pytesseract.pytesseract.tesseract_cmd = tessdata_path + r'\tesseract.exe'
        
        if PYTESSERACT_AVAILABLE:
            print(f"✅ pytesseract initialized with language: {lang}")
            if tessdata_path:
                print(f"   Tesseract path: {tessdata_path}")
        else:
            print("⚠️ pytesseract not available - OCR will return empty results")
    
    def recognize(self, image: np.ndarray) -> str:
        """
        Recognize text in image using Tesseract (pytesseract)
        
        Args:
            image: Preprocessed image (numpy array)
            
        Returns:
            Extracted text
        """
        if not PYTESSERACT_AVAILABLE:
            return ""
        
        try:
            # Convert BGR to RGB for Tesseract
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Perform OCR using pytesseract
            config = f'--oem 3 --psm 6 -l {self.lang}'
            text = pytesseract.image_to_string(rgb_image, config=config)
            return text.strip()
        except Exception as e:
            print(f"OCR error: {e}")
            return ""
    
    def recognize_with_confidence(
        self,
        image: np.ndarray
    ) -> Tuple[str, float]:
        """
        Recognize text with confidence score
        
        Returns:
            Tuple of (text, confidence)
        """
        if not PYTESSERACT_AVAILABLE:
            return "", 0.0
        
        try:
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Get detailed OCR data
            data = pytesseract.image_to_data(rgb_image, output_type=pytesseract.Output.DICT)
            
            # Calculate average confidence
            confidences = [c for c in data['conf'] if c > 0]
            avg_confidence = sum(confidences) / len(confidences) / 100.0 if confidences else 0.0
            
            # Get full text
            text = pytesseract.image_to_string(rgb_image)
            
            return text.strip(), avg_confidence
        except Exception as e:
            print(f"OCR error: {e}")
            return "", 0.0


class ProviderVisionService:
    """
    High-level service for extracting provider information from images
    Combines OpenCV preprocessing with OCR and NLP parsing
    """
    
    def __init__(self, tessdata_path: Optional[str] = None):
        self.opencv = OpenCVService()
        self.ocr = OCRService(tessdata_path=tessdata_path)
    
    def extract_from_url(self, image_url: str) -> ExtractedInfo:
        """
        Extract information from provider image URL
        
        Args:
            image_url: URL of provider's business hours/price list image
            
        Returns:
            ExtractedInfo with all parsed information
        """
        # Download image
        image = self.opencv.download_image(image_url)
        if image is None:
            return ExtractedInfo(confidence=0.0)
        
        return self.extract_from_image(image)
    
    def extract_from_image(self, image: np.ndarray) -> ExtractedInfo:
        """
        Extract information from image
        
        Args:
            image: Image as numpy array
            
        Returns:
            ExtractedInfo with all parsed information
        """
        # Preprocess for OCR
        preprocessed = self.opencv.preprocess_for_ocr(image)
        
        # Extract full text
        raw_text = self.ocr.recognize(preprocessed)
        
        # Parse structured information
        info = ExtractedInfo(
            raw_text=raw_text,
            confidence=0.85
        )
        
        # Extract business hours
        info.business_hours = self._parse_business_hours(raw_text)
        
        # Extract phone number
        info.phone_number = self._extract_phone_number(raw_text)
        
        # Extract email
        info.email = self._extract_email(raw_text)
        
        # Extract website
        info.website = self._extract_website(raw_text)
        
        return info
    
    def _parse_business_hours(self, text: str) -> Optional[BusinessHours]:
        """Parse business hours from extracted text"""
        import re
        
        days_pattern = r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday)[:\s]+([0-9]+\s*[AP]M?\s*[-–to]+\s*[0-9]+\s*[AP]M?)'
        
        hours = {}
        for match in re.finditer(days_pattern, text, re.IGNORECASE):
            day = match.group(1).lower()
            time_range = match.group(2)
            hours[day] = time_range
        
        if not hours:
            return None
        
        return BusinessHours(
            monday=hours.get("monday"),
            tuesday=hours.get("tuesday"),
            wednesday=hours.get("wednesday"),
            thursday=hours.get("thursday"),
            friday=hours.get("friday"),
            saturday=hours.get("saturday"),
            sunday=hours.get("sunday"),
        )
    
    def _extract_phone_number(self, text: str) -> Optional[str]:
        """Extract phone number from text"""
        import re
        
        # Indian phone number pattern
        pattern = r'(\+91[-.\s]?)?[6-9]\d{9}|\d{3,4}[-.\s]?\d{3,4}[-.\s]?\d{4}'
        
        match = re.search(pattern, text.replace(" ", ""))
        if match:
            return match.group(0)
        
        return None
    
    def _extract_email(self, text: str) -> Optional[str]:
        """Extract email from text"""
        import re
        
        pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        
        match = re.search(pattern, text)
        if match:
            return match.group(0)
        
        return None
    
    def _extract_website(self, text: str) -> Optional[str]:
        """Extract website URL from text"""
        import re
        
        pattern = r'https?://[^\s]+|www\.[^\s]+'
        
        match = re.search(pattern, text)
        if match:
            return match.group(0)
        
        return None
    
    def extract_business_hours_from_image(
        self,
        image_path: str
    ) -> Optional[BusinessHours]:
        """
        Extract business hours from image file
        
        Args:
            image_path: Path to image file
            
        Returns:
            BusinessHours object or None
        """
        image = cv2.imread(image_path)
        if image is None:
            return None
        
        info = self.extract_from_image(image)
        return info.business_hours


# CNN-based price list detection (placeholder for model integration)
class CNNPriceDetector:
    """
    CNN-based price list detection
    This is a placeholder for integrating a trained PyTorch/TensorFlow model
    """
    
    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        self.model_path = model_path
        
        # In production, load trained model:
        # self._load_model(model_path)
    
    def _load_model(self, model_path: str):
        """Load trained CNN model"""
        try:
            import torch
            self.model = torch.load(model_path, map_location='cpu')
            self.model.eval()
            print(f"✅ CNN model loaded: {model_path}")
        except ImportError:
            print("⚠️ PyTorch not available, CNN detection disabled")
        except Exception as e:
            print(f"⚠️ Failed to load CNN model: {e}")
    
    def detect(self, image: np.ndarray) -> List[PriceListItem]:
        """
        Detect and extract price list from image using CNN
        
        In production, this would:
        1. Run object detection to find price table regions
        2. Extract text from detected regions
        3. Parse service names and prices
        """
        # Placeholder implementation
        # In production: run CNN inference
        
        return []


# Singleton instance
_vision_service: Optional[ProviderVisionService] = None


def get_vision_service(tessdata_path: Optional[str] = None) -> ProviderVisionService:
    """Get or create vision service singleton"""
    global _vision_service
    if _vision_service is None:
        _vision_service = ProviderVisionService(tessdata_path=tessdata_path)
    return _vision_service
