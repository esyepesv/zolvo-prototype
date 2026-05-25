# CLAUDE.md — Operational guide for Claude Code

> This file is the operational specification of the project. Read it in full before any action. It is the source of truth for objectives, constraints, scope, and conventions.

---

## 1. Project context

This repository implements the **prototype of Zolvo's AI Sales & Growth Engine**, a technical proposal for the Coding Fellowship challenge at Makers Admission 2026-2.

**You are the primary developer.** You will plan and build the code under the author's supervision (Stiven). The final goal of the project is to demonstrate — in a 5-minute video — a production-quality architecture with a functional prototype covering the happy path.

**Required reading before coding:**
- `docs/arquitectura-zolvo.md` — complete system design (C4, ADRs, data model, state machine). Every implementation decision is justified against this document.

If you find a contradiction between this `CLAUDE.md` and the architecture document, **stop and ask**. Do not assume.

---

## 2. Prototype objectives

**Demo goal (5-minute video):** show the end-to-end happy path with real data, demonstrating:

1. Lead ingestion with automatic enrichment
2. Initial outbound message generation
3. Prospect reply received (simulated or real)
4. Two-gate pipeline: Intent Classifier + Confidence Gate
5. Multi-turn reply with dual memory
6. Meeting intent detection and scheduling

**What is NOT the objective:** a product deployed in production. This is a demonstrative prototype with emphasis on design quality, not feature coverage.

---

## 3. Real constraints

| Constraint | Value |
|---|---|
| Absolute deadline | 48h from May 23, 2026, 17:58 (Colombia time) |
| Effective development time | ~30h (rest for script, recording, editing, buffer) |
| Demo market | Mexico (ICP: B2B fintech) |
| Prompt/UX language | Spanish |
| API cost | Minimum necessary. Prefer cheap models where possible. |

**If time runs out, the prototype must NOT be incomplete on the critical path.** Better to deliver fewer features done well than many done halfway.

---

## 4. Technology stack

### Backend (Agent Services API)
- **Python 3.11+** with strict typing (mypy if time allows)
- **FastAPI** for HTTP
- **Pydantic v2** for schemas and validation
- **SQLAlchemy 2.x** + **asyncpg** for Postgres
- **pgvector** via `pgvector-python`
- **httpx** for async HTTP calls
- **structlog** or well-configured standard logging

### Data
- **Supabase** (Postgres + pgvector + Realtime + RLS)
- Versioned migrations (Supabase CLI or Alembic)

### Orchestration
- **n8n** — available via MCP server. **Use the n8n MCP** to create and update workflows. Do not edit n8n JSON manually.

### LLM providers (Strategy pattern mandatory)
- **OpenAI** (gpt-4o-mini for cheap, gpt-4o for premium)
- **Anthropic** (claude-haiku-4-5 for cheap, claude-sonnet-4-5 for premium)
- **Ollama** (local, optional — useful for PII-sensitive tasks)
- **OpenRouter** (access to Llama, Mistral, etc.)

**Code must never import provider SDKs directly outside the `llm/` module.** Everything goes through `LLMGateway`.

### Tooling
- **uv** or **poetry** for dependency management
- **ruff** for linting
- **pytest** for tests
- **Claude Code** for development (you)

---

## 5. Project structure

Monorepo with packages. Proposed structure:

