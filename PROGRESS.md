# PROGRESS — Zolvo AI Sales Engine Prototype

> **Este archivo es la fuente de verdad del estado del desarrollo.**
> Un agente que retoma el trabajo DEBE leer este archivo antes de cualquier acción,
> luego leer `CLAUDE.md` y `docs/arquitectura-zolvo.md`.

---

## Estado general

| Campo | Valor |
|---|---|
| Deadline absoluto | 25 may 2026, 17:58 COT |
| Fecha inicio | 24 may 2026 |
| Tiempo disponible | ~30h efectivas |
| Hito actual | **Hito 10 — COMPLETADO** |
| Próximo hito | **Hito 11 — Dataset sintético + demo end-to-end** |
| Último commit | `feat: Hito 10 — n8n workflows creados vía API` |

---

## Mapa de hitos

| # | Nombre | Estado | Verificado |
|---|---|---|---|
| 0 | Setup base | ✅ COMPLETADO | ✅ |
| 1 | LLM Gateway (Strategy pattern) | ✅ COMPLETADO | ✅ |
| 2 | Modelo de datos y repositorios | ✅ COMPLETADO | ✅ |
| 3 | Researcher Agent | ✅ COMPLETADO | ✅ |
| 4 | Copywriter Agent | ✅ COMPLETADO | ✅ |
| 5 | Intent Classifier (Puerta 1) | ✅ COMPLETADO | ✅ |
| 6 | Memory Service (memoria dual) | ✅ COMPLETADO | ✅ |
| 7 | Conversationalist Agent | ✅ COMPLETADO | ✅ |
| 8 | Evaluator / Confidence Gate (Puerta 2) | ✅ COMPLETADO | ✅ |
| 9 | Orchestrator | ✅ COMPLETADO | ✅ |
| 10 | n8n workflow vía MCP | ✅ COMPLETADO | ✅ |
| 11 | Dataset sintético + demo end-to-end | ⏳ PENDIENTE | — |
| 12 | Polish para el video | ⏳ PENDIENTE | — |

---

## Setup del entorno (para un agente nuevo)

```bash
# 1. Ir al directorio
cd /home/stiven/Projects/Makers/zolvo-prototype

# 2. Entorno virtual
# NOTA WSL: python3.12-venv puede no estar instalado.
# Si falla python3 -m venv .venv, usar bootstrap:
python3 -m venv --without-pip .venv
source .venv/bin/activate
curl -s https://bootstrap.pypa.io/get-pip.py | python3
pip install -r requirements-dev.txt

# Si ya existe .venv funcional:
source .venv/bin/activate
pip install -r requirements-dev.txt

# 3. Variables de entorno
cp .env.example .env
# El autor tiene las keys reales — editar .env antes de correr hitos 1+

# 4. Verificar estado base
bash scripts/verify.sh
```

---

## Decisiones técnicas ya tomadas

| Decisión | Justificación |
|---|---|
| pip + requirements.txt (no uv/poetry) | Elección del autor |
| Layout `src/` | Evita import ambigüedad sin instalar el paquete |
| Supabase Cloud (proyecto "Challenge Zolvo") | Creado en supabase.com, región us-west-1 |
| CI: Python 3.11 + 3.12 | Sistema local solo tiene 3.12; CI valida ambas |
| `pyproject.toml` solo para tooling | Derivado de decisión pip |
| structlog con PrintLoggerFactory | `add_logger_name` removido (incompatible con PrintLogger) |
| Git branch: `main` | Inicializado en Hito 0 |
| `supabase-py` en vez de SQLAlchemy+asyncpg | Host directo de Supabase es solo IPv6 en WSL2; Supavisor pooler no reconoce el proyecto; supabase-py usa REST/HTTPS vía CloudFlare IPv4 |
| Modelos Pydantic (no ORM) | Consecuencia del cambio a supabase-py — dict de respuesta se mapea directamente |
| PREFERRED_LLM_PROVIDER=openrouter | Más barato para el demo; fallback: ollama → anthropic → openai |
| **Despliegue local** | FastAPI en `localhost:8000`; n8n self-hosted en `n8n.stivenyepes.com` (misma máquina); Supabase Cloud para DB |
| n8n self-hosted en n8n.stivenyepes.com | Ya desplegado; se configura via MCP. URL en `N8N_BASE_URL`. |

---

## Estado detallado por hito completado

### ✅ Hito 0 — Setup base

**DoD cumplido:** `ruff check .` → OK | `pytest -q` → 1 passed | `GET /health` → `{"status":"ok","env":"dev"}`

