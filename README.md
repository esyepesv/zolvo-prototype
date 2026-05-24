# Zolvo AI Sales & Growth Engine — Prototipo

> Propuesta técnica · Coding Fellowship · Makers Admission 2026-2

Prototipo funcional del pipeline de ventas outbound con agentes de IA: enrichment de leads, generación de mensajes, clasificación de intent, memoria contextual y agendamiento automático.

## Prerequisitos

- Python 3.11+
- Proyecto en [supabase.com](https://supabase.com) (plan gratuito funciona)
- Al menos una API key LLM: OpenRouter (`OPENROUTER_API_KEY`) recomendado, o Anthropic/OpenAI

## Quickstart

```bash
# 1. Clonar
git clone <repo-url>
cd zolvo-prototype

# 2. Entorno virtual
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Dependencias
pip install --upgrade pip
pip install -r requirements-dev.txt

# 4. Variables de entorno
cp .env.example .env
# Edita .env con tus keys de Supabase y al menos un proveedor LLM

# 5. Supabase — aplicar migrations
# Abre el SQL Editor en supabase.com y ejecuta en orden:
#   supabase/migrations/00000000000000_init.sql
#   supabase/migrations/00000000000001_domain_tables.sql
#   supabase/seed.sql

# 6. Verificar
ruff check .
pytest -q   # 12 tests: 7 unit + 5 integration

# 7. Levantar la API
PYTHONPATH=src uvicorn zolvo.api.main:app --reload
# → http://localhost:8000/health
# → http://localhost:8000/docs
```

## Stack

| Capa | Tecnología |
|---|---|
| API | Python 3.11+ · FastAPI · Pydantic v2 |
| Base de datos | Supabase (Postgres + pgvector + RLS multi-tenant) |
| Acceso a datos | supabase-py async (REST API vía HTTPS) |
| LLM Gateway | Strategy pattern: OpenRouter · Anthropic · OpenAI · Ollama Cloud |
| Orquestación | n8n (workflows visibles para sales rep) |
| Observabilidad | structlog + `agent_runs` table (costo, latencia, tokens por agente) |

## Estructura

```
zolvo-prototype/
├── src/zolvo/
│   ├── api/            # FastAPI: /health, /agents, /events
│   ├── agents/         # Agentes: Researcher, Copywriter, Conversationalist, Scheduler, Evaluator
│   ├── intent/         # Intent Classifier (Puerta 1 del pipeline)
│   ├── orchestrator/   # Orquestador del pipeline multi-agente
│   ├── llm/            # LLM Gateway con Strategy pattern
│   │   ├── base.py         # LLMProvider ABC, LLMRequest, LLMResponse
│   │   ├── gateway.py      # Routing por costo/criticidad
│   │   ├── fake_provider.py
│   │   ├── openrouter_provider.py
│   │   ├── anthropic_provider.py
│   │   ├── openai_provider.py
│   │   ├── ollama_provider.py
│   │   └── prompts/        # Prompts versionados por agente
│   ├── memory/         # Memoria dual: textual (short-term) + pgvector (long-term)
│   ├── channels/       # Adapters de canal (LinkedIn mock, Email mock)
│   ├── repositories/   # Repository pattern — supabase-py async
│   │   ├── base.py
│   │   ├── leads.py
│   │   ├── conversations.py
│   │   ├── messages.py
│   │   └── agent_runs.py
│   ├── models/         # Pydantic domain models (Lead, Conversation, Message, AgentRun)
│   ├── events/         # Event bus (Supabase Realtime + outbox pattern)
│   ├── observability/  # Logs estructurados
│   └── config.py       # Settings via pydantic-settings
├── tests/
│   ├── unit/           # Tests con FakeLLMProvider (sin red)
│   └── integration/    # Tests contra Supabase real
├── supabase/
│   ├── migrations/     # SQL versionado (init + domain_tables)
│   └── seed.sql        # Tenant demo + leads ICP México
├── n8n/workflows/      # Exports JSON de workflows (Hito 10)
└── docs/
    └── arquitectura-zolvo.md
```

## Hitos completados

| # | Hito | Estado |
|---|---|---|
| 0 | Setup base (FastAPI, CI, Supabase schema) | ✅ |
| 1 | LLM Gateway con Strategy pattern | ✅ |
| 2 | Modelo de datos y repositorios | ✅ |
| 3–12 | Agentes, Orchestrator, n8n, Demo | ⏳ |

Ver [PROGRESS.md](PROGRESS.md) para el estado detallado y [CLAUDE.md](CLAUDE.md) para la guía operativa.

## Demo end-to-end

Una vez completado el Hito 11:

```bash
python demo/run_happy_path.py
```

Flujo: ingesta de lead → enriquecimiento → mensaje outbound → respuesta del prospect → intent classification → respuesta multi-turn → detección de meeting intent → agendamiento.

## Referencias

- [Arquitectura del sistema](docs/arquitectura-zolvo.md) — C4, ADRs, modelo de datos, máquina de estados
- [PROGRESS.md](PROGRESS.md) — estado de desarrollo y decisiones tomadas
- [Supabase setup](supabase/README.md)
