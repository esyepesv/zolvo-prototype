# LIMITATIONS.md — Gaps between design and prototype

> This document exists because technical honesty is worth more than the appearance of completeness. The system described in `docs/arquitectura-zolvo.md` is the target design. This prototype covers the essential happy path in 48 hours, with deliberate trade-offs listed here.

**Audience:** technical reviewers and future maintainers. If you plan to compare the code against the design, read this first.

---

## 1. Executive summary

| Design component | Status in prototype | Severity |
|---|---|---|
| Strategy pattern for LLMs | ✅ Fully implemented (4 providers) | — |
| Multi-tenant with RLS | ✅ Fully implemented | — |
| Intent Classifier (Gate 1) | ✅ Fully implemented | — |
| Confidence Gate (Gate 2) | ✅ Fully implemented | — |
| Dual memory (textual + pgvector) | ✅ Fully implemented | — |
| Observability (`agent_runs`) | ✅ Fully implemented | — |
| Operator dashboard | ✅ Fully implemented | — |
| Researcher Agent | ⚠️ Implemented without external sources | Medium |
| Conversationalist (multi-turn) | ✅ Fully implemented | — |
| Scheduler Agent | ❌ Absorbed by Conversationalist | **High** |
| Debouncing + Advisory Lock (ADR-06) | ✅ Implemented (async jitter + in-memory lock) | — |
| Async Event Bus (ADR-03) | ❌ Replaced by synchronous HTTP | Medium |
| Circuit breaker (ADR-01) | ✅ Implemented (in-memory, per-provider) | — |
| Re-engagement of `dormant` leads | ❌ State defined, not automated | Low |
| Specialized Objection Handler | ❌ Absorbed by Conversationalist | Low |
| Real channels (LinkedIn/Email/Calendar) | ❌ Mocks with structured logs | By design |
| Real Slack | ❌ Stub with `log.warning` | By design |

---

## 2. High-severity gaps

### 2.1 Debouncing + Advisory Lock (ADR-06) — implemented ✅

**What the design says:** ADR-06 argues that debouncing (30–90s with jitter) and `pg_advisory_xact_lock(lead_id)` are the mechanisms that turn latency into a humanization feature and eliminate race conditions on concurrent messages from the same lead.

**What the code does:**
- `POST /events/reply` persists the inbound message immediately (before acquiring the lock).
- Acquires an `asyncio.Lock` per `conversation_id` (module-level dict `_conv_locks`).
- Inside the lock: `asyncio.sleep(random.uniform(debounce_min, debounce_max))` with structured logging.
- The full pipeline and channel routing run inside the lock — processing the same conversation in parallel within a single process is impossible.

**Production limitation:** `asyncio.Lock` is in-memory and single-process. In a multi-worker deployment (Gunicorn with multiple workers), two workers can acquire separate locks for the same `conversation_id`. For multi-worker, `pg_advisory_xact_lock` or Redis Distributed Lock (Redlock) is required. In the single-worker uvicorn prototype, the lock is sufficient.

---

### 2.2 Scheduler Agent — absorbed by Conversationalist

**What the design says:** the C4 L3 diagram shows a `Scheduler Agent` as an independent component with Strategy pattern. The sequence diagram (Phase 4) details how the Scheduler queries Calendar, proposes natural slots, awaits confirmation, creates the event, and notifies.

**What the code does:** when the Intent Classifier detects `meeting_intent`, the flow goes to `ConversationalistAgent` with a specific prompt guide in `_INTENT_GUIDANCE["meeting_intent"]` that asks it to propose 2-3 time slots. **There is no real Calendar event creation.** In n8n there is a "Google Calendar — Create Event" node behind an `IF intent == meeting_intent` condition, but the endpoint points to `googleapis.com/calendar/v3` without configured OAuth — the node is a blueprint, not functional.

**Why it was left this way:**
- Creating a separate Python agent for a prompt guide applied to the same LLM adds no real value: it would be duplication under a different name.
- Real Google Calendar integration requires OAuth + Google Workspace credentials, out of scope for a 48-hour prototype.
- Available slot detection, confirmation parsing, and event creation are **3 distinct sub-features**, each with its own complexity.

