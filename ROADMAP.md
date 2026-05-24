# AI Receptionist — Product Roadmap
## Micro-SaaS: Automated phone answering for local service businesses

---

## Product Vision

A plug-and-play AI phone answering service for small local businesses (plumbers, electricians, dentists, hair salons, etc.). The business gets a phone number that an AI receptionist answers 24/7 — takes messages, answers FAQs, schedules appointments, and only transfers complex calls to the owner.

**Revenue model:** $29-39/mo per business
**Target:** Service businesses in Canada & US (1-10 employees)
**Differentiation:** Zero setup friction — sign up online, port or get a number, configure in 5 minutes via web form

---

## Phase 1: Core MVP (4-6 weeks)
**Goal:** A single working AI receptionist for ONE business (your own test number)

### Week 1-2: Foundation
- [ ] Create Twilio account + purchase a test phone number
- [ ] Clone Deepgram inbound telephony reference repo
- [ ] Deploy on a Proxmox LXC (2GB RAM, 1 CPU) behind Traefik
- [ ] Configure Deepgram Voice Agent with Ollama Cloud as LLM
- [ ] Test with `dev_client.py` (no phone needed — mic + speaker test)
- [ ] Make first real phone call — AI answers from end to end
- [ ] Tune system prompt, greetings, voice, turn-taking parameters

### Week 3-4: Core Features
- [ ] Add function calling: check availability, book appointment, transfer to owner
- [ ] Connect to Google Calendar API for appointment booking
- [ ] SMS call summary to business owner after each call
- [ ] Voicemail if owner doesn't answer transfer
- [ ] Web dashboard (simple Next.js): call log, transcripts, settings
- [ ] Stripe billing integration

### Week 5-6: Multi-Tenant Readiness
- [ ] Implement Deepgram Reusable Agent Configurations (UUID per customer)
- [ ] Build admin portal: create customer → provision agent config → assign phone number
- [ ] Add Twilio number provisioning via API (buy number programmatically per customer)
- [ ] Port your own existing business number as test case
- [ ] End-to-end test: sign up → get number → receive test call → receive SMS summary
- [ ] Write "See it in action" landing page

**Milestone:** You can call your own test number and have a conversation with the AI that can check a pretend schedule, book a time, and send you a summary SMS.

---

## Phase 2: Beta (4-6 weeks)
**Goal:** 3-5 real businesses using it for free

### Customer Acquisition
- [ ] Offer free 1-month trial to 5 local Vancouver businesses (your dentist, barber, mechanic, etc.)
- [ ] Browser agent scrapes Google Maps for service business contacts
- [ ] Send personalized cold email (CASL-compliant — one email per published business address)
- [ ] Or simply ask people you already interact with: "Want a free AI receptionist for a month?"

### Productization
- [ ] Self-serve onboarding flow: business name → business hours → FAQs → choose number → done
- [ ] Automated provisioning: customer fills form → Twilio buys number → Deepgram creates agent → server routes calls
- [ ] Call log dashboard per business
- [ ] Business owner can update hours/FAQs via simple web form
- [ ] SMS to owner: "New message from [caller]: [transcript]. Call back at [number]"

### Learn & Tune
- [ ] Review call transcripts — what does the AI handle well? What gets transferred?
- [ ] Tune system prompt based on real conversations
- [ ] Measure: calls answered, appointments booked, transfers needed
- [ ] Decide on pricing ($29/mo vs $39/mo based on value delivered)

**Milestone:** 5 businesses active, collectively handling 50+ calls/week, AI handling 80%+ without human transfer.

---

## Phase 3: Launch (ongoing)
**Goal:** Paid customers acquired via SEO

### SEO Content Engine
- [ ] Landing page: "AI Phone Answering for [city] [industry]" pages
- [ ] Blog content pipeline (same cron as Resume Optimizer): "How [industry] can automate phone calls"
- [ ] Target: "ai receptionist [city]" — high intent, local SEO
- [ ] Google Business Profile optimization

### Sales Automation
- [ ] Browser agent monitors r/smallbusiness, r/Vancouver, local Facebook groups for "missed calls" / "phone answering" pain points
- [ ] Automated cold email follow-ups at 30/60/90 days to non-converting leads
- [ ] Referral program: refer a business, get 1 month free

### Operations
- [ ] Monitoring dashboard (call success rate, transfer rate, customer satisfaction)
- [ ] Automated billing via Stripe
- [ ] Support: email + call transcript review

**Milestone:** 100 paid customers at $29/mo = $2,900 MRR.

---

## Feature Pipeline (post-launch)

| Feature | Priority | Why |
|---------|----------|-----|
| **Multi-language (Punjabi, Mandarin, French)** | High | Vancouver-specific — huge underserved market |
| **SMS appointment reminders** | Medium | Reduces no-shows, increases stickiness |
| **Custom voicemail greetings** | Medium | Basic expectation |
| **Call recording playback in dashboard** | Low | Nice-to-have, not essential for MVP |
| **Outbound calling (reminders, follow-ups)** | Low | Adds Twilio outbound costs, more complexity |
| **CRM integrations (Salesforce, HubSpot)** | Low | Enterprise feature, overkill for micro-SaaS |

---

## Business Model Summary

| Metric | Estimate |
|--------|----------|
| Monthly price | $29/mo |
| Customers needed for $5K MRR | 172 |
| Customers needed for $10K MRR | 345 |
| Estimated churn | 5-8%/mo (small business) |
| Cost to serve per customer | ~$24/mo (Twilio + Deepgram) |
| Gross margin per customer | ~$5-15/mo |
| **Breakeven** | Margin is thin. Volume needed. |

**Note on margins:** At $29/mo with $24/mo cost, margins are tight. Pricing should increase to $39/mo once the product is validated and value is proven. The economics work better at higher call volumes (Deepgram $4.50/hr is flat = cheaper per minute as calls increase).