**Archivos creados:**
- `src/zolvo/config.py` — Settings (pydantic-settings, lru_cache)
- `src/zolvo/api/main.py` — FastAPI app con `/health` y lifespan
- `src/zolvo/api/deps.py` — placeholder
- `src/zolvo/observability/logging.py` — structlog configurado
- Todos los `__init__.py` de la estructura `src/zolvo/`
- `requirements.txt` / `requirements-dev.txt`
- `pyproject.toml` (ruff + pytest config)
- `.gitignore` / `.env.example`
- `supabase/migrations/00000000000000_init.sql` — extensiones + tabla `tenants` + RLS
- `supabase/seed.sql` — tenant demo UUID `00000000-0000-0000-0000-000000000001`
- `supabase/README.md`
- `.github/workflows/ci.yml` — ruff + pytest en Python 3.11 y 3.12
- `README.md`
- `n8n/workflows/.gitkeep`
- `scripts/verify.sh` — script de verificación

**Supabase:** ✅ Migrations aplicadas vía MCP. Proyecto "Challenge Zolvo" (id: `diweoapyicjomzljkohx`, región us-west-1). Tenant demo insertado. Variables en `.env` ya configuradas.

**Verificación:** `bash scripts/verify.sh` → todos los checks pasan

---

### ✅ Hito 1 — LLM Gateway (Strategy pattern)

**DoD cumplido:** `ruff check .` → OK | `pytest -v` → 7 passed | `FakeLLMProvider` + `LLMGateway` importables | prueba real omitida hasta que haya keys en `.env`

**Archivos creados:**
- `src/zolvo/llm/base.py` — `LLMRequest`, `LLMResponse`, `LLMProvider` (ABC), `LLMProviderError`, `TaskType`
- `src/zolvo/llm/fake_provider.py` — `FakeLLMProvider` con `overrides` por `task_type`
- `src/zolvo/llm/anthropic_provider.py` — Anthropic Messages API via httpx, retries con tenacity
- `src/zolvo/llm/openai_provider.py` — OpenAI Chat Completions API via httpx, retries con tenacity
- `src/zolvo/llm/gateway.py` — `LLMGateway`: routing por `preferred_llm_provider`, fallback automático
- `tests/unit/test_llm_gateway.py` — 6 tests unitarios (todos con `FakeLLMProvider`)

**Archivos modificados:**
- `src/zolvo/config.py` — agrega `preferred_llm_provider: str = "anthropic"`
- `.env.example` — agrega `PREFERRED_LLM_PROVIDER=anthropic`

**Modelos por task_type:**
- `classification` / `generation_standard`: `claude-haiku-4-5-20251001` (Anthropic) / `gpt-4o-mini` (OpenAI)
- `generation_critical`: `claude-sonnet-4-6` (Anthropic) / `gpt-4o` (OpenAI)

**Pendiente:** prueba funcional con provider real (requiere key en `.env`). El verify.sh la corre automáticamente cuando detecta `ANTHROPIC_API_KEY` o `OPENAI_API_KEY`.

**Verificación:** `bash scripts/verify.sh 1` → todos los checks pasan

---

### ✅ Hito 2 — Modelo de datos y repositorios

**DoD cumplido:** `ruff check .` → OK | `pytest -q` → 12 passed | integración real contra Supabase Cloud

**Decisión técnica:** se usó `supabase-py` (REST API vía HTTPS) en lugar de SQLAlchemy + asyncpg directo. El host directo de Supabase (`db.[ref].supabase.co`) solo tiene IPv6, no alcanzable desde WSL2. El pooler de Supavisor (IPv4) retornó "Tenant or user not found" para este proyecto. supabase-py resuelve al CDN CloudFlare (IPv4) sin problema.

**Archivos creados:**
- `supabase/migrations/00000000000001_domain_tables.sql` — 7 tablas con RLS + índices (aplicadas vía MCP)
- `src/zolvo/models/domain.py` — Pydantic models: `Lead`, `Conversation`, `Message`, `AgentRun`, `EventOutbox`
- `src/zolvo/repositories/base.py` — `BaseRepository[M]` genérico con supabase-py async
- `src/zolvo/repositories/leads.py` — `LeadRepository`
- `src/zolvo/repositories/conversations.py` — `ConversationRepository`
- `src/zolvo/repositories/messages.py` — `MessageRepository`
- `src/zolvo/repositories/agent_runs.py` — `AgentRunRepository`
- `src/zolvo/api/deps.py` — `get_supabase()` dependency (service_role key)
- `tests/integration/test_repositories.py` — 5 integration tests (create, read, cross-tenant isolation)

**Tests:** 7 unit + 5 integration = 12 total pasando

---

### ✅ Hito 3 — Researcher Agent