**Real impact:**
- In the demo, the system "responds as if it's going to schedule" but **schedules nothing**. The brief asks to "book meetings."
- This is the most visible gap if the reviewer runs the demo manually and checks Calendar.

**What production requires:**
1. `SchedulerAgent` as Strategy with injected dependencies: `CalendarAdapter`, `LLMGateway`, `MemoryService`
2. `CalendarAdapter` with real implementations (`GoogleCalendarAdapter`, `OutlookAdapter`) + mock for tests
3. Secondary intent parser: "user confirmed slot X" vs. "user proposed alternative" vs. "user backed out"
4. Active `scheduling` state in the state machine (already defined in `docs/arquitectura-zolvo.md §8`)
5. n8n workflow with Google Calendar OAuth and `.ics` delivery

**Estimate:** 8-12h of development for a functional Scheduler without real channels; +15h for OAuth integrations in production.

---

## 3. Medium-severity gaps

### 3.1 Async Event Bus (ADR-03) — replaced by synchronous HTTP

**Design:** Supabase Realtime + outbox pattern. Domain events (`lead.created`, `reply.received`, `message.sent`) published asynchronously. Subscribed workers consume them without blocking.

**Code:** the API receives HTTP, executes the full pipeline in the same request, and responds with the result. The `events_outbox` table exists in migrations but **no code writes to it**.

**Why:** a synchronous demo is easier to show in a video. `POST /events/reply` returns `{intent, action, confidence}` in the response, which is ideal for recording live logs. Making it async would have required a separate event consumer running alongside and a polling/SSE mechanism for the demo to observe the result.

**Honest trade-off:**
- ✅ Demo is more visible and debuggable
- ❌ Blocking latency in the prospect's request (in real production, LinkedIn doesn't wait 8 seconds)
- ❌ No backpressure when message spikes occur
- ❌ `events_outbox` is defined but unused

**What production requires:**
- Async worker consuming from Supabase Realtime (channel per event type)
- `events_outbox` written in the same transaction as state changes
- Publisher worker that reads `events_outbox` and emits to Realtime with deduplication by `id`
- Retry policy with DLQ for events that fail 3 times
- Integration tests validating at-least-once delivery

---

### 3.2 Researcher Agent — enrichment without external sources

**Design:** the Researcher enriches the lead with external data before generating the embedding.

**Code:** the Researcher receives `{full_name, email, company, role}`, passes it to an LLM with an enrichment prompt, and persists the result as JSON in `leads.enriched_data` + embedding in `lead_embeddings`. **It does not query LinkedIn API, Crunchbase, Apollo, ZoomInfo, or any external source.** The LLM "infers" a plausible profile from the company name and role.

**Why:** real enrichment APIs require vendor contracts (Apollo starts at $99/month) or LinkedIn approval (a weeks-long process). In a prototype, using an LLM as synthetic enrichment demonstrates the pattern without the cost.

**Production risk:**
- Hallucinated enrichment may contain incorrect prospect information
- Embeddings built on fictional enrichment degrade RAG quality
- In a real case, you could send a personalized message with invented facts — worse than a generic message

