# Architecture — Zolvo AI Sales & Growth Engine

**Technical submission · Coding Fellowship · Makers Admission 2026-2**

**Author:** Stiven Yepes Vanegas
**Version:** 0.3 (prototype complete — all milestones 0-12 implemented)
**Last updated:** May 24, 2026

---

## 1. Challenge context

Zolvo operates an *AI Sales & Growth Engine* that automates outbound marketing and initial sales closing: identifies leads, sends personalized messages via LinkedIn/Email, and books meetings without human intervention. The challenge is to design the technical architecture of the system to launch it in a new market (Mexico), demonstrating how to automate 80% of the sales and marketing process with clear ROI for the customer.

**Target market:** Mexico. Reasons: same language as the company, manageable compliance (LFPDPPP), active B2B fintech ecosystem (Konfío, Klar, Stori, Kueski) that constitutes a natural ICP for Zolvo.

**Explicit brief constraints:**
- Use of tools like `n8n` or `Cursor AI` as visible orchestrator.
- Pipeline connecting `n8n` + `Supabase` + `LLMs`.
- Agents with responses indistinguishable from a human (requirement, not just a value proposition).
- Scalable architecture.

---

## 2. System objective

> *Automate 80% of the outbound sales and marketing process, guaranteeing measurable ROI and system maintainability in production.*

Three derived sub-objectives:

1. **80% automated:** the system operates autonomously on the happy path and escalates to humans when uncertain. The remaining 20% is not a bug — it is design.
2. **Clear ROI:** every agent records cost, latency, and result. Metrics like `cost_per_meeting_booked` are computed with a single query.
3. **Indistinguishable from a human:** contextual memory, variable timing, pre-send evaluation, objection handling, escalation under uncertainty.

---

## 3. Prioritized quality attributes

The system is designed explicitly optimizing the following attributes, in priority order:

| # | Attribute | How it serves the objective |
|---|---|---|
| 1 | **Modularity / provider agnosticism** | Strategy pattern for LLMs enables cost-based routing (estimated 60-70% reduction in token spend). |
| 2 | **Observability** | Without metrics there is no demonstrable ROI. Every agent decision is traceable. |
| 3 | **Reliability** | Retries, dead letter queues, fallbacks. A system that fails and requires human rescue is not 80% automated. |
| 4 | **Scalability** | Event-driven, async, no synchronous coupling. 50 → 5000 leads/day without re-architecture. |
| 5 | **Security** | Multi-tenant RLS, secrets management, LLM output guardrails, LFPDPPP/GDPR compliance. |
| 6 | **Maintainability / testability** | Consequence of the above: clear interfaces make unit tests and mocks straightforward. |

**Attributes NOT explicitly prioritized** (conscious decision, not negligence):
- *Low-latency performance:* outbound is inherently asynchronous — seconds vs. milliseconds don't matter here.
- *99.99% availability:* temporary degradation is tolerable as long as events are preserved.

---

## 4. Architectural style

**Event-driven with hybrid orchestration** (n8n + Python microservices).

Justification: outbound is asynchronous by nature (days between messages, unpredictable replies). A synchronous request-response model does not fit the domain.

### 4.1 Responsibility split: why not everything in n8n?

The brief explicitly asks to use n8n. This can be interpreted two ways:

- **Path A — everything in n8n:** use AI nodes and integrated LangChain to build agent logic directly in n8n nodes.
- **Path B — hybrid:** n8n as the channel integration and visible workflow layer; Python services for complex logic.

**This architecture explicitly adopts Path B — not to evade n8n, but to preserve critical quality attributes:**

| Attribute | Path A (all in n8n) | Path B (hybrid) |
|---|---|---|
| Testability | Near impossible — logic in JSON | Standard unit and integration tests |
| Maintainability | Logic lives in nodes without real versioning | Code in Git, normal code review |
| Modularity (Strategy pattern) | Limited by n8n abstractions | Natural implementation in Python |
| Brief compliance | ✅ literal | ✅ uses n8n as required, without lock-in |
| Visibility for sales rep | ✅ excellent | ✅ visible workflows remain in n8n |
| Technology lock-in | High (all logic coupled) | Low (n8n replaceable without touching agents) |

