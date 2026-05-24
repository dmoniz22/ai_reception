# AI Receptionist — Technical Implementation Plan
## For AI Coding Agents

---

## 1. Overview

Build a multi-tenant AI phone answering service. Businesses get a phone number that an AI receptionist answers 24/7. Uses Twilio for telephony, Deepgram Voice Agents API for the speech pipeline (STT → LLM → TTS), and Ollama Cloud for the conversation LLM.

**Deployment:** Single Proxmox LXC, Docker Compose, behind existing Traefik at 192.168.68.4.

---

## 2. Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Telephony | Twilio | Phone numbers + audio WebSocket streaming |
| Voice Pipeline | Deepgram Voice Agents API | Unified STT + LLM orchestration + TTS in one WebSocket |
| LLM | Ollama Cloud (your existing sub) | Flat-rate, no per-token cost. Model: deepseek-v4-flash or glm-5.1 |
| TTS | Deepgram Aura (included in Voice Agents) | Good enough for phone calls, included in $4.50/hr pricing |
| App Server | Python Starlette + Uvicorn | Async-first, WebSocket-native (Deepgram's reference uses this) |
| Web Dashboard | Next.js 14 (App Router) + TypeScript + Tailwind | Same stack as Resume Optimizer |
| Database | PostgreSQL 16 (via chronicler-postgres) | Multi-tenant: customers, agents, call logs, billing |
| Billing | Stripe | Same account used for Resume Optimizer |
| Deployment | Docker Compose on LXC | Lightweight, reproducible |
| Reverse Proxy | Existing Traefik at 192.168.68.4 | TLS + routing, already running |

---

## 3. File Structure

```
/opt/ai-reception/
├── docker-compose.yml
├── .env
├── .env.example
├── voice-agent-server/
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── main.py                    # Starlette app entry point
│   ├── config.py                  # Environment variable management
│   ├── session.py                 # VoiceAgentSession — Twilio ↔ Deepgram bridge
│   ├── agent_config.py            # Deepgram agent config builder
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── telephony.py           # POST /incoming-call, WS /twilio
│   │   ├── customers.py           # CRUD for customers
│   │   └── admin.py               # Admin endpoints
│   ├── services/
│   │   ├── __init__.py
│   │   ├── deepgram.py            # Deepgram Agent API client
│   │   ├── twilio_client.py       # Twilio REST API wrapper
│   │   ├── scheduling.py          # Google Calendar integration
│   │   └── billing.py             # Stripe integration
│   └── models/
│       ├── __init__.py
│       ├── customer.py            # Customer table
│       ├── agent_config.py        # Deepgram agent config UUIDs
│       └── call_log.py            # Call records
├── frontend/
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.ts
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx               # Landing page
│   │   ├── pricing/page.tsx
│   │   ├── login/page.tsx
│   │   ├── signup/page.tsx
│   │   └── dashboard/
│   │       ├── layout.tsx
│   │       ├── page.tsx            # Overview
│   │       ├── calls/page.tsx      # Call log
│   │       ├── settings/page.tsx   # Hours, FAQs, greeting
│   │       └── billing/page.tsx
│   └── lib/
│       ├── api-client.ts
│       └── stripe.ts
└── data/
    └── ...                         # Persistent data
```

---

## 4. Database Schema (PostgreSQL)

```sql
-- Customers (one row per business)
CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_name TEXT NOT NULL,
    owner_name TEXT,
    email TEXT UNIQUE NOT NULL,
    phone TEXT,                      -- Owner's mobile for SMS alerts
    timezone TEXT DEFAULT 'America/Vancouver',
    twilio_phone_number TEXT,        -- The AI's outbound number
    deepgram_agent_id UUID,         -- Reusable agent config UUID
    system_prompt TEXT,              -- Customized per business
    business_hours JSONB,            -- e.g. {"mon": "9-5", "tue": "9-5", ...}
    faqs JSONB,                      -- e.g. [{"q": "How much?", "a": "$75/hr"}]
    greeting TEXT,                   -- Custom greeting
    calendar_integration TEXT,       -- 'google_calendar' or NULL
    calendar_credentials JSONB,      -- Encrypted OAuth token
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    status TEXT DEFAULT 'active',    -- active, paused, cancelled
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Call logs
CREATE TABLE call_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id),
    caller_number TEXT NOT NULL,
    call_sid TEXT UNIQUE,            -- Twilio call SID
    started_at TIMESTAMPTZ DEFAULT now(),
    ended_at TIMESTAMPTZ,
    duration_seconds INT,
    transcript_url TEXT,             -- Deepgram transcript
    recording_url TEXT,              -- Call recording
    outcome TEXT,                    -- booked, transferred, message_taken, hung_up
    transferred_to_owner BOOLEAN DEFAULT false,
    summary TEXT,                    -- AI-generated call summary
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Messages left by callers
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_log_id UUID REFERENCES call_logs(id),
    customer_id UUID NOT NULL REFERENCES customers(id),
    caller_name TEXT,
    caller_number TEXT,
    message_text TEXT,
    urgency TEXT DEFAULT 'normal',   -- normal, urgent
    sms_sent_to_owner BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

---

## 5. Deepgram Voice Agent Configuration

### Base Config Template

```python
AGENT_CONFIG_TEMPLATE = {
    "version": "v1",
    "language": "en",
    "listen": {
        "provider": {
            "type": "deepgram",
            "model": "nova-3-general",    # Good accuracy + speed
            "language": "en",
            "smart_format": True,
            "interim_results": True,
        }
    },
    "think": {
        "provider": {
            "type": "custom",             # Custom LLM endpoint
        },
        "endpoint": {
            "url": "https://ollama.com/v1/chat/completions",
            "headers": {
                "Authorization": "Bearer 2bb48b47daa14741a3d9cd5d832d8214.Qpec2vIHYi6mPZpFh2UPhys6"
            },
        },
        "model": "deepseek-v4-flash",
        "prompt": SYSTEM_PROMPT_TEMPLATE,
        "functions": SCHEDULING_FUNCTIONS,
        "context_length": 15000,
        "temperature": 0.5,
    },
    "speak": {
        "provider": {
            "type": "deepgram",
            "model": "aura-2-thalia-en",   # Natural female voice
            "speed": 1.0,
        }
    },
    "greeting": GREETING_TEMPLATE,
}
```

### System Prompt Template

```
You are an AI receptionist for {business_name}. Your job is to:
1. Answer calls professionally and warmly
2. Answer FAQs about hours, pricing, services
3. Schedule appointments (use the schedule_appointment function)
4. Take messages if the owner isn't available
5. Transfer complex calls to the owner (use transfer_to_owner function)

Business name: {business_name}
Hours: {business_hours}
FAQs: {faqs}

Rules:
- Keep responses brief and natural
- If you don't know the answer, say "Let me transfer you to the owner"
- Never make up prices or availability
- Confirm appointment details before booking
- After booking, summarize the appointment for the caller
- If the caller is angry or abusive, stay polite and offer to transfer

Call flow:
1. Greet and identify the business
2. Ask how you can help
3. Handle the request (answer, schedule, or transfer)
4. End the call warmly
```

### Deepgram Agent Functions

```python
SCHEDULING_FUNCTIONS = [
    {
        "name": "check_availability",
        "description": "Check available appointment slots for a given date",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date in YYYY-MM-DD format"}
            },
            "required": ["date"]
        },
        "endpoint": {
            "url": "http://localhost:8000/api/scheduling/availability",
            "method": "post",
            "headers": {
                "Authorization": "Bearer {{INTERNAL_API_KEY}}"
            }
        }
    },
    {
        "name": "book_appointment",
        "description": "Book an appointment for a caller",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string"},
                "time": {"type": "string"},
                "name": {"type": "string", "description": "Caller's name"},
                "phone": {"type": "string", "description": "Caller's phone number"},
                "service": {"type": "string", "description": "Type of appointment"}
            },
            "required": ["date", "time", "name", "phone"]
        },
        "endpoint": {
            "url": "http://localhost:8000/api/scheduling/book",
            "method": "post",
            "headers": {
                "Authorization": "Bearer {{INTERNAL_API_KEY}}"
            }
        }
    },
    {
        "name": "transfer_to_owner",
        "description": "Transfer the call to the business owner",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Why the call needs the owner"}
            },
            "required": ["reason"]
        }
    },
    {
        "name": "take_message",
        "description": "Take a message for the owner when they can't take the call",
        "parameters": {
            "type": "object",
            "properties": {
                "caller_name": {"type": "string"},
                "callback_number": {"type": "string"},
                "message": {"type": "string"}
            },
            "required": ["caller_name", "callback_number", "message"]
        }
    }
]
```

---

## 6. Multi-Tenant Architecture

### Call Routing Flow

```
[Caller] dials Twilio number (+1-555-...)
    │
    ▼