**What production requires:**
- `EnrichmentProvider` with Strategy pattern: `ApolloProvider`, `ClearbitProvider`, `LinkedInScraperProvider`, `LLMFallbackProvider`
- Enrichment cache in Supabase with TTL (lead data doesn't change every hour)
- Cross-validation: if two providers disagree, flag for review

---

### 3.3 Circuit breaker (ADR-01) — implemented ✅

**Design:** ADR-01 mentions circuit breaker for protection against LLM provider outages.

**Code:** `src/zolvo/llm/circuit_breaker.py` implements an in-memory circuit breaker per provider with three states (closed → open → half-open). `LLMGateway.complete()` checks it before each call: if the circuit is open, it automatically tries the next available provider. Successive failures (`failure_threshold=3`) open the circuit for `recovery_timeout=60s`, then move to half-open to probe recovery.

---

## 4. Low-severity gaps

### 4.1 Automatic re-engagement of `dormant` leads

**Design:** the state machine (§8 of architecture) defines `dormant` with a maximum of 2 spaced retries.

**Code:** the state exists in `conversations.status` but **there is no scheduled job that scans it** and triggers re-engagement.

**What it requires:** an n8n workflow with a daily Cron trigger that queries `conversations WHERE status='dormant' AND updated_at < NOW() - INTERVAL '7 days'` and fires `POST /events/reengage`.

---

### 4.2 Specialized Objection Handler

**Design:** independent component for complex objections (price, authority, timing).

**Code:** absorbed by `ConversationalistAgent` with intent-specific `_INTENT_GUIDANCE`.

**Conscious decision:** a separate agent would have been duplication. The intent-based guide already generates differentiated responses. If production validates that objection copy benefits from longer prompts or separate RAG over successful cases, fragmenting makes sense. For now it is premature.

---

### 4.3 "Circular" Confidence Gate

**Legitimate criticism:** the Evaluator uses an LLM (cheap model) to evaluate what another LLM (premium model) generated. If both share training biases, the evaluator may approve responses that a human would reject.

**Why it was accepted:**
- Still better than having no evaluator
- Catches the obvious cases: wrong tone, explicit ROI promises, legal risks
- The 0.70 threshold allows conservative calibration

**Production improvement:**
- Deterministic rules as pre-filter before the LLM evaluator (already implemented: regex for promised prices, forbidden words, max length, caps ratio)
- Evaluator using a model from a different family than the generator (Anthropic generates, OpenAI evaluates) to reduce shared bias
- Periodic manual sampling (10% of approved messages) for human audit → fine-tuning dataset

---

## 5. Explicit mock decisions (by design, not by time)

These are not gaps — they are deliberate trade-offs:

| Mock | Reason |
|---|---|
| `LinkedInMockAdapter` | LinkedIn App requires approval (weeks). Designing the adapter with a clean interface is the architectural contribution. |
| `EmailMockAdapter` | Google Workspace OAuth is out of 48h scope. |
| `SlackStub` | No real webhook configured. Structured logging fulfills the demo function. |
| Real Calendar | Same reason as LinkedIn. |
| n8n with full OAuth | Same reason. Workflows remain as structural blueprints. |

In all cases, **the abstraction (ABC + Strategy) is implemented**. Swapping a mock for the real implementation is localized to a single file, without touching agents, orchestrator, or intent classifier.

---

## 6. Honest critique of n8n's role in the prototype

This is the observation most likely from a technical reviewer, so addressing it directly:

**Demo reality:** the two n8n workflows (`zolvo-new-lead-ingestion` and `zolvo-reply-received`) act primarily as **HTTP proxies**: receive a webhook, POST to the FastAPI API, return the response. n8n is not orchestrating complex logic in this demo.

**Why it was done this way:**
- The brief asks for "pipeline with n8n + Supabase + LLMs." Having n8n trigger visible workflows fulfills that literally.
- The complex logic (multi-agent, Strategy pattern, evaluation) lives in Python for the reasons in ADR-01 (testability, maintainability, versioning). Moving it to n8n nodes would have sacrificed those.
- In production n8n grows with: LinkedIn API nodes, Gmail, Google Calendar, Cron schedulers, Slack/Discord alerts, branches by channel/segment. The `n8n/README.md` describes that target state.

**What a demanding reviewer might argue:** "the demo doesn't show n8n's real value, it just uses it as a proxy." That is a valid and acknowledged criticism.

**Defense:** the demo prioritizes demonstrating the agent architecture and the two-gate pipeline, where the genuine technical contribution lies. n8n is the operational facade for the sales rep, not the computational core. Moving the core to n8n would have been literal compliance at the cost of quality attributes.

---

## 7. What should NOT be interpreted as a gap

Some likely criticisms that **are not failures but explicit decisions**:

- **"The prototype only uses one tenant"** — the multi-tenant design is complete in migrations + RLS + `tenant_id` filtering. The demo uses one tenant because showing two adds noise, not information.
- **"Tests use FakeLLMProvider"** — this is **correct by design**, not a shortcut. Deterministic tests without network cost. Integration tests against real Supabase exist separately.
- **"No web dashboard"** — the dashboard is a JSON endpoint (`GET /operator/dashboard`) plus a full HTML+Chart.js page at `/dashboard`. Both are implemented.
- **"The demo uses only 1 lead"** — `demo/run_happy_path.py` is sequential for clarity. The system processes N leads in parallel without code changes; the demo is optimized for video recording.

---

## 8. Gap closure roadmap, prioritized

With one more week of development, this is the implementation order:

| Day | Gap | Priority reason |
|---|---|---|
| ✅ | Debouncing with jitter | Implemented — advisory lock for real race conditions still missing |
| ✅ | In-memory circuit breaker | Implemented — distributed state (Redis) needed for multi-worker |
| 1 | Advisory lock (`pg_advisory_xact_lock`) | Closes the missing part of ADR-06 |
| 1-2 | Scheduler Agent + real Google Calendar | The brief asks to book meetings — without this the system is incomplete |
| 2-3 | Async Event Bus + outbox pattern | Enables real scalability and eliminates blocking latency |
| 3-4 | Researcher with Apollo/Clearbit | Without real enrichment, copy may contain invented data |
| 4-5 | Re-engagement of `dormant` + objection handler | Funnel refinements |
| 5-6 | Load tests, manual message audit, hardening | Pre-production |

---

## 9. What the prototype DOES demonstrate (for balance)

To avoid ending this document only on what's missing:

- **Engineered design:** quality attributes explicitly prioritized, ADRs with honest trade-offs, C4 at 3 levels, modeled state machine.
- **Real Strategy pattern:** 4 interchangeable LLM providers with cost-based routing. Switching from OpenRouter to Anthropic takes 1 line in `.env`.
- **Observability as first-class citizen:** every decision of every agent lands in `agent_runs` with cost, latency, tokens, and payloads. ROI is computable, not estimated.
- **Multi-tenant from day 1:** RLS implemented on all tables. `tenant_id` filtering defended at the database level.
- **Functional two-gate pipeline:** Intent Classifier filters what to attempt; Confidence Gate validates what was attempted. Documented in ADR-04 and implemented.
- **Real dual memory:** short-term textual (last 15 messages) + long-term vector (pgvector with `match_lead_embeddings` and `match_conversation_summaries`). Both queried on every turn.
- **Runnable end-to-end demo:** a script reproduces the happy path in ~60 seconds with visual UI. Data is persisted in real Supabase.
- **Tests with FakeLLMProvider:** 54 tests passing without API cost or network dependency.

---

## 9.bis Known gaps introduced during gap-closure

The gap-closure work (advisory lock, state machine, pre-filter, circuit breaker) introduced decisions with their own technical debt. Listed explicitly so they are documented, not hidden.

### `_conv_locks` — LRU eviction capped at 1000

The per-`conversation_id` lock (`events.py`) uses an `OrderedDict` capped at `_MAX_CONV_LOCKS = 1000` with LRU eviction. This avoids the obvious memory leak, but **is not production-correct for multi-worker**:
- In a single worker, the 1000 cap is defensible: covers active conversations and discards inactive ones.
- In multi-worker (Gunicorn with N workers), each worker has its own `OrderedDict` → 2 workers can acquire separate locks for the same conversation.
- Production: replace with `pg_advisory_xact_lock` or Redis Redlock.

### Circuit breaker fallback ignores `task_type`

`LLMGateway.complete()` with an open circuit on OpenRouter falls back to the next available provider (insertion-order). If the next is OpenAI/Anthropic, **a premium model is used for a classification task that should cost a fraction of a cent**. This breaks ADR-02 (cost-based routing) during the circuit-open period.

**Production mitigation:** maintain separate pools per `task_type` (cheap vs. premium) and open the circuit only within the corresponding pool.

### State machine is an unconditional setter, not a validated transition

`Orchestrator` calls `update_status()` without reading the current state. A `lost` (terminal) conversation that receives a new message returns to `engaging`. A `scheduling` conversation returns to `engaging` if the next message is not `meeting_intent`.

**What is correct:** `transition(current_state, event) → new_state` with a transition table matching `docs/arquitectura-zolvo.md §8`. Deferred to production because fixing it correctly requires Orchestrator refactoring and additional tests.

### Evaluator pre-filter is a hardcoded rule set

The rules (`_FORBIDDEN_PATTERNS`, `_MAX_DRAFT_CHARS`, `_MAX_CAPS_RATIO`) are in code. A regulated client (banking, healthcare) might want stricter rules. The pre-filter is extensible but not per-tenant configurable.

**In production:** a `tenant_rules` table with per-tenant patterns + UI for the client to manage them.

### Circuit breaker does NOT protect `LLMGateway.embed()`

Only `complete()` registers success/failure in the breaker. If the provider fails on embeddings, the breaker doesn't know. In production `embed()` should also use `before_call()` and `record_*`.

### No HTTP idempotency

`POST /events/reply` does not accept a `request_id`. If n8n retries on timeout and the pipeline takes longer, the same message is processed twice. Partially mitigated by the conversation lock, but the inbound message is persisted **before** the lock — double insertion in `messages` is still possible.

**In production:** `external_message_id UNIQUE` field in `messages` + idempotent upsert.

### Demo debouncing (3-7s) is still "instant" for a human

The default was changed from 30-90s to 3-7s so the demo can be recorded. A reviewer looking at `.env.example` may point out that the demo doesn't really demonstrate the humanization effect of ADR-06.

**In production:** keep 30-90s for real channels, adjust by prospect's business hours.

---

## 10. How to defend this document to a reviewer

If a reviewer asks "why isn't X implemented?", the answer is here. If they ask something not listed here, that is genuinely a gap I didn't anticipate and worth noting for the next cycle.

**The principle behind this document:** I'd rather a reviewer read me saying "I didn't do this and here's why" than discover it themselves and conclude I wasn't aware. The difference between a junior and a senior engineer is often knowing what you left out and being able to justify it.

---

## 11. Roadmap to real production

This section answers: *if this prototype were to become a real product with paying customers, what would need to be done, in what order, and what are the real blockers?*

### What is already production-ready without changes

| Component | Why it's production-ready |
|---|---|
| Strategy pattern LLM (4 providers) | Just change keys in `.env`; cost-based routing already implemented |
| Two-gate pipeline | Scales horizontally; no shared state between requests |
| Dual memory with pgvector | Supabase handles the load; HNSW indexes already configured |
| RLS multi-tenant | Defended at the database level, not just in code |
| `agent_runs` observability | ROI computable per tenant from day 1 |
| Evaluator pre-filter | Deterministic rules that don't depend on an external LLM |

---

### Phase 0 — Base infrastructure (2-4 weeks)

**Goal:** expose the system to the internet with minimum security.

**1. API authentication**
All endpoints are public in the prototype. In production: API keys per tenant with FastAPI middleware. Without this the system cannot be exposed to the internet.

**2. Real deployment**
Local `uvicorn` is not suitable for production. Minimum stack:
- Gunicorn + multiple Uvicorn workers
- Railway, Fly.io, or a VPS on GCP/AWS
- Nginx or Caddy as reverse proxy
- Automatic SSL (Let's Encrypt)

**3. Distributed advisory lock**
The in-memory `asyncio.Lock` in the prototype doesn't work with multiple workers. Replace with:
- `pg_advisory_xact_lock(hashtext('conv:' || conversation_id::text))` in Supabase, or
- Redis Redlock for cross-process distributed locking

**4. Real Event Bus (eliminate blocking latency)**
Today `POST /events/reply` blocks 5-15 seconds while the full pipeline runs. In production the endpoint must return 202 immediately and process in the background. Options by increasing complexity:
- **Supabase Realtime** — Python workers subscribed to `events_outbox` changes (already have Supabase, zero new infra)
- **Redis Streams + ARQ** — more control, requires Redis
- **Celery + RabbitMQ** — more mature, more operational overhead

**5. Secrets vault**
`.env` on the server doesn't scale. AWS Secrets Manager, GCP Secret Manager, Doppler, or 1Password Secrets Automation.

---

### Phase 1 — Real channels (2-6 months)

#### LinkedIn — the critical bottleneck

LinkedIn has an official API for messaging, but it requires **LinkedIn Marketing Developer Platform partnership**:
1. Apply at `developer.linkedin.com` with a detailed use case
2. Manual review by LinkedIn (automated SDRs is a sensitive case)
3. Approval: between 4 weeks and never — LinkedIn is very restrictive

**Pragmatic early-stage alternative:** integrate with tools already approved by LinkedIn (Lemlist, Instantly.ai, Expandi, La Growth Machine). Zolvo connects via their API/webhook. The `LinkedInMockAdapter` is replaced by the tool's SDK — one line in `deps.py`.

#### Email — trivial

- SendGrid, Postmark, or Resend — 1-day setup
- Configure SPF/DKIM/DMARC on the client's domain (critical for deliverability)
- Handle bounces and unsubscribes (legally required in Mexico)

#### Google Calendar — complete Scheduler Agent

1. Google Cloud project + OAuth 2.0 credentials
2. Authorization flow per client
3. Implement `SchedulerAgent(AgentBase)` with `GoogleCalendarAdapter`
4. Secondary intent parser: text "Thursday at 3pm" → `datetime` → check availability → create event → send `.ics`
5. Active `scheduling` state in the state machine

Estimated effort: 2-3 weeks. No approval blockers like LinkedIn.

---

### Phase 2 — Real enrichment (parallel to Phase 1)

**Enrichment stack by cost/quality:**

| Source | Cost | Quality for Mexico | Setup |
|---|---|---|---|
| Apollo.io | $99+/month | High — good B2B LATAM coverage | 1 day |
| Clearbit | Variable per lookup | High | 1 day |
| Hunter.io | $49+/month | Medium — mainly emails | 1 day |
| ZoomInfo | $15k+/year | Very high | Weeks (sales process) |

**Architecture:** add `EnrichmentProvider` ABC with `ApolloProvider` as the first implementation. The Researcher calls external enrichment first, then uses the LLM only for qualitative analysis over already-verified data.

---

### Phase 3 — Production hardening (1-2 months)

- **Prompt management:** version control with per-tenant A/B testing, instant rollback, per-version performance metrics (Langfuse, PromptLayer, or Supabase table)
- **LLM observability:** Helicone or Langfuse integrated with `agent_runs`; alerts when `confidence_score_avg` drops below 0.65 over 24h
- **Per-prospect rate limiting:** Redis counters per `(lead_id, channel, day)` with tenant-configurable limits
- **Distributed circuit breaker:** Redis-backed so all workers share provider state
- **Global opt-out:** database of emails/LinkedIn URLs that must never be contacted; legally required in Mexico
- **Human-in-the-loop:** web interface for SDR to review, edit, and approve escalated drafts
- **Tenant billing:** Stripe usage-based billing on top of `agent_runs.cost_usd`

---

### Phase 4 — Scale (when there's traction)

- **Horizontal worker pool** — Kubernetes or Railway autoscaling
- **Embedding cache** — 7-day TTL in Redis for already-processed leads
- **Fine-tuned model** — with 500+ successful conversations; reduces costs ~10x and improves cultural tone
- **Multi-channel per lead** — LinkedIn + email + WhatsApp orchestrated by prospect behavior

---

### The most underestimated blocker: legal compliance

In Mexico the **Ley Federal de Protección de Datos Personales en Posesión de Particulares (LFPDPPP)** applies:
- Consent to process personal data of prospects
- Privacy notice for each of Zolvo's business clients
- ARCO rights (Access, Rectification, Cancellation, Opposition) for contacted prospects

Zolvo processes personal data of third parties (prospects) on behalf of its clients. This requires a **Data Processing Agreement (DPA)** with each client and a full legal review of the data flow. **Resolve this before the first paying customer.**

---

### Summary: time and team for the first real customer

```
Weeks 1-2  ── API authentication + server deployment
Weeks 3-4  ── Real email (SendGrid) + real Slack + LFPDPPP legal review
Month 2    ── Google Calendar (complete Scheduler Agent)
Months 2-3 ── Apollo.io for verified enrichment
Months 3-6 ── LinkedIn API or agreement with Lemlist/Instantly
Ongoing    ── Prompt optimization + observability + billing
```

**Minimum viable team:**
- 1 backend engineer (Python async, FastAPI, Supabase)
- 1 GTM/partnerships person (LinkedIn approval + compliance)

**Infrastructure cost for the first customer:** ~$150-300/month (Railway/Fly + Supabase pro + Apollo starter + LLM APIs). Scales linearly with lead volume.

---

**Author:** Stiven Yepes Vanegas
**Date:** May 24, 2026
**Last updated:** production roadmap added post-submission · Makers Admission 2026-2
