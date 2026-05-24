# AI Receptionist — Full Implementation Plan

## Tech Stack Decision

| Layer | Choice | 
|-------|--------|
| Voice Server | Python 3.12 + Starlette + Uvicorn (async, WebSocket-native) |
| Frontend | Next.js 14 (App Router) + TypeScript + Tailwind CSS + shadcn/ui |
| Auth | NextAuth.js (email/password credentials provider) |
| Database | PostgreSQL 16 with Prisma ORM (frontend/API) + SQLAlchemy async (voice server) |
| Billing | Stripe (Checkout + Customer Portal + Webhooks) |
| Deployment | Docker Compose on Proxmox LXC behind existing Traefik |

---

## Frontend Design System (shadcn/ui)

All UI built with shadcn/ui components — a modern, accessible component library built on Radix primitives with Tailwind. Components are responsive by default. Dashboard layout uses a collapsible sidebar (desktop) / sheet drawer (mobile). Color theme: dark professional (`slate` base, `blue` accent).

**Key shadcn/ui components used:**
`Button`, `Card`, `Input`, `Label`, `Separator`, `Sheet`, `Sidebar`, `DataTable`, `Dialog`, `DropdownMenu`, `Form`, `Select`, `Switch`, `Tabs`, `Toast`, `Badge`, `Avatar`, `Skeleton`, `Table`

**Responsive breakpoints:**
- Mobile (< 768px): Single column, sidebar → Sheet, tables → cards
- Tablet (768px-1024px): 2-column grids where appropriate
- Desktop (> 1024px): Full sidebar, multi-column layouts

---

## Iteration 1 — Voice Agent Server (Days 1-3)

**Goal:** A single Twilio number that an AI answers end-to-end. No dashboard, no multi-tenancy.

### Files

```
voice-agent-server/
├── requirements.txt
├── Dockerfile
├── main.py                  # Starlette app, mount routers
├── config.py                # All env vars typed with pydantic-settings
├── session.py               # VoiceAgentSession: bridges Twilio WS ↔ Deepgram WS
├── agent_config.py          # Build Deepgram agent config + function definitions
├── routers/
│   ├── __init__.py
│   └── telephony.py         # POST /incoming-call → TwiML, WS /twilio
└── dev_client.py            # Local test client (mic+speaker, no phone needed)
```

### Key Details

**`config.py`** — Use `pydantic-settings` for typed env var access:
- `DEEPGRAM_API_KEY`, `DEEPGRAM_PROJECT_ID`
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`
- `OLLAMA_CLOUD_API_KEY`, `OLLAMA_CLOUD_ENDPOINT`
- `HOST`, `PORT`

**`session.py`** — The core bridge. Two concurrent async tasks connected by `asyncio.Queue`:
- Task 1: Read audio from Twilio WebSocket → forward to Deepgram WebSocket
- Task 2: Read audio from Deepgram WebSocket → forward to Twilio WebSocket

Use `websockets` library (not Starlette's built-in) for the Deepgram connection since the Starlette WS and Deepgram WS have different lifecycles.

**`routers/telephony.py`** — Two endpoints:
1. `POST /incoming-call` — Returns TwiML XML pointing to `wss://<host>/twilio`
2. `WS /twilio` — Accepts Twilio Media Streams, creates `VoiceAgentSession`

**`agent_config.py`** — Hardcoded single config for now (multi-tenant UUIDs come in Iteration 2). Embed the system prompt, functions, and voice settings from the design spec.

**`dev_client.py`** — Local test harness: captures mic via PyAudio, sends to `ws://localhost:8000/twilio`, plays returned audio through speakers.

### Verification
- [ ] `python dev_client.py` → speak into mic → hear AI response through speakers
- [ ] Call the Twilio phone number → AI answers, can hold a conversation
- [ ] End-to-end latency under 3s per exchange

---

## Iteration 2 — Multi-Tenant + Database (Days 4-5)