Twilio sends POST /incoming-call to your server
    │ Server looks up which customer owns this number
    │ Server responds with TwiML pointing to WS /twilio/{customer_id}
    │
    ▼
Twilio opens WebSocket to WS /twilio/{customer_id}
    │ Server instantiates VoiceAgentSession
    │ Session connects to Deepgram Voice Agent API
    │ Session sends the customer's specific agent config UUID
    │
    ▼
Audio flows: Twilio ↔ Server ↔ Deepgram (STT + LLM + TTS)
    │
    ▼
Call ends → Server logs call to PostgreSQL
    │ Server sends SMS summary to business owner
```

### Agent Configuration per Customer

Each customer gets their own Deepgram Reusable Agent Configuration:

```python
async def create_customer_agent(customer: dict) -> str:
    """Create a Deepgram Reusable Agent Config for this customer."""
    config = AGENT_CONFIG_TEMPLATE.copy()
    config["think"]["prompt"] = SYSTEM_PROMPT_TEMPLATE.format(
        business_name=customer["business_name"],
        business_hours=customer["business_hours"],
        faqs=customer["faqs"]
    )
    config["greeting"] = customer["greeting"]

    # POST to Deepgram API
    response = await deepgram_client.create_agent_config(
        project_id=DG_PROJECT_ID,
        config=json.dumps(config),
        metadata={"customer_id": customer["id"], "name": customer["business_name"]}
    )
    return response["agent_id"]
