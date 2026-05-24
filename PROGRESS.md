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
| Hito actual | **Hito 6 — COMPLETADO** |
| Próximo hito | **Hito 7 — Conversationalist Agent** |
| Último commit | `feat: Hito 6 — Memory Service con memoria dual (textual + semántica)` |

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
| 7 | Conversationalist Agent | ⏳ PENDIENTE | — |
| 8 | Evaluator / Confidence Gate (Puerta 2) | ⏳ PENDIENTE | — |
| 9 | Orchestrator | ⏳ PENDIENTE | — |
| 10 | n8n workflow vía MCP | ⏳ PENDIENTE | — |
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

## Próximo hito — Hito 7: Conversationalist Agent

**Prerequisito:** ✅ Memory Service funcional (short + long term)

**Qué construir:**

1. `src/zolvo/agents/conversationalist.py` — `Conversationalist`:
   - Mantiene threads multi-turn
   - Consume memoria dual vía `MemoryService`
   - Recibe el `intent` ya clasificado y ajusta su comportamiento
2. `src/zolvo/llm/prompts/conversationalist.txt` — prompt español para la respuesta
3. Tests unitarios

**DoD:** mantiene un thread coherente respondiendo de forma acorde al intent detectado y usando su memoria.

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