**Goal:** Multiple businesses. Each gets their own Deepgram agent config UUID, their own Twilio number, their own prompt customization.

### Files

```
voice-agent-server/
├── models/
│   ├── __init__.py
│   ├── database.py           # SQLAlchemy async engine + session factory
│   ├── customer.py           # Customer SQLAlchemy model
│   └── call_log.py           # CallLog + Message models
├── services/
│   ├── __init__.py
│   ├── deepgram.py           # Create/get/delete Deepgram Reusable Agent Configs
│   └── twilio_client.py      # Buy numbers, configure webhooks, send SMS
├── routers/
│   ├── customers.py          # POST/GET /api/customers (internal admin API)
│   └── health.py             # GET /health
└── main.py                   # Updated: init DB, mount new routers
```

### Database

Use the schema from the design spec (`customers`, `call_logs`, `messages`). Add Alembic for migrations.

**Key change to `routers/telephony.py`**: 
- `POST /incoming-call/{customer_id}` — Looks up customer by ID, responds with TwiML
- `WS /twilio/{customer_id}` — Loads that customer's Deepgram agent ID, passes it to `VoiceAgentSession`

### Multi-Tenant Flow

1. Admin calls `POST /api/customers` with `{business_name, email, timezone}`
2. Server creates DB row → calls Deepgram API to create reusable agent config → saves `deepgram_agent_id`
3. Server calls Twilio API to buy a number → configures voice webhook → saves `twilio_phone_number`
4. Admin sees the new phone number, hands it to the customer
5. When that number is dialed, Twilio hits `POST /incoming-call/{customer_id}`, server routes to the right agent

### Built-in Admin API (minimal)
- `POST /api/customers` — Create customer + provision everything
- `GET /api/customers` — List all customers
- `GET /api/customers/{id}` — Single customer details
- `DELETE /api/customers/{id}` — Teardown (release number, delete agent config)
- `GET /api/customers/{id}/calls` — Call log for a customer

### Verification
- [ ] `POST /api/customers` → new number assigned → call that number → AI uses that business's prompt
- [ ] Create 2 customers with different FAQs → call each → AI answers differently
- [ ] Call logs populated in DB with caller number, duration, transcript URL

---

## Iteration 3 — Scheduling + Messages (Days 6-7)

**Goal:** AI can check availability, book appointments on Google Calendar, and take messages. SMS summary sent to owner after each call.

### Files

```
voice-agent-server/
├── services/
│   ├── scheduling.py         # Google Calendar API client
│   └── billing.py            # Stripe integration (subscription status check)
├── routers/
│   └── admin.py              # POST /api/scheduling/availability, /book
└── session.py                # Updated: handle function calls, log messages
```

### Function Call Handling (session.py)

When Deepgram returns a function call in the response:
1. Extract function name + arguments
2. `check_availability` → call Google Calendar API, return slot list
3. `book_appointment` → create Google Calendar event, return confirmation
4. `transfer_to_owner` → forward call via Twilio `<Dial>`, log transfer
5. `take_message` → save to `messages` table, send SMS via Twilio

After each call ends → generate a summary (call the LLM once more with full transcript) → save to `call_logs.summary` + SMS to owner.

### Google Calendar Integration
- Use Google Calendar API v3 (free tier: 1M queries/day)
- Store OAuth tokens encrypted in `customers.calendar_credentials`
- OAuth consent flow: hosted at `/api/oauth/google/authorize` and `/api/oauth/google/callback`

### Stripe Integration (billing.py)
- `GET /api/stripe/checkout-session?customer_id=X` — Returns subscription status
- Used by the voice server to check if customer is still active before answering calls
- Webhook receiver for `customer.subscription.deleted` → deactivate customer

### Verification
- [ ] Call → "I want to book for Tuesday at 2pm" → Google Calendar event created
- [ ] Call → "Tell him I'll call back" → message saved, SMS sent to owner
- [ ] Call → "This is too complex" → transfer offered (Twilio `<Dial>` or prompt to call back)
- [ ] After call ends → owner receives SMS: "Call from [number]: [summary]"

