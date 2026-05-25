# Zolvo AI Sales & Growth Engine — Prototype

> Technical submission · Coding Fellowship · Makers Admission 2026-2

Multi-agent outbound sales pipeline: lead enrichment, personalized message generation, intent classification, dual memory (textual + vector), confidence gate before each reply is sent, and a real-time operator dashboard.

## Built with

| Layer | Tool |
|---|---|
| **Primary coding agent** | [Claude Code](https://claude.com/claude-code) (Sonnet 4.6) — architecture, implementation, refactors |
| **Support agents** | Google Gemini · Google Antigravity — second opinions and code review |
| **IDE** | Visual Studio Code |
| **Language** | Python 3.11+ with strict type hints |
| **Framework** | FastAPI · Pydantic v2 · structlog |
| **Database** | Supabase — Postgres + pgvector + RLS multi-tenant |
| **LLM providers** | OpenRouter (default) · Anthropic · OpenAI · Ollama (Strategy pattern) |
| **Orchestration** | n8n self-hosted |
| **Runtime** | Docker · uvicorn |
| **Dev tools** | ruff · pytest |

## Prerequisites

- Python 3.11+ (or Docker)
- A [supabase.com](https://supabase.com) project (free tier works)
- At least one LLM API key: **OpenRouter** (`OPENROUTER_API_KEY`) recommended

## Quickstart — Docker (< 5 min)

```bash
git clone <repo-url>
cd zolvo-prototype

# 1. Configure environment
cp .env.example .env
# Edit .env — required keys:
#   SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, OPENROUTER_API_KEY

# 2. Apply Supabase migrations (one-time, via SQL Editor on supabase.com)
#   supabase/migrations/00000000000000_init.sql
#   supabase/migrations/00000000000001_domain_tables.sql
#   supabase/migrations/00000000000002_similarity_search.sql
#   supabase/seed.sql

# 3. Build and run
docker compose up --build

# → http://localhost:8000/health     {"status":"ok"}
# → http://localhost:8000/dashboard  Operator dashboard (HTML + Chart.js)
# → http://localhost:8000/docs       Swagger UI
```

## Quickstart — local Python (< 10 min)

```bash
git clone <repo-url>
cd zolvo-prototype

# 1. Virtualenv + dependencies
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements-dev.txt

# 2. Environment
cp .env.example .env

# 3. Apply Supabase migrations (see above)

# 4. Verify
.venv/bin/ruff check .
PYTHONPATH=src .venv/bin/pytest -q
# → 52 passed (unit); integration tests require live Supabase

# 5. Run the API
PYTHONPATH=src .venv/bin/uvicorn zolvo.api.main:app --host 0.0.0.0 --reload
```

## End-to-end demo

With the API running in Terminal 1:

```bash
PYTHONPATH=src .venv/bin/uvicorn zolvo.api.main:app --host 0.0.0.0 --reload
```

### Happy path (all turns resolved by the agent)

```bash
.venv/bin/python demo/run_happy_path.py
```

Diego Ramírez @ CredIMex — interest → price objection → meeting intent. All 3 turns pass both gates; the agent responds autonomously. ~60s total.

### Escalation path (Gate 1 routes to human rep)

```bash
.venv/bin/python demo/run_escalation_demo.py
```

Sofía Herrera @ Conekta — meeting intent → complex technical question → complaint. Turns 2 and 3 hit `HANDOFF`: the system recognises it cannot answer well and alerts the sales rep via Slack instead of generating a risky response.

Both scripts print a pipeline summary table, a LinkedIn inbox simulation, and the operator dashboard.

> **Reset between demos:** truncate data tables in Supabase before the second demo to start with a clean state.

### Web dashboard

Open `http://localhost:8000/dashboard` in the browser for a live graphical view (auto-refresh every 5s):

- KPI cards: leads in pipeline, conversations, pending escalations, total cost
- Doughnut charts: pipeline state breakdown, intent distribution
- Bar charts: cost by agent, inbound vs outbound messages

The page consumes `GET /operator/dashboard?tenant_id=...` and renders with Chart.js (loaded from a CDN, no install step needed).

### Post-demo SQL metrics

Open the Supabase SQL Editor and paste `demo/metrics.sql` to see cost per agent, confidence score distribution, intent distribution, and pipeline totals.

---

## How the system works

A fully automated outbound sales pipeline. It takes a lead (name, company, role) and drives the conversation from the first message until it detects when the prospect wants a meeting — without human intervention except for cases that require it.

### The agents

| Agent | What it does | Default model |
|---|---|---|
| **Researcher** | Analyzes the lead and produces an ICP profile: fit, pain points, conversation hooks, company size. Saves a semantic embedding for RAG. | `claude-haiku-4.5` (cheap) |
| **Copywriter** | Generates the first outbound message: personalized subject + body using the Researcher's hooks. Returns JSON `{subject, body, channel}`. | `claude-haiku-4.5` |
| **IntentClassifier** | Classifies each prospect reply into one of 9 categories. Decides whether the agent can respond or needs a human. Persisted in `agent_runs`. | `claude-haiku-4.5` (temp 0.1) |
| **Conversationalist** | Generates multi-turn replies. Uses dual memory: the last 15 thread messages + semantic search over historical embeddings. Adapts tone by intent. | `claude-haiku-4.5` |
| **Evaluator** | Reviews the draft before sending across 3 axes: naturalness, relevance, risk. Blocks the send if the score is low. Includes a deterministic pre-filter (regex) that catches forbidden promises before calling the LLM. | `claude-haiku-4.5` (temp 0) |

### Channel adapters

Channels are implemented as stubs that log via structlog — visible in the API logs (Terminal 1 during the demo):

| Adapter | What it does | Visible log in Terminal 1 |
|---|---|---|
| `LinkedInMockAdapter` | Simulates a LinkedIn DM send | `LINKEDIN ▸ Message sent to prospect` |
| `EmailMockAdapter` | Simulates an email send | `EMAIL ▸ Message sent to prospect` |
| `SlackStub` | Notifies handoffs and escalations to the operator | `HANDOFF !! ▸ Human rep required` / `ESCALATE !! ▸ Draft blocked` |

All API logs use human-readable labels in `ENV=dev`. Each step of the pipeline appears as a labelled line with inline key metrics (intent, score, latency). JSON format is preserved for `ENV=prod`.

In production each mock is replaced with a real adapter (LinkedIn API, SMTP, Slack Webhooks) without touching business logic.

### The 9 intent categories

| Intent | Description | Handoff? |
|---|---|---|
| `interested` | General interest, wants to know more | No — agent responds |
| `objection_price` | Price/budget objection | No — agent negotiates |
| `objection_authority` | Not the decision-maker | No — agent educates |
| `objection_timing` | Not the right moment | No — agent works the timing |
| `meeting_intent` | Wants to schedule a call or demo | No — agent confirms |
| `complaint` | Complaint or negative experience | **Yes** → human |
| `complex_technical` | Deep technical question out of scope | **Yes** → human |
| `out_of_scope` | Unrelated to the product | **Yes** → human |
| `opt_out` | Wants to stop being contacted | **Yes** → human |

### The two-gate pipeline

Each prospect reply passes through two gates before the agent responds:

```
Prospect reply
      │
      ▼
┌─────────────────┐
│  GATE 1         │  IntentClassifier
│  Intent Check   │  Can the agent handle this?
└─────────────────┘
      │
      ├── should_handoff=True ──────────────────→ HANDOFF
      │                                           Slack: slack.handoff_alert
      │
      └── should_handoff=False
              │
              ▼
       Conversationalist
       (short-term: last 15 messages)
       (long-term: pgvector similarity search)
              │
              ▼ draft generated
      ┌─────────────────┐
      │  GATE 2         │  EvaluatorAgent
      │  Quality Gate   │  pre-filter (deterministic regex) → LLM score
      │                 │  score = (naturalness + relevance + (1−risk)) / 3
      └─────────────────┘
              │
              ├── score ≥ 0.70 ──→ SEND      (LinkedIn mock: channel.linkedin.send)
              └── score < 0.70 ──→ ESCALATE  (Slack: slack.escalation_alert)
```

### Dual memory

The Conversationalist has two memory layers:

- **Short-term (textual):** the last 15 messages of the current thread, passed directly into the prompt as conversation context.
- **Long-term (semantic):** vector search in pgvector. When generating a reply, the prospect's message is embedded and these are queried:
  - **`lead_embeddings`** — semantic profile of the lead produced by the Researcher.
  - **`conversation_summaries_embeddings`** — summaries of previous conversations.

### Observability: the `agent_runs` table

Every agent records a row in `agent_runs` with:
- `agent_name` — which agent ran (`researcher`, `copywriter`, `conversationalist`, `evaluator`, `intent_classifier`)
- `tokens_in / tokens_out` — exact token usage
- `cost_usd` — cost computed by the provider
- `latency_ms` — LLM response time
- `output_payload` — what was returned (intent, score, draft, etc.)

### The operator dashboard

`GET /operator/dashboard?tenant_id=...` aggregates real-time metrics:

```json
{
  "pipeline": {
    "total_leads": 154,
    "total_conversations": 91,
    "messages_inbound": 17,
    "messages_outbound": 42
  },
  "status_breakdown": {
    "researching": 12,
    "engaging": 65,
    "scheduling": 8,
    "handoff": 4,
    "escalated": 2
  },
  "quality_gates": {
    "pending_escalations": 1
  },
  "cost": {
    "total_usd": 0.079923,
    "by_agent": {
      "conversationalist": 0.027439,
      "evaluator": 0.020127,
      "copywriter": 0.016657,
      "researcher": 0.015700,
      "intent_classifier": 0.0
    }
  },
  "intent_distribution": {
    "meeting_intent": 2,
    "objection_price": 1
  }
}
```

`GET /operator/conversations?tenant_id=...&status=dormant` lists conversations by state for re-engagement queues.

The graphical dashboard at `/dashboard` consumes both endpoints automatically.

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | API status |
| `GET` | `/dashboard` | Web operator dashboard (HTML + Chart.js) |
| `POST` | `/agents/ingest` | Create lead → Researcher → Copywriter → outbound message |
| `POST` | `/events/reply` | Receive prospect reply → debounce → two-gate pipeline → route |
| `GET` | `/operator/dashboard` | Real-time pipeline metrics (JSON, param: `tenant_id`) |
| `GET` | `/operator/conversations` | List conversations by status (params: `tenant_id`, `status`) |
| `GET` | `/docs` | Swagger UI |

## Pipeline architecture

```
Lead ingested
      │
      ▼
 Researcher ──→ enriched_data + lead_embedding
      │
      ▼
 Copywriter ──→ outbound message (subject + body)
      │         └─→ LinkedInMockAdapter.send_message()
      ▼
 [Reply received]
      │
      ▼
 IntentClassifier (Gate 1) ──→ persisted to agent_runs
      │
      ├─ should_handoff=True ──→ HANDOFF → SlackStub.notify_handoff()
      │
      └─ should_handoff=False
            │
            ▼
       Conversationalist (dual memory)
            │  ├─ short-term: last 15 messages
            │  └─ long-term: pgvector similarity search
            ▼
       EvaluatorAgent (Gate 2)
            │  pre-filter (regex) → LLM score
            │  score = (naturalness + relevance + (1−risk)) / 3
            │
            ├─ score ≥ 0.70 ──→ SEND → LinkedInMockAdapter.send_message()
            └─ score < 0.70 ──→ ESCALATE → SlackStub.notify_escalation()
```

## Project layout

```
zolvo-prototype/
├── Dockerfile                  # Multi-stage build, non-root, healthcheck
├── docker-compose.yml          # API service with .env mount
├── .dockerignore
├── src/zolvo/
│   ├── api/
│   │   ├── main.py             # FastAPI app + static mount + /dashboard
│   │   ├── deps.py             # FastAPI dependency injection
│   │   ├── static/
│   │   │   └── dashboard.html  # Web dashboard (Chart.js via CDN)
│   │   └── routes/
│   │       ├── agents.py       # POST /agents/ingest
│   │       ├── events.py       # POST /events/reply (debounce + lock)
│   │       └── operator.py     # GET /operator/dashboard, conversations
│   ├── agents/                 # Researcher, Copywriter, Conversationalist, Evaluator
│   ├── channels/               # ChannelAdapter ABC + 3 mocks
│   ├── intent/                 # IntentClassifier — 9 categories
│   ├── orchestrator/           # Pipeline coordinator (two gates + state transitions)
│   ├── memory/                 # MemoryService — short-term + long-term (pgvector)
│   ├── llm/                    # Gateway + providers + circuit_breaker + prompts
│   ├── repositories/           # Repository pattern — supabase-py async
│   ├── models/                 # Pydantic domain models
│   ├── schemas.py              # FastAPI request/response schemas
│   └── config.py               # pydantic-settings
├── demo/
│   ├── run_happy_path.py       # Demo: all turns resolved autonomously (happy path)
│   ├── run_escalation_demo.py  # Demo: Gate 1 HANDOFF path (complex_technical, complaint)
│   └── metrics.sql             # Metrics queries for Supabase SQL Editor
├── supabase/
│   ├── migrations/             # 3 versioned SQL files
│   └── seed.sql                # Demo tenant
├── n8n/
│   ├── workflows/              # n8n workflow JSON exports
│   └── README.md               # What n8n does, curl commands, Konfío scenario
├── tests/
│   ├── unit/                   # 52 tests with FakeLLMProvider (no network)
│   └── integration/            # 5 tests against live Supabase
└── docs/
    └── arquitectura-zolvo.md   # C4, ADRs, data model, state machine
```

## Completed milestones

| # | Milestone | Status |
|---|---|---|
| 0 | Base setup (FastAPI, CI, Supabase schema) | ✅ |
| 1 | LLM Gateway with Strategy pattern | ✅ |
| 2 | Data model + repositories (RLS multi-tenant) | ✅ |
| 3 | Researcher Agent (enrichment + embeddings) | ✅ |
| 4 | Copywriter Agent (personalized outbound message) | ✅ |
| 5 | Intent Classifier (Gate 1, 9 categories) | ✅ |
| 6 | Memory Service (short-term + long-term pgvector) | ✅ |
| 7 | Conversationalist Agent (multi-turn with dual memory) | ✅ |
| 8 | Evaluator / Confidence Gate (Gate 2, 3 axes + pre-filter) | ✅ |
| 9 | Orchestrator (two-gate pipeline + state machine) | ✅ |
| 10 | FastAPI endpoints + n8n workflows | ✅ |
| 11 | End-to-end demo — happy path functional | ✅ |
| 12 | Video polish (channel stubs, operator dashboard, prospect view) | ✅ |
| 13 | Production gap closure (debounce, lock, circuit breaker, state transitions) | ✅ |
| 14 | Web dashboard + Dockerization | ✅ |
| 15 | Escalation demo script + human-readable API logs | ✅ |

## References

- [System architecture](docs/arquitectura-zolvo.md) — C4, ADRs, data model, state machine
- [LIMITATIONS.md](LIMITATIONS.md) — gaps between design and prototype + production roadmap
- [n8n workflows and Mexico simulation](n8n/README.md)
- [Supabase setup](supabase/README.md)
- [PROGRESS.md](PROGRESS.md) — internal development log (Spanish, kept for traceability)