```
zolvo-prototype/
├── CLAUDE.md                       # this file
├── README.md                       # quickstart and demo guide
├── docs/
│   ├── arquitectura-zolvo.md       # complete design
│   └── diagrams/                   # PlantUML rendered (PNG/SVG)
├── pyproject.toml
├── .env.example
├── .gitignore
├── supabase/
│   ├── migrations/                 # versioned SQL
│   └── seed.sql                    # test data (Mexican ICP)
├── n8n/
│   └── workflows/                  # JSON exports of flows created via MCP
├── src/
│   └── zolvo/
│       ├── __init__.py
│       ├── api/                    # FastAPI controllers
│       │   ├── main.py
│       │   ├── routes/
│       │   └── deps.py
│       ├── agents/                 # each agent as Strategy
│       │   ├── base.py             # abstract AgentBase
│       │   ├── researcher.py
│       │   ├── copywriter.py
│       │   ├── conversationalist.py
│       │   ├── scheduler.py
│       │   └── evaluator.py        # Confidence Gate
│       ├── intent/
│       │   └── classifier.py       # Intent Classifier (Gate 1)
│       ├── orchestrator/
│       │   └── orchestrator.py     # decides which agent to invoke
│       ├── llm/                    # Strategy pattern for providers
│       │   ├── base.py             # LLMProvider interface
│       │   ├── openai_provider.py
│       │   ├── anthropic_provider.py
│       │   ├── ollama_provider.py
│       │   ├── openrouter_provider.py
│       │   ├── gateway.py          # LLMGateway with cost-based routing
│       │   └── prompts/            # versioned prompts, one per agent
│       ├── memory/
│       │   └── service.py          # Dual memory: textual + semantic
│       ├── channels/               # channel adapters
│       │   ├── base.py
│       │   ├── linkedin_mock.py    # mock for the prototype
│       │   └── email_mock.py
│       ├── repositories/           # Repository pattern
│       │   ├── base.py
│       │   ├── leads.py
│       │   ├── conversations.py
│       │   ├── messages.py
│       │   └── agent_runs.py
│       ├── models/                 # Pydantic + SQLAlchemy models
│       │   └── domain.py
│       ├── events/
│       │   └── bus.py              # Event bus (Supabase Realtime + outbox)
│       ├── observability/
│       │   ├── logging.py
│       │   └── metrics.py
│       └── config.py               # settings via Pydantic Settings
└── tests/
    ├── unit/
    ├── integration/
    └── fixtures/                   # synthetic Mexican ICP dataset
```

**Do not create modules that are not in this structure without asking.** If you need a new one, ask first.

---

## 6. Code conventions

### Principles (apply with judgment, not dogmatically)

- **SOLID where it adds value.** Strategy pattern for `LLMProvider`, `AgentBase`, `ChannelAdapter`, and `Repository`. **Do not abstract what only has one implementation and won't have more soon.**
- **Composition over inheritance.** Agents receive dependencies via constructor.
- **Dependency injection via FastAPI.** No external DI frameworks.
- **Immutability by default.** Pydantic models with `frozen=True` where applicable.
- **Async/await across the entire I/O path.** No synchronous `requests`.

### Hard rules

- Typing mandatory on public signatures. `from __future__ import annotations` in all modules.
- Short docstrings on public classes and non-trivial functions. Language: English (Python ecosystem standard).
- Structured logs with `extra={...}`, never with f-strings.
- Domain errors as specific exceptions (`LLMProviderError`, `ConfidenceTooLowError`, `IntentClassificationError`). Never `except Exception` except at the HTTP boundary.
- No dead code, no TODOs without an associated issue/owner, no `# this is hacky` comments.
- **No secrets in code.** Everything via `.env` and `Settings`.

### Tests

- **Unit tests mandatory** for: `LLMGateway` (routing), `IntentClassifier`, `Evaluator`, `MemoryService`, `Orchestrator`.
- **Integration test mandatory** for the complete happy path (with LLM provider mocks).
- **DO NOT write tests for simple Pydantic models or trivial wrappers.** Time is scarce — prioritize tests with signal.
- LLM provider mocks via the `LLMProvider` interface. A `FakeLLMProvider` with predefined responses must exist from early on.

---

## 7. Development workflow

### Rule 1: plan before acting

**For each milestone in section 8, follow this protocol:**

1. Read the milestone and the relevant architecture document.
2. **Before writing code**, produce a short plan in this format:

   ```
   ## Plan: [milestone name]

   ### Files to create/modify
   - path/to/file.py — what it does

   ### Technical decisions
   - decision 1 and why
   - decision 2 and why

   ### Risks / questions
   - something that is not clear
   - decision that requires validation

   ### Tests
   - what will be tested

   ### Estimated time: X minutes
   ```

3. Wait for the author's approval before coding.
4. Implement.
5. Run tests.
6. Report milestone completed with: files created, tests passing, validation command, suggested next milestone.

**If the plan is clear and obviously correct, say so and proceed without waiting.** Do not introduce unnecessary friction.

### Rule 2: small, descriptive commits