```

### Number Provisioning

```python
async def provision_number(customer_id: str, area_code: str = None):
    """Buy a Twilio number and assign it to a customer."""
    # 1. Search for available number
    numbers = twilio_client.available_phone_numbers(area_code)

    # 2. Buy the first available
    number = twilio_client.buy_phone_number(numbers[0])

    # 3. Configure webhook
    twilio_client.configure_voice_url(
        phone_number_sid=number.sid,
        voice_url=f"https://reception.{DOMAIN}/incoming-call/{customer_id}"
    )

    # 4. Save to DB
    await db.execute(
        "UPDATE customers SET twilio_phone_number = $1 WHERE id = $2",
        number.phone_number, customer_id
    )

    return number.phone_number
```

---

## 7. Build Order for a Coding Agent

### Iteration 1: Voice Agent Server (Days 1-3)

```
Goal: Twilio ↔ Deepgram bridge working. You can call a number and talk to the AI.

Files to create:
  docker-compose.yml        # PostgreSQL + voice agent server
  main.py                   # Starlette app, 200 lines
  config.py                 # Env vars: DEEPGRAM_API_KEY, etc.
  session.py                # VoiceAgentSession (bridges Twilio WebSocket ↔ Deepgram)
  agent_config.py           # Agent config builder + function definitions
  routers/telephony.py      # /incoming-call + WS /twilio

Test: python dev_client.py → speak → AI responds
Test: call the Twilio number → speak → AI responds
```

### Iteration 2: Multi-Tenant + Database (Days 4-5)

```
Goal: Multiple customers, each with their own agent config and number.

Files to create:
  models/customer.py         # SQLAlchemy models
  models/call_log.py         # Call log schema
  services/deepgram.py       # Create/get/delete reusable agent configs
  services/twilio_client.py  # Buy number, configure webhook
  routers/customers.py       # POST /api/customers → creates agent + buys number

Test: Create customer via API → verify number works with that customer's prompt
Test: Call number → agent uses that customer's greeting + FAQs
```

### Iteration 3: Scheduling + Messages (Days 6-7)

```
Goal: AI can book appointments and leave messages.

Files to create:
  services/scheduling.py     # Google Calendar API integration
  routers/admin.py           # Internal endpoints for function calls

Update:
  agent_config.py            # Add check_availability + book_appointment functions
  session.py                 # Handle function call responses