---

## Iteration 4 — Web Dashboard (Days 8-10)

**Goal:** Self-serve customer experience. Sign up → pay → get number → dashboard.

### Architecture

```
frontend/
├── package.json
├── next.config.ts
├── tailwind.config.ts
├── postcss.config.js
├── tsconfig.json
├── components.json          # shadcn/ui config
├── prisma/
│   └── schema.prisma        # Mirror of PostgreSQL schema
├── app/
│   ├── layout.tsx            # Root layout (fonts, providers, metadata)
│   ├── page.tsx              # Landing page
│   ├── pricing/page.tsx
│   ├── login/page.tsx
│   ├── signup/page.tsx
│   ├── api/
│   │   ├── auth/[...nextauth]/route.ts   # NextAuth.js
│   │   ├── stripe/checkout/route.ts      # Create checkout session
│   │   └── stripe/webhook/route.ts       # Stripe webhook receiver
│   └── (dashboard)/          # Route group (requires auth)
│       ├── layout.tsx        # Dashboard shell (sidebar + header)
│       ├── page.tsx          # Overview / stats
│       ├── calls/page.tsx    # Call log with transcript viewer
│       ├── settings/page.tsx # Hours, FAQs, greeting, voice
│       └── billing/page.tsx  # Subscription management
├── components/
│   ├── ui/                   # shadcn/ui primitives (button, card, input, etc.)
│   ├── landing/
│   │   ├── hero.tsx
│   │   ├── features.tsx
│   │   ├── pricing-section.tsx
│   │   ├── demo-section.tsx
│   │   └── footer.tsx
│   ├── dashboard/
│   │   ├── sidebar.tsx
│   │   ├── header.tsx
│   │   ├── stats-cards.tsx
│   │   ├── call-table.tsx
│   │   ├── transcript-dialog.tsx
│   │   ├── settings-form.tsx
│   │   └── billing-card.tsx
│   └── providers.tsx         # SessionProvider, ThemeProvider, Toaster
├── lib/
│   ├── api-client.ts         # Typed fetch wrapper for Python API
│   ├── auth.ts               # NextAuth config (CredentialsProvider)
│   ├── stripe.ts             # Stripe client (server-side)
│   ├── db.ts                 # Prisma client singleton
│   └── utils.ts              # cn() helper, formatters
└── public/
    └── ...                   # OG image, favicon
```

### Authentication Flow

1. Customer signs up at `/signup` → creates account (email + password hashed with bcrypt)
2. Automatically logged in via NextAuth CredentialsProvider
3. Redirected to Stripe Checkout → after payment → callback sets `stripe_customer_id`
4. Stripe webhook `checkout.session.completed` → calls Python API to provision Twilio number + Deepgram agent

### Page Details

#### Landing Page (`/`)
- **Hero**: Headline "Never Miss Another Business Call", subhead, CTA "Get Your AI Receptionist", demo phone number
- **Features**: 3-column grid — 24/7 answering, appointment booking, message taking, SMS summaries
- **How it Works**: 3-step visual (Sign up → Configure → AI answers)
- **Pricing**: Single plan card ($29/mo → $39/mo after beta)
- **Footer**: Links, contact

#### Signup Page (`/signup`)
- Form fields: business name, owner name, email, password, timezone
- On submit: create user in DB → create customer via Python API → redirect to Stripe Checkout
- Use `react-hook-form` + `zod` validation + shadcn/ui `Form` components

#### Dashboard Overview (`/dashboard`)
- Stat cards: Total calls (today/month), appointments booked, messages taken, transfer rate
- Recent calls table (last 10) with status badges
- Quick actions: update hours, view latest transcript

#### Call Log (`/dashboard/calls`)
- shadcn/ui `DataTable` with sorting, filtering by date/outcome
- Columns: caller number, date/time, duration, outcome (badge), actions
- Click row → `Dialog` with full transcript (with speaker labels), recording playback (if available), summary
- Download transcript as text

