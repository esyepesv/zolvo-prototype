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
| Hito actual | **Hito 0 — COMPLETADO** |
| Próximo hito | **Hito 1 — LLM Gateway** |
| Último commit | `docs: add PROGRESS.md tracking + scripts/verify.sh` |

---

## Mapa de hitos

| # | Nombre | Estado | Verificado |
|---|---|---|---|
| 0 | Setup base | ✅ COMPLETADO | ✅ |
| 1 | LLM Gateway (Strategy pattern) | ⏳ PENDIENTE | — |
| 2 | Modelo de datos y repositorios | ⏳ PENDIENTE | — |
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
| Supabase Cloud | El autor crea el proyecto en supabase.com |
| CI: Python 3.11 + 3.12 | Sistema local solo tiene 3.12; CI valida ambas |
| `pyproject.toml` solo para tooling | Derivado de decisión pip |
| structlog con PrintLoggerFactory | `add_logger_name` removido (incompatible con PrintLogger) |
| Git branch: `main` | Inicializado en Hito 0 |

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

**Supabase:** migrations escritas pero NO ejecutadas. El autor debe:
1. Crear proyecto en supabase.com
2. Correr `supabase/migrations/00000000000000_init.sql` en el SQL Editor
3. Correr `supabase/seed.sql`
4. Llenar `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` en `.env`

**Verificación:** `bash scripts/verify.sh` → todos los checks pasan

---

## Próximo hito — Hito 1: LLM Gateway

**Qué construir:**

1. `src/zolvo/llm/base.py` — interfaz `LLMProvider` + dataclasses `LLMRequest` / `LLMResponse`
2. `src/zolvo/llm/openai_provider.py` — implementación OpenAI via httpx async
3. `src/zolvo/llm/anthropic_provider.py` — implementación Anthropic via httpx async
4. `src/zolvo/llm/fake_provider.py` — `FakeLLMProvider` con respuestas predefinidas (para tests)
5. `src/zolvo/llm/gateway.py` — `LLMGateway` con routing por `task_type`:
   - `classification` → modelo barato (haiku / gpt-4o-mini)
   - `generation_critical` → modelo premium (sonnet / gpt-4o)
   - `generation_standard` → modelo intermedio
6. Tests unitarios: routing elige proveedor correcto; `FakeLLMProvider` retorna predefinido

**DoD:** `gateway.complete(task_type="classification", prompt="...")` funciona con al menos 2 proveedores reales (requiere keys en `.env`).

**Modelos por task_type (por costo):**
- `classification`: `claude-haiku-4-5` (Anthropic) o `gpt-4o-mini` (OpenAI)
- `generation_critical`: `claude-sonnet-4-6` (Anthropic) o `gpt-4o` (OpenAI)
- `generation_standard`: `claude-haiku-4-5` o `gpt-4o-mini`

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