**DoD cumplido:** `ruff check .` → OK | `pytest -q` → 17 passed

**Archivos creados/modificados:**
- `src/zolvo/agents/base.py` — `AgentBase` abstracto con DI de `LLMGateway`
- `src/zolvo/agents/researcher.py` — `ResearcherAgent.run(lead_id, tenant_id)` → enriquece lead + embedding
- `src/zolvo/llm/prompts/researcher.txt` — prompt español ICP mexicano fintech (8 campos JSON)
- `src/zolvo/llm/base.py` — añadido `EmbeddingResponse` y `embed()` default con `NotImplementedError`
- `src/zolvo/llm/gateway.py` — añadido `embed()` con routing OpenAI-first
- `src/zolvo/llm/openai_provider.py` — añadido `embed()` + constantes `_EMBED_URL`, `_EMBED_MODEL`
- `src/zolvo/llm/fake_provider.py` — añadido `embed()` → vector `[0.0] * 1536`
- `src/zolvo/repositories/leads.py` — añadido `save_embedding()` upsert a `lead_embeddings`
- `tests/unit/test_researcher.py` — 5 tests unitarios

---

### ✅ Hito 4 — Copywriter Agent

**DoD cumplido:** `ruff check .` → OK | `pytest -q` → 22 passed

**Archivos creados:**
- `src/zolvo/agents/copywriter.py` — `CopywriterAgent.run(lead_id, tenant_id)` → mensaje outbound personalizado
- `src/zolvo/llm/prompts/copywriter.txt` — prompt español con reglas B2B consultivo México
- `tests/unit/test_copywriter.py` — 5 tests (JSON estructurado, fallback non-JSON, sin enrichment, not-found, agent_run)

---

### ✅ Hito 5 — Intent Classifier (Puerta 1)

**DoD cumplido:** `ruff check .` → OK | `pytest -q` → 33 passed | casos DoD verificados

**Archivos creados:**
- `src/zolvo/intent/classifier.py` — `IntentClassifier.classify(message, context)` → `IntentResult`
- `src/zolvo/llm/prompts/intent_classifier.txt` — prompt con 9 categorías y reglas de handoff
- `tests/unit/test_intent_classifier.py` — 11 tests (DoD + todas las categorías + edge cases)

**Categorías con handoff=True:** `complaint`, `complex_technical`, `out_of_scope`, `opt_out`

---

### ✅ Hito 6 — Memory Service (memoria dual)

**DoD cumplido:** `ruff check .` → OK | `pytest -q` → 38 passed

**Archivos creados:**
- `src/zolvo/memory/service.py` — `MemoryService.get_short_term()`, `get_long_term()`, `summarize_and_index()`
- `src/zolvo/models/domain.py` — añadidos `ConversationSummary` y `MemoryMatch`
- `src/zolvo/llm/prompts/summarizer.txt` — prompt español denso optimizado para vectorización
- `supabase/migrations/00000000000002_similarity_search.sql` — `match_lead_embeddings` y `match_conversation_summaries`
- `tests/unit/test_memory_service.py` — 5 tests con mocks y FakeLLMProvider

---

### ✅ Hito 7 — Conversationalist Agent

**DoD cumplido:** `ruff check .` → OK | `pytest -q` → 43 passed

**Archivos creados:**
- `src/zolvo/agents/conversationalist.py` — `ConversationalistAgent.run()` con memoria dual, guía por intent, registro de `agent_runs`
- `src/zolvo/llm/prompts/conversationalist.txt` — prompt español B2B México con 8 reglas de redacción
- `tests/unit/test_conversationalist.py` — 5 tests (draft, memoria dual, agent_run, memoria vacía, 9 intents)

**Decisión técnica:** `get_long_term()` recibe `tenant_id` como kwarg (no posicional) para permitir assertions en tests.

---

### ✅ Hito 8 — Evaluator / Confidence Gate

**DoD cumplido:** `ruff check .` → OK | `pytest -q` → 49 passed

**Archivos creados:**
- `src/zolvo/agents/evaluator.py` — `EvaluatorAgent.evaluate()`: score combinado (naturalidad + relevancia + (1-riesgo)) / 3, umbral configurable, registro de `agent_runs`
- `src/zolvo/llm/prompts/evaluator.txt` — prompt español con 3 ejes de evaluación; `{{}}` escapados para `str.format()`
- `tests/unit/test_evaluator.py` — 6 tests: draft bueno pasa, draft malo bloqueado, alto riesgo bloqueado, breakdown poblado, agent_run registrado, umbral configurable

