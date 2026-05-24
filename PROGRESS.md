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
| Hito actual | **Hito 2 — COMPLETADO** |
| Próximo hito | **Hito 3 — Researcher Agent** |
| Último commit | `feat: Hito 2 — modelo de datos y repositorios con supabase-py` |

---

## Mapa de hitos

| # | Nombre | Estado | Verificado |
|---|---|---|---|
| 0 | Setup base | ✅ COMPLETADO | ✅ |
| 1 | LLM Gateway (Strategy pattern) | ✅ COMPLETADO | ✅ |
| 2 | Modelo de datos y repositorios | ✅ COMPLETADO | ✅ |
| 3 | Researcher Agent | ⏳ PENDIENTE | — |
| 4 | Copywriter Agent | ⏳ PENDIENTE | — |
| 5 | Intent Classifier (Puerta 1) | ⏳ PENDIENTE | — |
| 6 | Memory Service (memoria dual) | ⏳ PENDIENTE | — |
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

## Próximo hito — Hito 3: Researcher Agent

**Prerequisito:** ✅ Supabase configurado, repositorios funcionando, supabase-py async disponible.

**Qué construir:**

1. `src/zolvo/agents/base.py` — `AgentBase` abstracto con `run()` async y acceso a `LLMGateway` + `AgentRunRepository`
2. `src/zolvo/agents/researcher.py` — `ResearcherAgent.run(lead_id)`:
   - Consulta el lead desde `LeadRepository`
   - Genera enrichment (industria, ICP fit, contexto de empresa) vía `LLMGateway` con `task_type="generation_standard"`
   - Genera embedding del perfil via API de embeddings (OpenAI `text-embedding-3-small` o equivalente)
   - Persiste resultado en `leads.enriched_data` y en `lead_embeddings`
   - Registra `agent_runs` con costo + latencia
3. `src/zolvo/llm/prompts/researcher.txt` — prompt de enrichment en español
4. Tests unitarios con `FakeLLMProvider` y un lead sintético

**DoD:** `researcher.run(lead_id)` enriquece un lead de prueba y guarda el embedding en Supabase.

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
