# CallPilot - Agentic Swarm Architecture (SDE 3 Design)

## 🏗️ System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CALLPILOT ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐                │
│  │   User UI    │     │  Provider    │     │   External   │                │
│  │  (Streamlit) │     │   Phone      │     │   Services   │                │
│  └──────┬───────┘     └──────┬───────┘     └──────┬───────┘                │
│         │                    │                    │                         │
│         ▼                    ▼                    ▼                         │
│  ┌──────────────────────────────────────────────────────────────┐          │
│  │                    API Gateway Layer                          │          │
│  │              (Spring Boot REST + WebSocket)                   │          │
│  └──────────────────────────────────────────────────────────────┘          │
│         │                    │                    │                         │
│         ▼                    ▼                    ▼                         │
│  ┌──────────────────────────────────────────────────────────────┐          │
│  │                 Orchestration Layer                           │          │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  │          │
│  │  │ State Machine  │  │ Swarm          │  │ Distributed    │  │          │
│  │  │ (Call Lifecycle)│  │ Controller     │  │ Lock Manager   │  │          │
│  │  └────────────────┘  └────────────────┘  └────────────────┘  │          │
│  └──────────────────────────────────────────────────────────────┘          │
│         │                    │                    │                         │
│         ▼                    ▼                    ▼                         │
│  ┌──────────────────────────────────────────────────────────────┐          │
│  │                 Agentic AI Layer                              │          │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  │          │
│  │  │ Tool-Calling   │  │ RAG Engine     │  │ Validator      │  │          │
│  │  │ Engine         │  │ (Pinecone)     │  │ Agent          │  │          │
│  │  └────────────────┘  └────────────────┘  └────────────────┘  │          │
│  └──────────────────────────────────────────────────────────────┘          │
│         │                    │                    │                         │
│         ▼                    ▼                    ▼                         │
│  ┌──────────────────────────────────────────────────────────────┐          │
│  │                 Tool Layer                                    │          │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  │          │
│  │  │ Google Calendar│  │ Google Maps    │  │ ElevenLabs     │  │          │
│  │  │ Service        │  │ Service        │  │ Voice AI       │  │          │
│  │  └────────────────┘  └────────────────┘  └────────────────┘  │          │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  │          │
│  │  │ Twilio Service │  │ OpenCV/OCR     │  │ Pinecone DB    │  │          │
│  │  │                │  │ (Vision Layer) │  │                │  │          │
│  │  └────────────────┘  └────────────────┘  └────────────────┘  │          │
│  └──────────────────────────────────────────────────────────────┘          │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────┐          │
│  │                 Infrastructure Layer                          │          │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  │          │
│  │  │ Redis          │  │ RabbitMQ       │  │ PostgreSQL     │  │          │
│  │  │ (State Cache)  │  │ (Message Queue)│  │ (Persistence)  │  │          │
│  │  └────────────────┘  └────────────────┘  └────────────────┘  │          │
│  └──────────────────────────────────────────────────────────────┘          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📋 Table of Contents