**What n8n actually does** (heavy lifting, not just passthrough):
- Scheduled triggers (re-engagement of `dormant` leads)
- LinkedIn, Email, Calendar integrations (OAuth, rate limiting, retries)
- Visible workflows for sales reps (n8n native UI)
- Incoming webhooks and event outbox
- Send scheduling respecting the prospect's business hours

**What Python does:**
- Multi-agent logic with Strategy pattern
- LLM Gateway with cost-based routing
- Intent Classifier + Confidence Gate
- Contextual memory with pgvector
- Serial processing with debouncing

### 4.2 Applied patterns

- *Strategy* — abstraction of LLM providers and channels.
- *Repository* — data access decoupled from business logic.
- *Outbox pattern* — reliable event delivery without coupling transactions to external brokers.
- *Pipes & filters* — message processing pipeline (classify → generate → evaluate → send).
- *Circuit breaker* — protection against LLM provider or channel outages.
- *Debouncing + advisory lock* — guaranteed serial processing per lead (see ADR-06).

---

## 5. Architecture Decision Records (ADRs)

### ADR-01 · n8n as visible orchestrator, agents as Python microservices

**Context:** the brief explicitly asks for `n8n` or `Cursor AI`. Implementing all logic in n8n nodes makes the system unmaintainable (logic in JSON, no tests, no real versioning).

**Decision:** n8n manages visible workflows (lead intake, message scheduling, temporal triggers, channel integrations) and delegates via HTTP to decoupled Python services where agent logic and evaluation reside.

**Consequences:**
- ✅ Explicit brief compliance.
- ✅ Complex logic remains testable and versionable.
- ✅ Operational visibility for sales reps via n8n UI.
- ⚠️ Two systems to maintain (operationally more complex).

---

### ADR-02 · Strategy pattern for LLM provider with cost/criticality routing

**Context:** LLMs are commodities — their prices and capabilities change monthly. Coupling to a single provider is guaranteed technical debt.

**Decision:** an `LLMProvider` interface with implementations for OpenAI, Anthropic, Ollama, and OpenRouter. Each agent receives the provider by injection. A router selects the model based on task type: cheap models for classification and evaluation, premium models for critical generation.

**Consequences:**
- ✅ 60-70% cost reduction vs. using premium models for everything.
- ✅ Provider migration without touching business logic.
- ✅ Enables local models (Ollama) for PII-sensitive tasks.
- ⚠️ Additional complexity in tests (mandatory mocks).

---

### ADR-03 · Event-driven with Supabase Realtime + outbox pattern

**Context:** outbound conversations are asynchronous. Waiting hours or days between turns is the norm. A synchronous model forces polling or blocking.

**Decision:** domain events (`lead.created`, `message.sent`, `reply.received`, `meeting.booked`, `escalation.required`) published via Supabase Realtime. For critical events the outbox pattern applies: the event is written in the same transaction as the state change and a worker publishes it afterwards.

**Consequences:**
- ✅ No polling, no blocking.
- ✅ Reliable event delivery (at-least-once).
- ✅ Natural horizontal scalability.
- ⚠️ Debugging distributed flows requires strong observability (mitigated by ADR-04).

---

### ADR-04 · Two-gate pipeline: Intent Classifier + Confidence Gate

**Context:** no autonomous system is 100% reliable. Pretending otherwise is naive and operationally dangerous (an agent burning leads through hallucination costs more than any savings). Relying solely on the generator's "low confidence" is insufficient: LLMs tend to over-confident hallucination rather than admitting uncertainty.

**Decision:** two independent gates in the pipeline.

**Gate 1 — Intent Classifier (before generating):** a fast, cheap classifier (Haiku, Llama-3.1-8B or equivalent) reads the incoming message and categorizes it into a predefined set: `interested`, `objection_price`, `objection_authority`, `objection_timing`, `meeting_intent`, `complaint`, `complex_technical`, `out_of_scope`, `opt_out`. Sensitive categories (`complaint`, `complex_technical`, `out_of_scope`, `opt_out`) trigger **direct handoff to a human without passing through generation**. This prevents the agent from attempting to respond to something it should not.

