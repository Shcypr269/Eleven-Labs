# CallPilot - Agentic Swarm Setup Guide

## 🏗️ Architecture Overview

CallPilot now implements a production-grade **Agentic Swarm Architecture** with:

- **State Machine**: Call lifecycle management (INITIATED → RINGING → NEGOTIATING → CONFIRMING → COMPLETED)
- **Swarm Orchestrator**: Distributed parallel calling with Redis locking
- **Voice Agent**: LangChain-powered AI with tool-calling capabilities
- **Vision Service**: OpenCV + OCR for extracting info from provider images
- **WebSocket Streaming**: Full-duplex audio for < 500ms latency
- **Hallucination Validator**: Post-call verification using LLM

---

## 📋 Prerequisites

- Python 3.10+
- Redis 7.0+ (optional, for distributed locking)
- ElevenLabs API key (for voice calls)
- Twilio credentials (optional, for real phone calls)

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd "C:\Users\seniv\Downloads\Machine Learning\callpilot"

# Activate virtual environment
.venv\Scripts\activate

# Install all dependencies
pip install -r requirements.txt
```

### 2. Set Up Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# ElevenLabs (Required for voice)
ELEVENLABS_API_KEY=your_api_key_here
ELEVENLABS_VOICE_ID=Rachel

# Twilio (Optional - mock mode enabled without)
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_PHONE_NUMBER=+1234567890

# Redis (Optional - for distributed swarm)
REDIS_URL=redis://localhost:6379

# OpenAI (Optional - for LangChain agent)
OPENAI_API_KEY=your_openai_key

# Google (Optional - for real calendar integration)
GOOGLE_APPLICATION_CREDENTIALS=path/to/credentials.json

# Vision/OCR (Optional)
TESSDATA_PATH=C:\Program Files\Tesseract-OCR\tessdata
ENABLE_WEBSOCKET=true
```

### 3. Install Redis (Optional but Recommended)

**Windows:**
```bash
# Using Chocolatey
choco install redis-64

# Or download from: https://github.com/microsoftarchive/redis/releases
```

**Linux/Mac:**
```bash
# Ubuntu/Debian
sudo apt-get install redis-server

# Mac
brew install redis
```

### 4. Run the Server

```bash
# Activate virtual environment
.venv\Scripts\activate

# Start FastAPI backend
python main.py
```

The server will start on `http://localhost:8000`

### 5. Start Streamlit UI (Optional)

Open a new terminal:

```bash
.venv\Scripts\activate
streamlit run app.py
```

Access the UI at `http://localhost:8501`

---

## 📡 API Endpoints

### Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| GET | `/places/search?service_type=dentist&location=KIIT` | Search providers |
| GET | `/places/details/{place_id}` | Get provider details |
| POST | `/book` | Book appointment |
| GET | `/calendar/slots?pref=afternoon` | Get calendar slots |

### Swarm Mode (New!)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/swarm` | Start swarm campaign |
| GET | `/swarm/{campaign_id}` | Get campaign status |
| GET | `/swarm/{campaign_id}/results` | Get detailed results |

### Voice Calls

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/voice/call` | Initiate voice call |
| GET | `/calls/history` | Get call history |
| WS | `/ws/voice` | WebSocket voice streaming |

### Vision/OCR (New!)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/vision/extract` | Extract info from images |

---

## 🔬 Usage Examples

### 1. Search Providers

```bash
curl "http://localhost:8000/places/search?service_type=hospital&location=KIIT%20Bhubaneswar"
```

### 2. Book Appointment

```bash
curl -X POST "http://localhost:8000/book" \
  -H "Content-Type: application/json" \
  -d '{
    "service_type": "dentist",
    "location": "KIIT Bhubaneswar",
    "time_preference": "afternoon",
    "max_budget": 2000,
    "user_name": "John Doe"
  }'
```

### 3. Start Swarm Campaign (NEW!)

```bash
curl -X POST "http://localhost:8000/swarm" \
  -H "Content-Type: application/json" \
  -d '{
    "service_type": "hospital",
    "location": "KIIT Bhubaneswar",
    "time_preference": "morning",
    "max_budget": 3000,
    "max_providers": 5,
    "user_name": "John Doe"
  }'
```

Response:
```json
{
  "campaign_id": "abc123-def456",
  "status": "initiated",
  "targets": 5,
  "message": "Swarm campaign started with 5 providers"
}
```

### 4. Check Swarm Status

```bash
curl "http://localhost:8000/swarm/abc123-def456"
```

Response:
```json
{
  "campaign_id": "abc123-def456",
  "status": "completed",
  "total_targets": 5,
  "calls_made": 5,
  "successful_calls": 3,
  "success_rate": 0.6,
  "has_booking": true
}
```

### 5. Extract Info from Provider Image (NEW!)

```bash
curl -X POST "http://localhost:8000/vision/extract" \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://example.com/business-hours.jpg",
    "extract_type": "business_hours"
  }'
```

---

## 🧪 Testing the Agentic Swarm

### Test 1: State Machine

