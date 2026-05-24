# Zolvo AI Sales & Growth Engine — Prototipo

> Propuesta técnica · Coding Fellowship · Makers Admission 2026-2

Prototipo funcional del pipeline de ventas outbound con agentes de IA: enrichment de leads, generación de mensajes, clasificación de intent, memoria contextual y agendamiento automático.

## Prerequisitos

- Python 3.11+
- Cuenta en [supabase.com](https://supabase.com) (plan gratuito funciona)
- Al menos una API key: OpenAI (`OPENAI_API_KEY`) o Anthropic (`ANTHROPIC_API_KEY`)

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
pip install -r requirements-dev.txt   # incluye deps de test y lint

# 4. Variables de entorno
cp .env.example .env
# Edita .env con tus keys de Supabase y al menos un proveedor LLM

# 5. Supabase — correr migrations
# Opción A: pega el contenido de supabase/migrations/00000000000000_init.sql
#           en el SQL Editor de tu proyecto Supabase.
# Opción B (si tienes psql instalado):
psql "$DATABASE_URL" -f supabase/migrations/00000000000000_init.sql
psql "$DATABASE_URL" -f supabase/seed.sql

# 6. Verificar
ruff check .
pytest -q

# 7. Levantar la API
PYTHONPATH=src uvicorn zolvo.api.main:app --reload
# → http://localhost:8000/health
# → http://localhost:8000/docs
```

## Estructura

```
zolvo-prototype/
├── src/zolvo/
│   ├── api/            # FastAPI controllers y rutas
│   ├── agents/         # Agentes: Researcher, Copywriter, Conversationalist, Scheduler, Evaluator
│   ├── intent/         # Intent Classifier (Puerta 1)
│   ├── orchestrator/   # Orquestador del pipeline
│   ├── llm/            # LLM Gateway con Strategy pattern (OpenAI, Anthropic, Ollama, OpenRouter)
│   ├── memory/         # Memoria dual: textual (short-term) + pgvector (long-term)
│   ├── channels/       # Adapters de canal (LinkedIn mock, Email mock)
│   ├── repositories/   # Repository pattern para Supabase
│   ├── models/         # Pydantic + SQLAlchemy models
│   ├── events/         # Event bus (Supabase Realtime + outbox)
│   ├── observability/  # Logs estructurados con structlog
│   └── config.py       # Settings via pydantic-settings
├── tests/
│   ├── unit/           # Tests unitarios con FakeLLMProvider
│   └── integration/    # Happy path end-to-end
├── supabase/
│   ├── migrations/     # SQL versionado
│   └── seed.sql        # Tenant demo + leads ICP México (Hito 11)
├── n8n/workflows/      # Exports JSON de workflows (Hito 10)
└── docs/
    └── arquitectura-zolvo.md  # Diseño completo del sistema
```

## Referencias

- [Arquitectura del sistema](docs/arquitectura-zolvo.md) — C4, ADRs, modelo de datos, máquina de estados
- [CLAUDE.md](CLAUDE.md) — Guía operativa y hitos de desarrollo
- [Supabase setup](supabase/README.md)

## Demo end-to-end

Una vez completado el Hito 11:

```bash
python demo/run_happy_path.py
```

Esto ejecuta el flujo completo: ingesta de lead → mensaje outbound → respuesta del prospect → intent classification → respuesta multi-turn → detección de meeting intent → agendamiento.