#### Settings (`/dashboard/settings`)
- Tabs: Business Info, Hours & Availability, FAQs, Greeting & Voice
- Business Info: name, timezone, owner contact
- Hours: toggles per day + time range pickers (mon-sun)
- FAQs: dynamic add/remove rows (question + answer)
- Greeting: textarea with character count + preview ("This is what callers will hear")
- Voice: dropdown of Deepgram Aura voices with sample playback

#### Billing (`/dashboard/billing`)
- Current plan display
- Stripe Customer Portal link (manage subscription)
- Invoice history

### Responsive Design

Dashboard uses a **collapsible sidebar** — expands on desktop, collapses to icons on tablet, becomes a `Sheet` on mobile.

### Verification
- [ ] Sign up → Stripe checkout → receive confirmation email → number assigned
- [ ] Login → see dashboard → call log populates after test call
- [ ] Update FAQs in settings → call number → AI uses updated FAQs
- [ ] Update business hours → after-hours call → AI gives "we're closed" message
- [ ] Billing page shows subscription, Customer Portal works

---

## Iteration 5 — Polish & Deploy (Days 11-12)

**Goal:** Production-ready behind Traefik with proper error handling, monitoring, and hardening.

### Docker Compose (final)

```yaml
services:
  postgres:     # pgvector/pgvector:pg16
  server:       # voice-agent-server (uvicorn, port 8000)
  frontend:     # Next.js (npm run start, port 3000)
```

All on a bridge network. Only `frontend` (port 3000) and optionally `server` (port 8000 for health checks) exposed. Traefik routes:
- `reception.monizhealth.com` → frontend:3000
- `api.reception.monizhealth.com` → server:8000

### Production Hardening
- Rate limiting per customer (prevent single caller from spamming)
- Call concurrency limits (max 3 concurrent calls per customer)
- Error logging to structured JSON logs
- Stripe subscription webhook: cancel → deactivate customer
- Graceful shutdown: drain active calls before stopping
- Health check endpoint monitored by Traefik

### Security
- All API keys in `.env` only (never committed)
- Internal API key for function call endpoints (Deepgram → server)
- bcrypt password hashing for customer logins
- HTTPS via Traefik + Let's Encrypt (already configured)
- CORS configured for dashboard ↔ API communication

---

## Dependency Graph

```
Iteration 1 (Voice Server)
  └── Iteration 2 (Multi-Tenant + DB)
        ├── Iteration 3 (Scheduling + Messages)
        │     └── Iteration 5 (Polish)
        └── Iteration 4 (Web Dashboard)
              └── Iteration 5 (Polish)
```

Iterations 3 and 4 can theoretically run in parallel (different repos) but are sequential in the plan since they're both done solo.

---

## Pre-flight Checklist

Before implementing, confirm these are in place:

| Requirement | Status |
|-------------|--------|
| Twilio account (paid, $20 minimum funded) | ? |
| Deepgram account with Voice Agents API access | ? |
| Ollama Cloud API key (already in env vars) | ? |
| Proxmox LXC available (2GB+ RAM) | ? |
| Traefik running at 192.168.68.4 | ? |
| Domain `reception.monizhealth.com` DNS pointed | ? |
| Stripe account (same as Resume Optimizer) | ? |
| Google Cloud Console project (Calendar API) | ? |

---

## Environment Variables

```
# Deepgram
DEEPGRAM_API_KEY=your_key
DEEPGRAM_PROJECT_ID=your_project_id

# Twilio
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_PHONE_NUMBER_SID=your_number_sid

# Ollama Cloud
OLLAMA_CLOUD_API_KEY=...
OLLAMA_CLOUD_ENDPOINT=https://ollama.com/v1

# Internal
INTERNAL_API_KEY=...

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

# NextAuth
NEXTAUTH_SECRET=...
NEXTAUTH_URL=https://reception.monizhealth.com
```