```python
from services import CallStateMachine, CallState, CallEvent

# Create state machine
sm = CallStateMachine(
    call_id="call_001",
    provider_id="provider_001",
    campaign_id="campaign_001"
)

# Transition through states
sm.transition(CallEvent.CALL_INITIATED)  # INITIATED → RINGING
sm.transition(CallEvent.PROVIDER_ANSWERED)  # RINGING → NEGOTIATING
sm.transition(CallEvent.SLOT_IDENTIFIED)  # NEGOTIATING → CONFIRMING
sm.transition(CallEvent.SLOT_CONFIRMED)  # CONFIRMING → COMPLETED

print(sm.to_dict())
```

### Test 2: Swarm Orchestrator

```python
import asyncio
from services import get_swarm_orchestrator

async def test_swarm():
    swarm = get_swarm_orchestrator()
    await swarm.initialize()
    
    # Create campaign
    campaign = swarm.create_campaign(
        user_id="user_001",
        service_type="dentist",
        location="KIIT Bhubaneswar",
        time_preference="afternoon",
        max_budget=2000,
        providers=[...],  # Provider list
        max_providers=5
    )
    
    # Execute swarm
    result = await swarm.execute_swarm(campaign.campaign_id)
    
    print(f"Success rate: {result.success_rate}")
    print(f"Best booking: {result.best_booking}")
    
    await swarm.close()

asyncio.run(test_swarm())
```

### Test 3: Vision Service

```python
from services import get_vision_service

vision = get_vision_service()

# Extract from URL
info = vision.extract_from_url("https://example.com/hours.jpg")

print(f"Business Hours: {info.business_hours}")
print(f"Phone: {info.phone_number}")
print(f"Confidence: {info.confidence}")
```

---

## 🏛️ Architecture Components

### 1. State Machine (`services/state_machine.py`)

Manages call lifecycle with proper state transitions:

```
INITIATED → RINGING → NEGOTIATING → CONFIRMING → COMPLETED
                               ↓
                         HANDOVER (if complex query)
                               ↓
                          FAILED → RETRYING
```

### 2. Swarm Orchestrator (`services/swarm.py`)

- **Distributed Locking**: Redis-based locks prevent double-booking
- **Parallel Execution**: Semaphore limits concurrent calls
- **Campaign Management**: Tracks all swarm calls

### 3. Voice Agent (`services/voice_agent.py`)

- **LangChain Integration**: Tool-calling agent with calendar/maps tools
- **Hallucination Validator**: Post-call verification
- **Mock Mode**: Works without API keys for testing

### 4. Vision Service (`services/vision_service.py`)

- **OpenCV Preprocessing**: CLAHE, denoising, thresholding
- **Tesseract OCR**: Text extraction
- **NLP Parsing**: Extract business hours, prices, contact info

### 5. WebSocket Voice (`services/websocket_voice.py`)

- **Full-Duplex Streaming**: Bidirectional audio
- **< 500ms Latency**: Stream-to-stream processing
- **ElevenLabs Integration**: Real-time TTS

---

## 📊 Performance Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Voice Latency | < 500ms | WebSocket round-trip time |
| Swarm Throughput | 5 calls/sec | Concurrent calls via semaphore |
| State Machine P99 | < 100ms | Transition timing |
| OCR Accuracy | > 85% | Confidence score |
| Double-Booking | 0% | Distributed locks |

---

## 🐛 Troubleshooting

### Redis Connection Failed

```
⚠️ Redis not available, using in-memory swarm
```

**Solution:** Install and start Redis, or continue with in-memory mode (works for single-instance testing).

### ElevenLabs API Error

```
ElevenLabs API error: 401
```

**Solution:** Check your API key in `.env`

### Tesseract Not Found

```
Tesseract initialization failed
```

**Solution:** Install Tesseract OCR and set `TESSDATA_PATH`

### WebSocket Connection Refused

```
Connection refused on ws://localhost:8765
```

**Solution:** Set `ENABLE_WEBSOCKET=true` in `.env`

---

## 📈 Next Steps

### Phase 1: Core Testing (Week 1)
- [ ] Test state machine transitions
- [ ] Test swarm with mock providers
- [ ] Test voice agent in mock mode

### Phase 2: Production Integration (Week 2-3)
- [ ] Connect real ElevenLabs API
- [ ] Connect real Twilio for PSTN
- [ ] Set up Redis cluster

### Phase 3: Vision Layer (Week 4)
- [ ] Install Tesseract OCR
- [ ] Test business hours extraction
- [ ] Test price list extraction

### Phase 4: Optimization (Week 5-6)
- [ ] Enable WebSocket streaming
- [ ] Tune LangChain agent
- [ ] Add hallucination validation

---

## 📚 Additional Resources

- [Architecture Documentation](ARCHITECTURE.md)
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [LangChain Documentation](https://python.langchain.com/)
- [ElevenLabs API](https://docs.elevenlabs.io/)
- [Twilio Voice](https://www.twilio.com/docs/voice)

---

**Built with ❤️ using Agentic Swarm Architecture**