Test: "Book an appointment for Tuesday at 2pm" → creates Google Calendar event
Test: "Tell him I'll call back later" → saves message, sends SMS
```

### Iteration 4: Web Dashboard (Days 8-10)

```
Goal: Customers can log in, see calls, update settings.

Files to create:
  frontend/ entirely (Next.js app)

Pages:
  /          → Landing page with demo number to call
  /signup    → Business name, email, hours, FAQs → Stripe checkout
  /dashboard → Call log, transcript viewer
  /settings  → Update hours, FAQs, greeting, voicemail
  /billing   → Subscription management

Test: Sign up → Stripe checkout → number provisioned → call works
```

### Iteration 5: Polish & Deploy (Days 11-12)

```
Goal: Production-ready behind Traefik.

Files to create:
  Dockerfile                 # For voice agent server
  nginx/app.conf or Traefik config

Tasks:
  - Configure Traefik routing for reception.YOURDOMAIN.com
  - TLS via Let's Encrypt (already handled by Traefik)
  - Rate limiting per customer (prevent abuse)
  - Error logging to file
  - Stripe subscription webhooks (cancel = deactivate number)
```

---

## 8. Environment Variables

```
# Deepgram
DEEPGRAM_API_KEY=your_key
DEEPGRAM_PROJECT_ID=your_project_id

# Twilio
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_PHONE_NUMBER_SID=your_number_sid

# Ollama Cloud
OLLAMA_CLOUD_API_KEY=2bb48b47daa14741a3d9cd5d832d8214.Qpec2vIHYi6mPZpFh2UPhys6
OLLAMA_CLOUD_ENDPOINT=https://ollama.com/v1

# Internal
INTERNAL_API_KEY=52fd81dfed8f7576285b27866d574057b450ce9f920343b4750b54b59c750e36

# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/ai_reception

# Stripe
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Domain (for Traefik routing)
DOMAIN=reception.monizhealth.com

# Google Calendar (for scheduling)
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
```

---

## 9. Docker Compose

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    restart: unless-stopped
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: ai_reception
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d ai_reception"]
      interval: 10s
      timeout: 5s
      retries: 5

  server:
    build: ./voice-agent-server
    restart: unless-stopped
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "8000:8000"
    command: uvicorn main:app --host 0.0.0.0 --port 8000

  frontend:
    build: ./frontend
    restart: unless-stopped
    env_file: .env
    depends_on:
      - server
    ports:
      - "3000:3000"
    command: npm run dev

volumes:
  pgdata:
```

---

## 10. Cost Per Customer (Detailed)

| Component | Cost | Notes |
|-----------|------|-------|
| Twilio phone number | $1.15/mo | Local US/Canada number |
| Twilio inbound calls | $0.0085/min | ~100 min/mo avg = $0.85 |
| Deepgram Voice Agents | $4.50/hr | ~5 hrs call time/mo = $22.50 |
| Ollama Cloud | $0 (flat sub) | Already paid |
| PostgreSQL | $0 (self-hosted) | On chronicler-postgres |
| **Total per customer** | **~$24.50/mo** | |

**At $29/mo:** $4.50 gross margin per customer.
**At $39/mo:** $14.50 gross margin per customer.
**At $49/mo:** $24.50 gross margin per customer.

Recommendation: Start at $29/mo for beta (free month), then increase to $39-49/mo after validating value.

---

## 11. Known Pitfalls & Mitigations

| Pitfall | Mitigation |
|---------|-----------|
| Deepgram Voice Agents has cold start (~2-3s first response) | Keep the WebSocket connection warm by pinging every 30s, or accept the 2-3s delay (acceptable for phone calls) |
| Twilio trial disclaimer plays before callers | Upgrade to paid Twilio account ($20 minimum) |
| Ollama Cloud LLM latency adds 0.5-1s per exchange | Use `deepseek-v4-flash` (fastest model). Total pipeline: ~2-2.5s per exchange — acceptable |
| Deepgram Aura TTS is good but not ElevenLabs quality | Phone audio compressed — Aura is good enough. Can swap to ElevenLabs later via config change |
| Google Calendar API requires OAuth per customer | Guide customer through OAuth once during setup. Store encrypted token |
| Twilio number porting is slow (5-10 days) | Start by buying new numbers, port existing numbers later |
| Customer doesn't like the AI voice | Offer voice selection (Aura has 27 voices). Let them preview before going live |