**Gate 2 — Confidence Gate (after generating):** for messages that do pass to generation, the output is evaluated before sending. Another LLM (cheap model) scores the `confidence_score` on naturalness, relevance, and risk axes. If it falls below the configurable threshold, it escalates to a human via Slack with full context.

**Consequences:**
- ✅ Operationalizes the brief's 80% with a double safeguard.
- ✅ Reduces hallucinations: what shouldn't be responded to, isn't attempted.
- ✅ Every decision is auditable (both classification and evaluation).
- ✅ Generates a labeled dataset for future fine-tuning.
- ⚠️ 2 extra LLM calls per incoming message (~$0.002 with cheap models). Trivial cost vs. the avoided risk.

---

### ADR-05 · Multi-tenant from day one with Row-Level Security

**Context:** Zolvo is B2B. Multiple clients share the infrastructure. A cross-tenant data leak would be catastrophic.

**Decision:** all operational tables carry `tenant_id`. RLS policies in Postgres guarantee row-level isolation. The application never manually filters by `tenant_id` — it relies on RLS + session context.

**Consequences:**
- ✅ Isolation guaranteed at the database level, not the application level.
- ✅ LFPDPPP/GDPR compliance (right to erasure via RLS and soft-deletes).
- ⚠️ Performance: indexes with `tenant_id` as the first field are mandatory.

---

### ADR-06 · Serial processing per lead with debouncing and advisory lock

**Context:** a prospect may send rapid successive messages ("Hi", 3 seconds later "I'm interested, pricing?"). If the system processes in parallel, two agents read incomplete history and send desynchronized responses. Nothing exposes a bot more than this. Additionally, instant responses (< 5 seconds) also expose the bot: a human reading LinkedIn doesn't reply in 2 seconds.

**Decision:** combine two mechanisms.

1. **Debouncing on ingestion:** when a message arrives, the system waits between 30 and 90 seconds (random jitter, configurable by channel and time of day) before processing it. If another message from the same lead arrives during that window, the timer resets and the messages are grouped as a single conversational turn.

2. **Advisory lock on processing:** before processing a turn, the worker acquires a `pg_advisory_xact_lock(lead_id)` in Postgres. This guarantees strict serial processing per lead, even if multiple workers compete for the same event.

**Consequences:**
- ✅ Eliminates race conditions on concurrent messages from the same lead.
- ✅ "Natural" latency stops being a bug and becomes a humanization feature.
- ✅ Reduces cost: grouped messages = one LLM call instead of N.
- ⚠️ Increases response latency — acceptable and desirable in async outbound.
- ⚠️ Requires monitoring: if debouncing drifts, the system responds slowly without justification.

---

### ADR-07 · Dual memory strategy: immediate context + semantic memory

**Context:** the "memory" of a conversational agent has two distinct needs that are frequently confused: the immediate context of the current thread (what was said 2 messages ago) and long-term semantic memory (how similar objections were resolved in other leads, what this same lead said 3 weeks ago).

Solving both with the same mechanism is suboptimal: vectorizing the current thread is expensive and unnecessary; loading all textual history is impossible beyond a certain volume.

**Decision:** dual strategy.

**Short-term memory (textual):** the last N messages of the current conversation are loaded as text from the `messages` table and injected into the prompt as `chat_history`. N is configurable (typically 10-20 turns). Not vectorized. O(1) access by `conversation_id`.

**Long-term memory (semantic):** closed conversations, successful objection cases, similar lead profiles, and ICP — all stored as embeddings in `lead_embeddings` and a new `conversation_summaries_embeddings` table. The agent queries via similarity search (pgvector) when it needs context outside the immediate window.

**Consequences:**
- ✅ Efficiency: we don't vectorize what doesn't need semantic search.
- ✅ Quality: the agent has precise recent context + relevant historical context.
- ✅ Controlled cost: embeddings are generated when closing conversations, not on every turn.
- ⚠️ Complexity: two memory mechanisms instead of one. Mitigated by encapsulating both in `MemoryService` with a unified interface.