1. [Orchestration Layer](#1-orchestration-layer)
2. [Agentic AI Layer](#2-agentic-ai-layer)
3. [Vision/Intelligence Layer](#3-visionintelligence-layer)
4. [Tech Stack](#4-tech-stack)
5. [Data Models](#5-data-models)
6. [API Contracts](#6-api-contracts)
7. [Deployment Architecture](#7-deployment-architecture)

---

## 1. Orchestration Layer

### 1.1 State Machine (Call Lifecycle)

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  INITIATED  │───▶│  RINGING    │───▶│ NEGOTIATING │
└─────────────┘    └─────────────┘    └─────────────┘
       ▲                                    │
       │                                    ▼
       │                             ┌─────────────┐
       │                             │ CONFIRMING  │
       │                             └─────────────┘
       │                                    │
       │              ┌─────────────────────┼─────────────────────┐
       │              │                     │                     │
       ▼              ▼                     ▼                     ▼
┌─────────────┐ ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   FAILED    │ │  COMPLETED  │    │  HANDOVER   │    │  RETRYING   │
└─────────────┘ └─────────────┘    └─────────────┘    └─────────────┘
```

**State Transitions:**
| From | To | Trigger |
|------|-----|---------|
| INITIATED | RINGING | Twilio call initiated |
| RINGING | NEGOTIATING | Provider answered |
| NEGOTIATING | CONFIRMING | Slot identified |
| CONFIRMING | COMPLETED | Booking confirmed |
| NEGOTIATING | HANDOVER | Complex query detected |
| ANY | FAILED | Max retries exceeded |
| FAILED | RETRYING | Retry policy triggered |

### 1.2 Swarm Controller

```java
@Component
public class SwarmController {
    
    private final ExecutorService virtualThreadExecutor;
    private final StateMachineService stateMachineService;
    private final DistributedLockManager lockManager;
    
    /**
     * Spawns multiple worker threads for parallel provider calls
     * Uses Java Virtual Threads (Project Loom) for efficiency
     */
    public SwarmCampaign startSwarm(SwarmRequest request) {
        // 1. Fetch providers from Google Maps
        List<Provider> providers = providerService.findProviders(request);
        
        // 2. Create campaign
        SwarmCampaign campaign = campaignRepository.save(
            SwarmCampaign.builder()
                .userId(request.getUserId())
                .serviceType(request.getServiceType())
                .status(CampaignStatus.INITIATED)
                .targets(providers)
                .build()
        );
        
        // 3. Spawn worker threads (one per provider)
        providers.forEach(provider -> {
            virtualThreadExecutor.submit(() -> 
                executeProviderCall(campaign, provider)
            );
        });
        
        return campaign;
    }
    
    /**
     * Manages single provider call with state tracking
     */
    private void executeProviderCall(SwarmCampaign campaign, Provider provider) {
        CallStateMachine stateMachine = stateMachineService.create(provider);
        
        try {
            // Acquire distributed lock for this provider
            Lock lock = lockManager.acquireLock(
                "provider:" + provider.getId()
            );
            
            // Execute call through state machine
            stateMachine.transition(CallEvent.CALL_INITIATED);
            
            // Voice agent negotiation
            NegotiationResult result = voiceAgent.negotiate(provider);
            
            if (result.isConfirmed()) {
                stateMachine.transition(CallEvent.CONFIRMED);
                campaign.setBestBooking(result);
            } else {
                stateMachine.transition(CallEvent.FAILED);
            }
            
        } catch (Exception e) {
            stateMachine.transition(CallEvent.ERROR);
            log.error("Provider call failed", e);
        }
    }
}
```

### 1.3 Distributed Lock Manager

```java
@Component
public class DistributedLockManager {
    
    @Autowired
    private RedisTemplate<String, String> redisTemplate;
    
    /**
     * Prevents double-booking when multiple swarm calls
     * try to book the same time slot
     */
    public Lock acquireLock(String resource, Duration timeout) {
        String lockKey = "lock:" + resource;
        String lockValue = UUID.randomUUID().toString();
        
        Boolean acquired = redisTemplate.opsForValue()
            .setIfAbsent(lockKey, lockValue, timeout);
        
        if (Boolean.TRUE.equals(acquired)) {
            return new RedisLock(lockKey, lockValue, redisTemplate);
        }
        throw new LockAcquisitionException("Could not acquire lock: " + resource);
    }
    
    /**
     * Lock calendar slot during booking confirmation
     */
    public void lockCalendarSlot(String dateTime) {
        acquireLock("calendar:" + dateTime, Duration.ofMinutes(5));
    }
}
```

---

## 2. Agentic AI Layer

### 2.1 Tool-Calling Engine (Action-RAG Pattern)

```java
@Component
public class SchedulingAgent {
    
    private final LangChain4jAgent agent;
    private final ToolRegistry toolRegistry;
    
    public SchedulingAgent() {
        this.agent = LangChain4j.builder()
            .chatModel(ElevenLabsChatModel.builder()
                .apiKey(System.getenv("ELEVENLABS_API_KEY"))
                .modelName("eleven_turbo_v2")
                .build())
            .tools(toolRegistry.getAllTools())
            .systemMessage("""
                You are a professional appointment scheduling assistant.
                - Always verify calendar availability before offering slots
                - Be polite and professional
                - If provider asks unknown question, trigger HANDOVER
                - Never hallucinate availability - always check tools
                """)
            .build();
    }
    
    /**
     * Tool registry for agent capabilities
     */
    @Component
    public class ToolRegistry {
        
        @Tool("Check user calendar availability for a given date/time")
        public CalendarAvailability checkCalendarAvailability(
            @P("date") String date,
            @P("time") String time
        ) {
            return googleCalendarService.checkAvailability(date, time);
        }
        
        @Tool("Search for service providers near a location")
        public List<Provider> searchNearbyProviders(
            @P("serviceType") String serviceType,
            @P("location") String location,
            @P("radius") int radius
        ) {
            return googleMapsService.searchNearby(serviceType, location, radius);
        }
        
        @Tool("Book appointment on Google Calendar")
        public BookingConfirmation bookAppointment(
            @P("providerName") String providerName,
            @P("dateTime") String dateTime,
            @P("duration") int durationMinutes
        ) {
            return googleCalendarService.bookAppointment(
                providerName, dateTime, durationMinutes
            );
        }
        
        @Tool("Extract business hours from provider image")
        public BusinessHours extractBusinessHours(
            @P("imageUrl") String imageUrl
        ) {
            return visionService.extractBusinessHours(imageUrl);
        }
    }
}
```

### 2.2 RAG Engine (Vector DB Integration)

```java
@Component
public class PreferenceRAGService {
    
    @Autowired
    private PineconeClient pineconeClient;
    
    /**
     * Store user preferences in vector DB for agent retrieval
     */
    public void storeUserPreferences(UserPreferences prefs) {
        Embedding embedding = embeddingModel.embed(prefs.toText());
        
        pineconeClient.upsert(UpsertRequest.newBuilder()
            .addVectors(Vector.newBuilder()
                .setId(prefs.getUserId())
                .addAllValues(embedding.vector())
                .putMetadata("user_id", prefs.getUserId())
                .putMetadata("budget_preference", prefs.getMaxBudget())
                .putMetadata("time_preference", prefs.getTimePreference())
                .putMetadata("quality_priority", prefs.isPrioritizeQuality())
                .build())
            .setNamespace("user_preferences")
            .build());
    }
    
    /**
     * Retrieve relevant preferences during call
     */
    public UserPreferences retrievePreferences(String userId) {
        QueryResponse response = pineconeClient.query(
            QueryRequest.newBuilder()
                .setVector(embeddingModel.embed(userId).vector())
                .setTopK(5)
                .setNamespace("user_preferences")
                .build()
        );
        
        return PreferenceMapper.fromVectorDB(response);
    }
}
```

---

## 3. Vision/Intelligence Layer

### 3.1 CNN-Based OCR for Provider Information

```java
@Component
public class ProviderVisionService {
    
    @Autowired
    private OpenCVService openCVService;
    
    @Autowired
    private TesseractOCRService ocrService;
    
    /**
     * Extract business hours from provider's Google Maps photo
     */
    public BusinessHours extractBusinessHours(String imageUrl) {
        // 1. Download and preprocess image
        Mat image = openCVService.downloadAndPreprocess(imageUrl);
        
        // 2. Enhance contrast for OCR
        Mat enhanced = openCVService.applyCLAHE(image);
        
        // 3. Detect text regions
        List<Rect> textRegions = openCVService.detectTextRegions(enhanced);
        
        // 4. Extract text with Tesseract
        StringBuilder text = new StringBuilder();
        for (Rect region : textRegions) {
            Mat roi = enhanced.submat(region);
            text.append(ocrService.recognize(roi));
        }
        
        // 5. Parse business hours with regex/NLP
        return BusinessHoursParser.parse(text.toString());
    }
    
    /**
     * Extract price list from menu/service photo
     */
    public PriceList extractPriceList(String imageUrl) {
        Mat image = openCVService.downloadAndPreprocess(imageUrl);
        
        // Use CNN model trained on price list detection
        PriceListDetection detection = cnnModel.detect(image);
        
        return detection.getPriceList();
    }
}
```

### 3.2 OpenCV Preprocessing Pipeline

```java
@Component
public class OpenCVService {
    
    static {
        System.loadLibrary(Core.NATIVE_LIBRARY_NAME);
    }
    
    /**
     * Preprocess image for optimal OCR results
     */
    public Mat preprocessForOCR(Mat image) {
        Mat result = new Mat();
        
        // 1. Convert to grayscale
        Imgproc.cvtColor(image, result, Imgproc.COLOR_BGR2GRAY);
        
        // 2. Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
        CLAHE clahe = Imgproc.createCLAHE(2.0, new Size(8, 8));
        clahe.apply(result, result);
        
        // 3. Denoise
        Imgproc.medianBlur(result, result, 3);
        
        // 4. Threshold (Otsu's binarization)
        Imgproc.threshold(result, result, 0, 255, 
            Imgproc.THRESH_BINARY + Imgproc.THRESH_OTSU);
        
        return result;
    }
    
    /**
     * Detect text regions using MSER (Maximally Stable Extremal Regions)
     */
    public List<Rect> detectTextRegions(Mat image) {
        MSER mser = MSER.create();
        List<List<Point>> regions = new ArrayList<>();
        mser.detectRegions(image, regions);
        
        return regions.stream()
            .map(this::pointsToRect)
            .filter(this::isTextLikeRegion)
            .collect(Collectors.toList());
    }
}
```

---

## 4. Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Backend Framework** | Spring Boot 3.2 + Virtual Threads | High-concurrency call handling |
| **State Machine** | Spring State Machine | Call lifecycle management |
| **AI/LLM** | LangChain4j + ElevenLabs | Tool-calling agent |
| **Vector DB** | Pinecone | User preference RAG |
| **Cache/Locks** | Redis | Distributed locking, state cache |
| **Message Queue** | RabbitMQ | Swarm task distribution |
| **Database** | PostgreSQL | Persistent storage |
| **Voice** | ElevenLabs + Twilio | Voice AI + PSTN connectivity |
| **Maps** | Google Maps API | Provider discovery |
| **Calendar** | Google Calendar API | Availability checking |
| **Vision** | OpenCV + Tesseract | OCR for provider images |
| **Frontend** | Streamlit (Python) / React | User interface |

---

## 5. Data Models

### 5.1 Core Entities

```java
@Entity
@Table(name = "swarm_campaigns")
public class SwarmCampaign {
    @Id
    private UUID id;
    
    private String userId;
    private String serviceType;
    private CampaignStatus status;
    
    @OneToMany(mappedBy = "campaign", cascade = CascadeType.ALL)
    private List<ProviderCallResult> callResults;
    
    private ProviderCallResult bestBooking;
    
    private LocalDateTime createdAt;
    private LocalDateTime completedAt;
}

@Entity
@Table(name = "provider_call_results")
public class ProviderCallResult {
    @Id
    private UUID id;
    
    @ManyToOne
    private SwarmCampaign campaign;
    
    private String providerId;
    private String providerName;
    private String providerPhone;
    
    private CallStatus status;
    private String transcript;
    
    private String bookedDate;
    private String bookedTime;
    private Double priceQuoted;
    
    private LocalDateTime callStartedAt;
    private LocalDateTime callEndedAt;
}

@Entity
@Table(name = "call_state_machines")
public class CallStateMachine {
    @Id
    private UUID id;
    
    private String callSid;
    private CallState currentState;
    
    @ElementCollection
    private List<CallStateTransition> transitionHistory;
    
    private String providerId;
    private String campaignId;
}
```

### 5.2 State Machine Configuration

```java
@Configuration
@EnableStateMachineFactory
public class CallStateMachineConfig 
    extends EnumStateMachineConfigurerAdapter<CallState, CallEvent> {
    
    @Override
    public void configure(StateMachineStateConfigurer<CallState, CallEvent> states) {
        states.withStates()
            .initial(CallState.INITIATED)
            .states(EnumSet.allOf(CallState.class))
            .end(CallState.COMPLETED)
            .end(CallState.FAILED);
    }
    
    @Override
    public void configure(StateMachineTransitionConfigurer<CallState, CallEvent> transitions) {
        transitions
            .from(CallState.INITIATED)
                .event(CallEvent.CALL_INITIATED)
                .to(CallState.RINGING)
            .and()
            .from(CallState.RINGING)
                .event(CallEvent.PROVIDER_ANSWERED)
                .to(CallState.NEGOTIATING)
            .and()
            .from(CallState.NEGOTIATING)
                .event(CallEvent.SLOT_IDENTIFIED)
                .to(CallState.CONFIRMING)
            .and()
            .from(CallState.CONFIRMING)
                .event(CallEvent.CONFIRMED)
                .to(CallState.COMPLETED)
            .and()
            .from(CallState.NEGOTIATING)
                .event(CallEvent.HANDOVER_REQUESTED)
                .to(CallState.HANDOVER);
    }
}
```

---

## 6. API Contracts

### 6.1 REST Endpoints

```yaml
openapi: 3.0.3
info:
  title: CallPilot API
  version: 2.0.0

paths:
  /api/v2/swarm:
    post:
      summary: Start swarm campaign
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/SwarmRequest'
      responses:
        '200':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SwarmCampaignResponse'
  
  /api/v2/swarm/{campaignId}:
    get:
      summary: Get campaign status
      parameters:
        - name: campaignId
          in: path
          required: true
          schema:
            type: string
            format: uuid
  
  /api/v2/calls/{callId}/state:
    get:
      summary: Get call state machine status
  
  /api/v2/voice/websocket:
    get:
      summary: WebSocket endpoint for real-time voice streaming
      servers:
        - url: wss://api.callpilot.com

components:
  schemas:
    SwarmRequest:
      type: object
      properties:
        userId:
          type: string
        serviceType:
          type: string
        location:
          type: string
        maxBudget:
          type: number
        maxProviders:
          type: integer
          default: 5
```

### 6.2 WebSocket Voice Streaming

```java
@ServerEndpoint("/voice/stream")
@Component
public class VoiceWebSocketHandler {
    
    private final ConcurrentMap<String, Session> activeSessions = 
        new ConcurrentHashMap<>();
    
    @OnOpen
    public void onOpen(Session session) {
        activeSessions.put(session.getId(), session);
    }
    
    @OnMessage
    public void onMessage(byte[] audioData, Session session) {
        // 1. Receive audio from ElevenLabs
        // 2. Stream to Twilio
        // 3. Process provider response
        // 4. Send back AI response audio
    }
    
    /**
     * Full-duplex streaming with < 500ms latency
     */
    public void streamToTwilio(String callSid, byte[] audioChunk) {
        TwilioConnection connection = connections.get(callSid);
        if (connection != null) {
            connection.sendMedia(audioChunk);
        }
    }
}
```

---

## 7. Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Kubernetes Cluster                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Ingress Controller                     │   │
│  │              (NGINX + SSL Termination)                    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│         ┌────────────────────┼────────────────────┐             │
│         ▼                    ▼                    ▼             │
│  ┌─────────────┐      ┌─────────────┐     ┌─────────────┐       │
│  │   API       │      │  WebSocket  │     │   Worker    │       │
│  │  Service    │      │   Service   │     │   Nodes     │       │
│  │  (x3 pods)  │      │   (x2 pods) │     │   (x5 pods) │       │
│  └─────────────┘      └─────────────┘     └─────────────┘       │
│         │                    │                    │             │
│         └────────────────────┼────────────────────┘             │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   Redis Cluster                           │   │
│  │         (State Cache + Distributed Locks)                 │   │
│  └──────────────────────────────────────────────────────────┘   │
│         │                    │                    │             │
│         ▼                    ▼                    ▼             │
│  ┌─────────────┐      ┌─────────────┐     ┌─────────────┐       │
│  │  PostgreSQL │      │   Pinecone  │     │  RabbitMQ   │       │
│  │  (Primary)  │      │  (Vector)   │     │   (Queue)   │       │
│  └─────────────┘      └─────────────┘     └─────────────┘       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8. Migration Path (Python → Java)

### Phase 1: Core Logic Migration (Week 1-2)
1. Set up Spring Boot project
2. Migrate provider search (Google Maps)
3. Migrate ranking algorithm
4. Migrate calendar service

### Phase 2: State Machine & Swarm (Week 3-4)
1. Implement Spring State Machine
2. Build distributed swarm controller
3. Add Redis for distributed locking
4. Add RabbitMQ for task queuing

### Phase 3: Agentic AI (Week 5-6)
1. Integrate LangChain4j
2. Build tool-calling engine
3. Set up Pinecone RAG
4. Implement validator agent

### Phase 4: Voice & Vision (Week 7-8)
1. WebSocket voice streaming
2. OpenCV/OCR integration
3. Hallucination detection
4. User handover (SIP transfer)

---

## 9. Key Performance Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Voice Latency | < 500ms | WebSocket round-trip |
| Swarm Throughput | 10 calls/sec | Virtual threads |
| State Machine P99 | < 100ms | Transition time |
| RAG Retrieval | < 50ms | Pinecone query |
| OCR Processing | < 2sec | Image to structured data |
| Double-Booking | 0% | Distributed locks |

---

## 10. Error Handling & Resilience

### 10.1 Retry Policy
```java
@Configuration
public class RetryConfig {
    
    @Bean
    public RetryTemplate retryTemplate() {
        return RetryTemplate.builder()
            .maxAttempts(3)
            .exponentialBackoff(100, 2, 1000)
            .retryOn(CallException.class)
            .build();
    }
}
```

### 10.2 Circuit Breaker
```java
@Service
public class ProviderService {
    
    @CircuitBreaker(name = "googleMaps", fallbackMethod = "fallbackSearch")
    public List<Provider> searchNearby(String serviceType, String location) {
        return googleMapsClient.search(serviceType, location);
    }
    
    public List<Provider> fallbackSearch(String serviceType, String location, 
                                          Throwable ex) {
        return cachedProviderSearch(serviceType, location);
    }
}
```

### 10.3 Hallucination Validator
```java
@Component
public class HallucinationValidator {
    
    private final ChatModel validatorModel;
    
    /**
     * Post-call validation using second LLM
     */
    public ValidationResult validate(CallTranscript transcript, 
                                      BookingResult result) {
        String prompt = """
            Review this call transcript and booking result.
            Did the provider actually confirm the appointment?
            
            Transcript: %s
            Booking Result: %s
            
            Respond with: CONFIRMED, AMBIGUOUS, or HALLUCINATION
            """.formatted(transcript.getText(), result.toString());
        
        String response = validatorModel.generate(prompt);
        return ValidationResult.parse(response);
    }
}
```

---

**Built with ❤️ by SDE 3 Architecture**
