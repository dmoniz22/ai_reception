# AI Receptionist

**24/7 AI phone answering for small businesses.** A multi-tenant micro-SaaS that answers calls, books appointments, takes messages, and only transfers complex issues to the owner.

[![GitHub](https://img.shields.io/badge/github-dmoniz22/ai__reception-blue)](https://github.com/dmoniz22/ai_reception)

---

## Architecture

```
 ┌──────────┐     Call      ┌──────────┐    WebSocket    ┌───────────┐
 │  Caller  │ ──────────────→│  Twilio  │ ──────────────→│  Server   │
 │          │← - - - - - - - │          │← - - - - - - - │ (Python)  │
 └──────────┘    Audio       └──────────┘    μ-law ↔ L16  └─────┬─────┘
                                                          │    │ async
                                                    ┌─────┘    │ tasks
                                                    │          │
                                              ┌─────▼──────┐   │
                                              │  Deepgram  │   │
                                              │Voice Agent │   │
                                              │STT+LLM+TTS │   │
                                              └────────────┘   │
                                                                │
 ┌──────────┐    HTTP/HTTPS    ┌──────────┐                    │
 │ Browser  │ ────────────────→│ Next.js  │                    │
 │Dashboard │← - - - - - - - - │ Frontend │← ─ ─ ─ ─ ─ ─ ─ ─ ┘
 └──────────┘                  └────┬─────┘     REST API
                                    │
                              ┌─────▼──────┐
                              │ PostgreSQL │
                              │    16      │
                              └────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Telephony | Twilio (phone numbers + audio streaming) |
| Voice Pipeline | Deepgram Voice Agents API (STT + LLM + TTS) |
| LLM | Ollama Cloud (deepseek-v4-flash) |
| Voice Server | Python 3.12 + Starlette + Uvicorn (async, WebSocket-native) |
| Frontend | Next.js 16 + TypeScript + Tailwind CSS + shadcn/ui |
| Auth | NextAuth.js v5 (credentials provider, JWT) |
| Database | PostgreSQL 16 + pgvector (SQLAlchemy async + Prisma) |
| Billing | Stripe (Checkout, Customer Portal, Webhooks) |
| Deployment | Docker Compose on Proxmox LXC behind Traefik |

---

## Prerequisites

### Accounts & API Keys

You need paid/active accounts for the following:

| Service | Purpose | Sign Up |
|---------|---------|---------|
| Twilio | Buy phone numbers, receive calls, send SMS | [twilio.com](https://twilio.com) |
| Deepgram | Voice Agents API (STT + LLM orchestration + TTS) | [deepgram.com](https://deepgram.com) |
| Ollama Cloud | LLM for conversation + call summaries | `ollama.com` |
| Stripe | Subscription billing | [stripe.com](https://stripe.com) |
| Google Cloud | Calendar API for appointment scheduling | [console.cloud.google.com](https://console.cloud.google.com) |

**Twilio minimum setup:**
- Fund account with $20 to remove trial disclaimer on calls
- After signup, get your Account SID, Auth Token, and buy a phone number

**Deepgram setup:**
- Create a project at [console.deepgram.com](https://console.deepgram.com)
- Note your API Key and Project ID
- Voice Agents is billed at $4.50/hr of call time

**Google Cloud setup (for scheduling):**
- Create a project, enable Google Calendar API
- Create OAuth 2.0 credentials (Web application type)
- Set redirect URI to `https://reception.YOURDOMAIN.com/api/scheduling/oauth/callback`

### Software

- **Python 3.12+** (for voice server)
- **Node.js 22+** (for frontend)
- **Docker** + **Docker Compose** (for production deployment)
- **PostgreSQL 16** (local dev; Docker provides it in production)

### Ports

The app uses these ports. Ensure they're free on your machine:

| Service | Port |
|---------|------|
| Voice server | **8001** |
| Frontend | **3002** |
| PostgreSQL | 5432 (Docker internal) |

To check used ports: `ss -tlnp | grep -E ':8001|:3002'`

---

## Quick Start (Local Development)

### 1. Clone the repo

```bash
git clone git@github.com:dmoniz22/ai_reception.git
cd ai_reception
```

### 2. Set up environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your API keys. See [Environment Variables](#environment-variables) for details on each variable.

### 3. Set up the voice server

```bash
cd voice-agent-server

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 4. Set up PostgreSQL

You need a running PostgreSQL instance. Options:

**Option A — Docker (recommended):**
```bash
docker run -d --name ai_reception_db \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=ai_reception \
  -p 5434:5432 \
  pgvector/pgvector:pg16
```
Then set `DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5434/ai_reception` in `.env`.

**Option B — Existing PostgreSQL:**
Create the database manually and point `DATABASE_URL` at it.

### 5. Start the voice server

```bash
cd voice-agent-server
source .venv/bin/activate
python main.py
```

Server starts on `http://localhost:8001`. Verify: `curl http://localhost:8001/health` → `{"status":"ok"}`

### 6. Set up the frontend

```bash
cd frontend
npm install
```

Create `frontend/.env.local`:
```
DATABASE_URL=postgresql://postgres:postgres@localhost:5434/ai_reception
NEXTAUTH_SECRET=any-random-string-for-dev
NEXTAUTH_URL=http://localhost:3002
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRICE_ID=
NEXT_PUBLIC_API_URL=http://localhost:8001
```

### 7. Generate Prisma client

```bash
cd frontend
npx prisma generate
```

### 8. Start the frontend

```bash
cd frontend
npm run dev -- -p 3002
```

Frontend starts on `http://localhost:3002`.

---

## Testing the Voice Pipeline

### Local test (no phone required)

```bash
cd voice-agent-server
pip install pyaudio  # optional; only needed for dev_client.py
python dev_client.py
```

Speak into your microphone. You'll hear the AI respond through your speakers. Press Ctrl+C to exit.

### With a real phone call

1. Buy a Twilio number (or use one you already own)
2. Configure the number's voice webhook in Twilio Console:
   - **When a call comes in:** Webhook → `https://YOUR_DOMAIN/incoming-call`
   - **HTTP Method:** POST
3. Call the number — the AI answers

If testing locally (no public domain), use [ngrok](https://ngrok.com) to expose your server:
```bash
ngrok http 8001
```
Then set the Twilio webhook to `https://YOUR_NGROK_URL/incoming-call`.

---

## Environment Variables

### Required

| Variable | Description |
|----------|-------------|
| `DEEPGRAM_API_KEY` | Deepgram API key (from console.deepgram.com) |
| `DEEPGRAM_PROJECT_ID` | Deepgram project ID |
| `TWILIO_ACCOUNT_SID` | Twilio Account SID |
| `TWILIO_AUTH_TOKEN` | Twilio Auth Token |
| `TWILIO_PHONE_NUMBER_SID` | SID of your Twilio phone number (for SMS) |
| `OLLAMA_CLOUD_API_KEY` | Ollama Cloud API key |
| `INTERNAL_API_KEY` | Random secret key for Deepgram→server function calls |
| `DATABASE_URL` | PostgreSQL connection string (asyncpg for server) |
| `NEXTAUTH_SECRET` | Random string for NextAuth session encryption |
| `NEXTAUTH_URL` | Public URL of the frontend (e.g. `https://reception.monizhealth.com`) |

### Optional (for specific features)

| Variable | Feature | Description |
|----------|---------|-------------|
| `STRIPE_SECRET_KEY` | Billing | Stripe secret key |
| `STRIPE_WEBHOOK_SECRET` | Billing | Stripe webhook signing secret |
| `STRIPE_PRICE_ID` | Billing | Stripe price ID for subscription |
| `GOOGLE_OAUTH_CLIENT_ID` | Scheduling | Google OAuth client ID |
| `GOOGLE_OAUTH_CLIENT_SECRET` | Scheduling | Google OAuth client secret |
| `DOMAIN` | Multi-tenant | Domain for webhook URLs (default: `reception.monizhealth.com`) |
| `OLLAMA_CLOUD_ENDPOINT` | LLM | Ollama API endpoint (default: `https://api.ollama.com/v1`) |
| `HOST` | Server | Bind address (default: `0.0.0.0`) |
| `PORT` | Server | Server port (default: `8001`) |

---

## Docker Deployment

### 1. Configure environment

```bash
cp .env.example .env
# Edit .env with your production API keys
```

The Docker Compose file uses `env_file: .env` so all variables are injected.

### 2. Build and start

```bash
docker compose up -d --build
```

This starts three services:
- `postgres` — PostgreSQL 16 with pgvector
- `server` — Voice agent server (port 8001)
- `frontend` — Next.js dashboard (port 3002)

### 3. Verify

```bash
# Check all services are healthy
docker compose ps

# Test the voice server
curl http://localhost:8001/health

# Check frontend
curl -I http://localhost:3002
```

### 4. View logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f server
```

Logs are structured JSON for easy ingestion into monitoring tools.

### 5. Stop

```bash
docker compose down
```

Add `-v` to remove the database volume (destroys all data).

---

## Traefik Configuration

This app runs behind Traefik on a separate LXC at `192.168.68.4`. Add these routes to your Traefik dynamic file configuration:

```yaml
http:
  routers:
    ai-reception-frontend:
      rule: "Host(`reception.YOURDOMAIN.com`)"
      service: ai-reception-frontend
      tls:
        certResolver: letsencrypt

    ai-reception-api:
      rule: "Host(`api.reception.YOURDOMAIN.com`)"
      service: ai-reception-api
      tls:
        certResolver: letsencrypt

  services:
    ai-reception-frontend:
      loadBalancer:
        servers:
          - url: "http://LXC_IP:3002"

    ai-reception-api:
      loadBalancer:
        servers:
          - url: "http://LXC_IP:8001"
```

Replace `YOURDOMAIN.com` with your domain and `LXC_IP` with the IP of the LXC running this Docker Compose stack.

---

## Project Structure

```
ai_reception/
├── docker-compose.yml              # Production orchestration
├── .env.example                    # All required env vars documented
├── .gitignore
│
├── voice-agent-server/             # Python — call handling & API
│   ├── main.py                     # Starlette app entry point
│   ├── config.py                   # Typed env vars (pydantic-settings)
│   ├── session.py                  # Twilio ↔ Deepgram WebSocket bridge
│   ├── agent_config.py             # Deepgram agent settings + functions
│   ├── dev_client.py               # Local mic+speaker test harness
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── middleware/
│   │   ├── rate_limit.py           # Per-IP rate limiting
│   │   └── logging.py              # Structured JSON logging
│   ├── models/
│   │   ├── database.py             # SQLAlchemy async engine
│   │   ├── customer.py             # Customer table
│   │   └── call_log.py             # CallLog + Message tables
│   ├── services/
│   │   ├── deepgram.py             # Deepgram agent config management
│   │   ├── twilio_client.py        # Twilio number provisioning + SMS
│   │   ├── scheduling.py           # Google Calendar OAuth + API
│   │   └── billing.py              # Stripe webhook handling
│   └── routers/
│       ├── telephony.py            # /incoming-call + WS /twilio
│       ├── customers.py            # Customer CRUD API
│       ├── admin.py                # Scheduling endpoints + OAuth
│       └── health.py               # GET /health
│
├── frontend/                       # Next.js 16 — web dashboard
│   ├── app/
│   │   ├── page.tsx                # Landing page
│   │   ├── layout.tsx              # Root layout
│   │   ├── login/page.tsx          # NextAuth sign-in
│   │   ├── signup/page.tsx         # Registration + Stripe checkout
│   │   ├── pricing/page.tsx
│   │   ├── api/
│   │   │   ├── auth/[...nextauth]/  # NextAuth route handler
│   │   │   ├── signup/             # User registration
│   │   │   └── stripe/             # Checkout + webhook
│   │   └── (dashboard)/
│   │       ├── layout.tsx          # Dashboard shell (sidebar + header)
│   │       ├── page.tsx            # Stats overview
│   │       ├── calls/page.tsx      # Call log + transcript viewer
│   │       ├── settings/page.tsx   # Hours, FAQs, greeting
│   │       └── billing/page.tsx    # Subscription management
│   ├── components/
│   │   ├── ui/                     # shadcn/ui primitives
│   │   ├── landing/                # Hero, features, pricing, demo
│   │   ├── dashboard/              # Sidebar, header
│   │   └── providers.tsx           # Session + theme providers
│   ├── lib/
│   │   ├── auth.ts                 # NextAuth configuration
│   │   ├── db.ts                   # Prisma client singleton
│   │   ├── stripe.ts               # Stripe server client
│   │   ├── api-client.ts           # Typed API fetch wrapper
│   │   └── utils.ts                # cn(), formatters
│   ├── prisma/
│   │   └── schema.prisma           # Database schema
│   └── Dockerfile                  # Production build (standalone output)
│
├── ROADMAP.md                      # Product vision + phases
├── IMPLEMENTATION.md               # Original technical spec
├── IMPLEMENTATION_PLAN.md          # Detailed build plan
└── README.md                       # This file
```

---

## API Reference

All endpoints are served by the voice server on port `8001`.

### Health

```
GET /health
→ 200 {"status": "ok"}
```

### Customer Management (internal admin API)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/customers` | List all customers |
| `POST` | `/api/customers` | Create customer + provision Twilio number + Deepgram agent |
| `GET` | `/api/customers/{id}` | Get customer details |
| `PUT` | `/api/customers/{id}` | Update customer settings |
| `DELETE` | `/api/customers/{id}` | Remove customer + release resources |
| `GET` | `/api/customers/{id}/calls` | Get call log for customer |

**Create customer example:**
```bash
curl -X POST http://localhost:8001/api/customers \
  -H "Content-Type: application/json" \
  -d '{
    "business_name": "Acme Plumbing",
    "owner_name": "John Smith",
    "email": "john@acmeplumbing.com",
    "timezone": "America/Vancouver",
    "area_code": "604",
    "business_hours": {"mon": "9-5", "tue": "9-5", "wed": "9-5", "thu": "9-5", "fri": "9-5"},
    "faqs": [{"q": "What are your rates?", "a": "$75/hr plus materials"}],
    "greeting": "Hello, you've reached Acme Plumbing. How can I help you today?"
  }'
```

### Call Handling (Twilio)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/incoming-call` | Twilio voice webhook (returns TwiML) |
| `POST` | `/incoming-call/{customer_id}` | Customer-specific webhook |
| `WS` | `/twilio` | Twilio Media Streams WebSocket |
| `WS` | `/twilio/{customer_id}` | Customer-specific Media Streams |

### Scheduling (authenticated with `INTERNAL_API_KEY`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/scheduling/{customer_id}/availability` | Check available slots |
| `POST` | `/api/scheduling/{customer_id}/book` | Book an appointment |
| `GET` | `/api/scheduling/oauth/authorize` | Start Google OAuth flow |
| `GET` | `/api/scheduling/oauth/callback` | Google OAuth callback |

These endpoints require `Authorization: Bearer {INTERNAL_API_KEY}` header.

---

## Phone Number Provisioning

When you create a customer via `POST /api/customers`, the server automatically:

1. Creates a customer record in PostgreSQL
2. Creates a Deepgram reusable agent configuration (with the customer's business name, hours, FAQs, greeting)
3. Purchases a Twilio phone number in the requested area code
4. Configures the number's voice webhook to point to your server
5. Saves everything in the database

The customer's AI phone number is returned in the response.

---

## Call Flow

```
1. Caller dials the business's Twilio number
2. Twilio sends POST to /incoming-call/{customer_id}
3. Server returns TwiML with <Stream> pointing to WS /twilio/{customer_id}
4. Twilio opens WebSocket, streams audio (μ-law, 8kHz)
5. Server bridges audio to Deepgram Voice Agent (linear16, 24kHz)
6. Deepgram handles STT → LLM → TTS in a single WebSocket
7. AI converses with caller using the business's custom prompt, FAQs, and greeting
8. Function calls (schedule, message, transfer) are dispatched to internal APIs
9. When call ends: server saves call log, generates LLM summary, sends SMS to owner
```

---

## Rate Limiting & Concurrency

| Limit | Value |
|-------|-------|
| HTTP requests per IP | 120/minute |
| Concurrent calls per customer | 3 max |

Exceeding rate limits returns HTTP 429.

---

## Troubleshooting

### Voice server fails to connect to Deepgram
- Verify `DEEPGRAM_API_KEY` and `DEEPGRAM_PROJECT_ID` in `.env`
- Check your Deepgram account has Voice Agents enabled
- Test: `curl -H "Authorization: Token {KEY}" https://api.deepgram.com/v1/projects/{ID}`

### Twilio call doesn't reach the server
- Verify the Twilio number's voice webhook URL is reachable from the internet
- For local testing, use ngrok: `ngrok http 8001`
- Check server logs: `docker compose logs -f server`

### AI gives generic responses, not business-specific
- Verify the customer has a `deepgram_agent_id` in the database
- The agent config is created when the customer is provisioned
- If missing, recreate: `PUT /api/customers/{id}` which regenerates the agent config

### Frontend can't connect to API
- Verify `NEXT_PUBLIC_API_URL` is set correctly
- For Docker: `NEXT_PUBLIC_API_URL=http://server:8001`
- For local dev: `NEXT_PUBLIC_API_URL=http://localhost:8001`
- Check CORS is configured (allowed origins are set in `main.py`)

### "Calendar not connected" in scheduling
- Run the OAuth flow: visit `/api/scheduling/oauth/authorize?customer_id={ID}`
- Verify `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET` are set
- Check the redirect URI matches what's configured in Google Cloud Console

### Database connection issues
- Docker: PostgreSQL is at `postgres:5432` (container name)
- Local: use your PostgreSQL host/port
- Check `DATABASE_URL` format is correct for your environment

---

## License

MIT