- One commit per closed functional unit (`feat: add LLMGateway with OpenAI provider`, not `wip`).
- Conventional commits: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`.
- No commits with broken code on `main`.

### Rule 3: when in doubt, ask

- 30 seconds of asking beats 30 minutes of wrong code.
- If you find an ambiguity in the architecture, **stop and ask** before improvising.

---

## 8. Delivery milestones

Each milestone is **demonstrable**: when done, there must be something concrete to show.

### Milestone 0 — Setup (estimated 2h)
- Folder structure
- `pyproject.toml` with dependencies
- `.env.example` with all variables
- Supabase: project created, base migrations, RLS enabled
- README with quickstart
- Minimal CI: ruff + pytest in GitHub Actions

**DoD:** `uvicorn zolvo.api.main:app` starts without errors; `pytest` runs without tests but without failures.

### Milestone 1 — LLM Gateway with Strategy pattern (estimated 3h)
- Abstract `LLMProvider` interface
- Implementations: `OpenAIProvider`, `AnthropicProvider`, `FakeLLMProvider` (for tests)
- `LLMGateway` with task-type routing (`classification` → cheap; `generation_critical` → premium)
- Automatic `agent_runs` registration (cost, latency, tokens)
- Unit tests: routing decides correctly; provider called with correct params; `agent_runs` persisted

**DoD:** `gateway.complete(task_type="classification", prompt="...")` works with at least 2 real providers.

### Milestone 2 — Data model and repositories (estimated 3h)
- Migrations in `supabase/migrations/` for all model tables (architecture section 9)
- RLS policies by `tenant_id`
- Repositories for `leads`, `conversations`, `messages`, `agent_runs`
- Integration test: insert lead, read lead, RLS blocks cross-tenant

**DoD:** `LeadRepository.create()` and `LeadRepository.get_by_id()` work against real Supabase.

### Milestone 3 — Researcher Agent (estimated 2h)
- `Researcher` implements `AgentBase`
- Generates lead enrichment + embedding
- Persists to `lead_embeddings`
- Registers `agent_runs`

**DoD:** `researcher.run(lead_id)` enriches a test lead and saves the embedding.

### Milestone 4 — Copywriter Agent (estimated 2h)
- `Copywriter` generates initial outbound message
- Retrieves ICP examples via RAG (placeholder if no ICP data yet)
- Prompts in Spanish, professional but approachable tone (Mexico ICP)
- Registers `agent_runs`

**DoD:** `copywriter.run(lead_id)` produces a plausible message for a Mexican fintech lead.

### Milestone 5 — Intent Classifier (Gate 1) (estimated 2h)
- `IntentClassifier` classifies into the 9 categories from ADR-04
- Uses cheap model via `LLMGateway` with `task_type="classification"`
- Returns `IntentResult(intent: str, should_handoff: bool, reason: str)`
- Unit tests with cases from each category using `FakeLLMProvider`

**DoD:** given a price objection message, returns `objection_price` and `should_handoff=False`. Given a complaint message, returns `complaint` and `should_handoff=True`.

### Milestone 6 — Memory Service (dual memory) (estimated 3h)
- `MemoryService.get_short_term(conversation_id, n=15)` → last N textual messages
- `MemoryService.get_long_term(query_embedding, top_k=5)` → similarity search in `conversation_summaries_embeddings` and `lead_embeddings`
- `MemoryService.summarize_and_index(conversation_id)` → generates summary when closing a conversation
- Unit tests with synthetic dataset

**DoD:** both methods work; the agent can query them.

### Milestone 7 — Conversationalist Agent (estimated 3h)
- `Conversationalist` maintains multi-turn threads
- Consumes dual memory via `MemoryService`
- Receives the already-classified `intent` and adjusts prompt by category
- Registers `agent_runs`

**DoD:** maintains a 3-4 turn thread with coherence and responds according to the detected intent.

### Milestone 8 — Evaluator / Confidence Gate (Gate 2) (estimated 2h)
- `Evaluator.evaluate(draft, context)` → `EvaluationResult(score, breakdown, should_send, reason)`
- Score on 3 axes: naturalness, relevance, risk
- Configurable threshold via settings
- Tests with good and bad drafts using `FakeLLMProvider`

**DoD:** obviously bad drafts are rejected; good drafts pass.

### Milestone 9 — Orchestrator (estimated 2h)
- `Orchestrator` coordinates the flow:
  1. Receives `reply.received` event
  2. Loads conversation and memory
  3. Calls `IntentClassifier`
  4. If handoff → notifies Slack (can be mock); if not → calls the appropriate agent
  5. Calls `Evaluator`
  6. If approved → persists and sends via `ChannelAdapter`; if not → escalates
- Integration test of the complete happy path

**DoD:** a `reply.received` event traverses the entire pipeline without errors with synthetic data.

### Milestone 10 — n8n workflow via MCP (estimated 3h)
- Create workflow in n8n using the MCP:
  - Trigger: webhook for new lead
  - HTTP node calls `/agents/ingest` on the API
  - Trigger: webhook for incoming reply (simulating LinkedIn)
  - HTTP node calls `/events/reply` on the API
- Workflow exported to `n8n/workflows/`
- README explains how to import and run

**DoD:** triggering a webhook from curl traverses the full flow and leaves a record in Supabase.

### Milestone 11 — Synthetic dataset and end-to-end demo (estimated 2h)
- Create 5-10 realistic Mexican B2B fintech leads
- Create sequence of simulated replies covering: interest, objection, meeting intent
- Script `demo/run_happy_path.py` that triggers the full flow
- Validate that generated responses are coherent and "indistinguishable"

**DoD:** run `python demo/run_happy_path.py` and the full pipeline runs visibly; the database is in clean state for recording the video.

### Milestone 12 — Video polish (estimated 2h, optional depending on time)
- Readable logs for screen recording
- Small CLI dashboard or prepared SQL queries to show metrics (`cost_per_message`, `confidence_score_avg`, `intent_distribution`)
- Final README with reproducible instructions

**DoD:** the repo looks professional on first scroll.

---

## 9. Tool access (MCP)

**You have MCP access to n8n.** Use it to:
- Create workflows (instead of editing JSON manually)
- List existing workflows
- Trigger test webhooks
- Export workflows to JSON for versioning in `n8n/workflows/`

**If you need information from Supabase, Anthropic API, or another tool,** say so explicitly. Do not assume you have access to something not listed.

---

## 10. Anti-patterns to avoid

These mistakes are recurring in fast projects. Avoid them actively.

- **Over-abstraction.** Do not create `BaseAbstractFactoryStrategy` for something with only one implementation.
- **Tests with nested mocks.** If you need 4 mocks for a test, the design is wrong.
- **Hardcoding models or prompts.** Models go through config; prompts live versioned in `llm/prompts/`.
- **Empty or noisy logs.** Log system decisions (which intent was detected, which model the router chose, which score the evaluator gave). Do not log "function called" for every function.
- **Try/except with `pass` or `print(e)`.** Errors are propagated or handled with judgment.
- **Long functions.** If it goes past 50 lines, there is a cohesion problem.
- **Coupling to an LLM SDK in business logic.** Everything goes through `LLMGateway`.
- **Forgetting `tenant_id`.** All queries filter by tenant. RLS is the last guardian, not the first.
- **"I'll fix it later."** There is no later. Either fix it now, or document it as explicit debt.

---

## 11. Global Definition of Done

The prototype is done when:

- [ ] Milestones 0-11 completed
- [ ] `pytest` passes without failures
- [ ] `ruff check .` without errors
- [ ] End-to-end demo runs without manual intervention
- [ ] Root README allows an external person to clone, install, and run in under 10 minutes
- [ ] Basic metrics are visible at the end of the happy path
- [ ] The code reflects the decisions in the architecture document

The video is recorded **only after** this. Not before.

---

## 12. Communication with the author

- **Language:** Spanish by default. English for standard technical jargon (commits, docstrings).
- **Tone:** direct, no fluff. Short reports.
- **When you finish a milestone:** short message with: files created, tests passing, validation command, suggested next milestone.
- **When in doubt:** ask before improvising.
- **When you find debt:** document it explicitly in code (`# DEBT: reason. see issue X.`) and report it.

---

## 13. Quick references

- Architecture document: `docs/arquitectura-zolvo.md`
- Original challenge brief: `docs/zolvo-challenge.pdf` (if uploaded)
- Stack docs:
  - Supabase: https://supabase.com/docs
  - pgvector: https://github.com/pgvector/pgvector
  - FastAPI: https://fastapi.tiangolo.com
  - n8n: https://docs.n8n.io

---

## 14. Expected first action

When a development session starts, your first action is:

1. Read `CLAUDE.md` (this file) in full
2. Read `docs/arquitectura-zolvo.md` in full
3. Produce an **attack plan for Milestone 0** following the format in section 7
4. Wait for approval

Do not start creating files before that.