**Nota técnica:** braces literales `{}` en el ejemplo JSON del prompt deben estar escapados como `{{}}` para compatibilidad con `str.format()`.

---

### ✅ Hito 9 — Orchestrator

**DoD cumplido:** `ruff check .` → OK | `pytest -q` → 54 passed

**Archivos creados:**
- `src/zolvo/orchestrator/orchestrator.py` — `Orchestrator.handle_reply()`: Gate 1 (IntentClassifier) → si handoff devuelve inmediato; si no → ConversationalistAgent → Gate 2 (EvaluatorAgent) → `"send"` o `"escalate"`
- `tests/unit/test_orchestrator.py` — 5 tests: handoff salta generación, draft bueno → send, baja confianza → escalate, todas las etapas se invocan, context del evaluador incluye intent

**Diseño:** el Orchestrator solo orquesta — no tiene acceso directo a memoria ni a repositorios; el draft se propaga siempre en `escalate` para que el humano pueda revisarlo.

---

### ✅ Hito 10 — n8n workflow vía API

**DoD cumplido:** 54 tests pasando | ruff OK | 2 workflows activos en n8n

**Archivos creados:**
- `src/zolvo/schemas.py` — `IngestRequest`, `IngestResponse`, `ReplyRequest`, `ReplyResponse`
- `src/zolvo/api/routes/agents.py` — `POST /agents/ingest`: crea lead → researcher → conversación → copywriter
- `src/zolvo/api/routes/events.py` — `POST /events/reply`: persiste mensaje → Orchestrator → persiste draft si send
- `src/zolvo/api/deps.py` — factory functions para todos los agentes con DI FastAPI
- `src/zolvo/api/main.py` — registra routers `agents` y `events`
- `n8n/workflows/zolvo-new-lead-ingestion.json` — workflow exportado (id: `5VEfQA0VC44iM6Zs`)
- `n8n/workflows/zolvo-reply-received.json` — workflow exportado (id: `LDjEhcuc7DMNRywX`)

**Nota técnica:** n8n MCP no estaba configurado en sesión; workflows creados vía REST API (`POST /api/v1/workflows`). `B008` (Depends en args) ignorado en ruff — es el patrón estándar FastAPI.

**Webhooks activos en n8n:**
- `POST https://n8n.stivenyepes.com/webhook/zolvo-new-lead` → `/agents/ingest`
- `POST https://n8n.stivenyepes.com/webhook/zolvo-reply` → `/events/reply`

---

## Próximo hito — Hito 11: Dataset sintético + demo end-to-end

**Prerequisito:** ✅ Pipeline completo (API + n8n + Orchestrator)

**Qué construir:**

1. `supabase/seed_demo.sql` — 5 leads realistas de fintech B2B mexicana + 1 conversación con 3-4 mensajes
2. `demo/run_happy_path.py` — script que:
   - Crea lead vía `POST /agents/ingest`
   - Simula 3 turnos de respuesta vía `POST /events/reply` (interested → objection_price → meeting_intent)
   - Imprime en consola el estado al final (leads, agent_runs, cost, intent_distribution)
3. Validar que las respuestas son coherentes

**DoD:** `python demo/run_happy_path.py` corre sin errores y muestra el pipeline completo.

---

## Protocolo para un agente que retoma

1. **Leer `PROGRESS.md`** — entender estado actual, hito en curso, y próximo
2. **Leer `CLAUDE.md`** — reglas operativas y convenciones
3. **Leer sección relevante de `docs/arquitectura-zolvo.md`** — ADR y modelo de datos del hito
4. **Correr `bash scripts/verify.sh`** — confirmar que el estado base está limpio
5. **Producir plan** en el formato de `CLAUDE.md` §7 y esperar aprobación
6. **Implementar** el hito
7. **Correr `bash scripts/verify.sh`** al finalizar
8. **Actualizar `PROGRESS.md`**: mover hito a ✅, actualizar "Estado general", agregar sección de detalle, actualizar "Próximo hito"
9. **Hacer commit** con mensaje conventional

---

## Variables de entorno necesarias por hito

| Variable | Hito donde se necesita por primera vez |
|---|---|
| `OPENAI_API_KEY` o `ANTHROPIC_API_KEY` | Hito 1 (LLM Gateway real) |
| `DATABASE_URL` | Hito 2 (repositorios) |
| `SUPABASE_URL` / `SUPABASE_ANON_KEY` / `SUPABASE_SERVICE_ROLE_KEY` | Hito 2 |
| `DEFAULT_TENANT_ID` | Hito 2 |
| `CONFIDENCE_THRESHOLD` | Hito 8 |
| `DEBOUNCE_MIN/MAX_SECONDS` | Hito 9 |