---

## 6. C4 Diagrams

### 6.1 Level 1 — Context

![C4 Level 1 — Context Diagram](Challenge%20Zolvo%20Architecture-Context%20Diagram.drawio.png)

---

### 6.2 Level 2 — Containers

![C4 Level 2 — Container Diagram](Challenge%20Zolvo%20Architecture-Container%20Diagram.drawio.png)

---

### 6.3 Level 3 — Components (Agent Services API)

![C4 Level 3 — Component Diagram (Agent Services API)](Challenge%20Zolvo%20Architecture-Component%20Diagram.drawio.png)

---

## 7. Sequence diagram — Happy Path

![Sequence Diagram — Happy Path](Challenge%20Zolvo%20Architecture-Sequence.drawio.png)

**Notes on the diagram:**

- **Phase 1 runs in the background** when the lead is ingested, not on every reply. This decouples research latency from the prospect's perceived response time.
- **Debouncing turns latency into a humanization feature.** A human doesn't reply to a LinkedIn DM in 2 seconds.
- **The two gates (Intent Classifier + Confidence Gate) are independent.** The first filters what to attempt; the second validates what was attempted.
- **The advisory lock guarantees serialization per lead** even if multiple workers consume from the bus.

---

## 8. State machine — Conversation lifecycle

![State Machine — Conversation Lifecycle](Challenge%20Zolvo%20Architecture-states.drawio.png)

> **Prototype implementation note:** The design state `awaiting_human` is implemented as two separate observable states: `handoff` (Gate 1 routed — intent is `complex_technical`, `complaint`, `opt_out`, or `out_of_scope`; no draft was generated) and `escalated` (Gate 2 blocked — draft existed but confidence score was below threshold; draft pending human review). Both trigger a Slack notification to the SDR.

---

## 9. Data model (Supabase)

### 9.1 Core tables

```sql
-- Multi-tenancy: tenant_id on all operational tables
-- RLS enabled on all tables

leads
  id              uuid PK
  tenant_id       uuid FK
  source          text          -- linkedin, csv_import, api, manual
  full_name       text
  email           text
  linkedin_url    text
  company         text
  role            text
  enriched_data   jsonb         -- Researcher output
  status          text          -- see state machine
  created_at      timestamptz
  owner_id        uuid          -- assigned sales rep

lead_embeddings
  lead_id         uuid FK
  tenant_id       uuid FK
  embedding       vector(1536)
  source_text     text          -- text from which the embedding was generated
  model_used      text          -- text-embedding-3-small, etc.
  created_at      timestamptz

conversation_summaries_embeddings
  conversation_id   uuid FK
  tenant_id         uuid FK
  embedding         vector(1536)
  summary_text      text          -- dense summary generated when closing the conversation
  outcome           text          -- scheduled | lost | dormant
  loss_reason       text          -- NULL if outcome != lost
  model_used        text
  created_at        timestamptz

conversations
  id              uuid PK
  tenant_id       uuid FK
  lead_id         uuid FK
  channel         text          -- linkedin, email
  started_at      timestamptz
  status          text          -- researching, engaging, conversing, ...
  current_stage   text
  loss_reason     text          -- NULL if not in lost state

messages
  id                    uuid PK
  tenant_id             uuid FK
  conversation_id       uuid FK
  direction             text          -- inbound | outbound
  channel               text
  content               text
  generated_by_agent    text          -- copywriter, conversationalist, ...
  confidence_score      numeric(3,2)
  human_reviewed        boolean
  sent_at               timestamptz

agent_runs
  id                uuid PK
  tenant_id         uuid FK
  agent_name        text
  conversation_id   uuid FK
  input_payload     jsonb
  output_payload    jsonb
  llm_provider      text          -- openai, anthropic, ollama
  llm_model         text          -- gpt-4o-mini, claude-sonnet-4-5
  tokens_in         integer
  tokens_out        integer
  cost_usd          numeric(10,6)
  latency_ms        integer
  decision_trace    jsonb         -- agent reasoning, useful for debugging
  created_at        timestamptz

events_outbox
  id              uuid PK
  tenant_id       uuid FK
  aggregate_id    uuid          -- lead_id or conversation_id
  event_type      text          -- lead.created, message.sent, etc.
  payload         jsonb
  published_at    timestamptz   -- NULL if not yet published
  attempts        integer
```

### 9.2 Model decisions

- **`agent_runs` is the pure observability table.** Every decision of every agent is auditable with cost and latency. `cost_per_meeting_booked` is computed with a single aggregated query.
- **`lead_embeddings` separated from `leads`** by separation of concerns: regenerating embeddings should not touch the rest of the record.
- **`conversation_summaries_embeddings` materializes the long-term memory** from ADR-07. Generated when closing the conversation, not on every turn. Enables RAG over past cases ("how were price objections resolved in Mexican fintech?").
- **`confidence_score` and `human_reviewed`** materialize the Confidence Gate from ADR-04.
- **`loss_reason` always persisted** when a conversation ends in `lost`. Without this there is no aggregate learning.
- **`events_outbox`** enables the outbox pattern from ADR-03.
- **`decision_trace`** captures agent reasoning for debugging and eventual fine-tuning.

---

## 10. Technology stack

| Layer | Technology | Justification |
|---|---|---|
| Visible orchestration | n8n | Explicit brief compliance, visibility for sales rep |
| Agent logic | Python + FastAPI | Most mature LLM ecosystem, typed with Pydantic, native async |
| Database | Supabase Postgres + pgvector | Brief compliance, native RLS, realtime, embeddings without extra service |
| Data access | supabase-py async (REST/HTTPS) | Direct Postgres host is IPv6-only in WSL2; supabase-py uses CloudFlare IPv4 without changing logical architecture |
| LLM providers | OpenRouter (default), Anthropic, OpenAI, Ollama | Strategy pattern; agnostic; OpenRouter as unified, cheaper gateway for the demo |
| Channels | LinkedIn, Gmail/Outlook, Google Calendar | Standard B2B outbound |
| Observability | OpenTelemetry + structured logs | Standard, vendor-agnostic |
| Notifications | Slack webhooks | Common in B2B teams |
| Deployment | Local · FastAPI on `localhost:8000` + n8n self-hosted on `n8n.stivenyepes.com` + Supabase Cloud | Demo on local machine; n8n already deployed on the same host |
| CI/CD | GitHub Actions | Standard |

---

## 11. Attribute-to-ROI mapping

| Design decision | ROI metric it enables |
|---|---|
| Strategy pattern + cost routing (ADR-02) | `cost_per_lead`, `cost_per_meeting`, estimated 60-70% savings vs. uniform premium model |
| `agent_runs` with cost/latency (Sec. 9) | Precise spend attribution per funnel stage |
| Intent Classifier (ADR-04, Gate 1) | `pct_messages_handed_off_by_intent` → prevents burning leads through inappropriate responses |
| Confidence Gate (ADR-04, Gate 2) | `pct_messages_auto_approved` → measures real automation level |
| Debouncing + advisory lock (ADR-06) | `messages_per_turn_avg` → avoids N LLM calls when 1 suffices; improves naturalness |
| Dual memory (ADR-07) | `context_retrieval_hit_rate` → measures when RAG adds real value |
| Explicit `awaiting_human` state (Sec. 8) | `human_intervention_rate` → how much of the 20% is being used |
| `loss_reason` persisted (Sec. 9) | Aggregate objection analysis → ICP and copy improvement |
| Event-driven async (ADR-03) | `leads_processed_per_hour` without touching code |

**Proposed ROI formula for the end customer:**

```
ROI = (meetings_booked × avg_meeting_value - total_system_cost)
       / total_system_cost

total_system_cost = sum(agent_runs.cost_usd) + infra_cost + residual_human_cost
```

This formula is defensible because every variable is measured from the database, not estimated.

---

## 12. Prototype implementation status

### Implemented (Milestones 0-12 completed)

- ✅ **[Milestone 0]** Python project structure, CI (ruff + pytest), Supabase schema + RLS
- ✅ **[Milestone 1]** LLM Gateway with Strategy pattern — 4 providers (OpenRouter, Anthropic, OpenAI, FakeLLMProvider)
- ✅ **[Milestone 2]** Data model and repositories with RLS multi-tenant (supabase-py async)
- ✅ **[Milestone 3]** Researcher Agent — ICP enrichment + pgvector embedding
- ✅ **[Milestone 4]** Copywriter Agent — personalized outbound message (subject + body JSON)
- ✅ **[Milestone 5]** Intent Classifier — 9 categories, automatic handoff, persists to `agent_runs`
- ✅ **[Milestone 6]** Memory Service — short-term textual (last 15 messages) + long-term pgvector
- ✅ **[Milestone 7]** Conversationalist Agent — multi-turn with dual memory, adapts tone by intent
- ✅ **[Milestone 8]** Evaluator / Confidence Gate — score = (naturalness + relevance + (1−risk)) / 3
- ✅ **[Milestone 9]** Orchestrator — coordinated two-gate pipeline, persists intent_classifier agent_run
- ✅ **[Milestone 10]** Complete FastAPI endpoints + 2 active n8n workflows
- ✅ **[Milestone 11]** Functional end-to-end demo — lead Diego Ramírez (CTO @ CredIMex), 3 turns
- ✅ **[Milestone 12]** Video polish:
  - `ChannelAdapter` ABC + `LinkedInMockAdapter` + `EmailMockAdapter` (logs via structlog)
  - `SlackStub` — `notify_handoff()` / `notify_escalation()` visible in Terminal 1
  - `GET /operator/dashboard` — real-time pipeline metrics
  - `demo/run_happy_path.py` — rich UI with prospect view + operator dashboard
  - `demo/metrics.sql` — 4 queries for Supabase SQL Editor

### Out of scope for the prototype (documented, not implemented)

- **Real LinkedIn API integration** — simulated with `LinkedInMockAdapter` logging `channel.linkedin.send`
- **Real Slack integration** — simulated with `SlackStub` logging `slack.handoff_alert` / `slack.escalation_alert`
- **Specialized Objection Handler** — covered by Conversationalist in the prototype
- **Automated re-engagement of `dormant` state** — state defined in the state machine, not implemented
- **Real debouncing** — in production requires a worker with timer reset; not implemented in the prototype
- **Advisory locks under real contention** — single-worker in the prototype
- **Demo with multiple simultaneous tenants** — the RLS multi-tenant design is implemented; the demo uses a single tenant

### Implementation decisions that differ from the original design

| Component | Original design | Actual implementation | Reason |
|---|---|---|---|
| DB access | SQLAlchemy + asyncpg | supabase-py async (REST/HTTPS) | DB direct host is IPv6-only in WSL2; supabase-py uses CloudFlare IPv4 |
| LLM providers | OpenAI + Anthropic as primary | OpenRouter as default | Cheaper for the demo; covers multiple models with one key |
| Channels | Real LinkedIn/Email/Calendar | Mocks with structlog | LinkedIn App requires approval; OAuth out of prototype scope |
| Slack | Real webhook | SlackStub with log.warning | No credentials; the log is sufficient for the visual demo |
| Debouncing | 30-90s jitter + timer reset | 3-7s for demo recordability | Prototype: immediate processing; does not affect the demo flow |

---

## Appendix — Glossary

| Term | Meaning |
|---|---|
| ICP | Ideal Customer Profile — definition of the ideal customer |
| RAG | Retrieval-Augmented Generation — generation with retrieved context |
| RLS | Row-Level Security — row-level security policies in Postgres |
| DLQ | Dead Letter Queue — queue for messages that failed after N retries |
| LFPDPPP | Ley Federal de Protección de Datos Personales en Posesión de los Particulares (Mexico data protection law) |
| GDPR | General Data Protection Regulation (Europe) |
| LTV | Lifetime Value — estimated total value of a customer |
| CAC | Customer Acquisition Cost — cost to acquire a customer |
| C4 | Simon Brown's model for diagramming software architectures |
| ADR | Architecture Decision Record — record of an architectural decision |
