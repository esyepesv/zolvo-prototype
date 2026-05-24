# Zolvo AI Sales & Growth Engine — Prototipo

> Propuesta técnica · Coding Fellowship · Makers Admission 2026-2

Pipeline de ventas outbound multi-agente: enrichment de leads, generación de mensajes personalizados, clasificación de intent, memoria dual (textual + vectorial), y gate de confianza antes de enviar cada respuesta.

## Prerequisitos

- Python 3.11+
- Proyecto en [supabase.com](https://supabase.com) (plan gratuito funciona)
- Al menos una API key LLM: **OpenRouter** (`OPENROUTER_API_KEY`) recomendado

## Quickstart (< 10 min)

```bash
# 1. Clonar
git clone <repo-url>
cd zolvo-prototype

# 2. Entorno virtual + dependencias
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements-dev.txt

# 3. Variables de entorno
cp .env.example .env
# Editar .env — mínimo necesario:
#   SUPABASE_URL=https://<ref>.supabase.co
#   SUPABASE_ANON_KEY=...
#   SUPABASE_SERVICE_ROLE_KEY=...
#   OPENROUTER_API_KEY=...

# 4. Supabase — aplicar migrations
# Abrir SQL Editor en supabase.com y ejecutar en orden:
#   supabase/migrations/00000000000000_init.sql
#   supabase/migrations/00000000000001_domain_tables.sql
#   supabase/migrations/00000000000002_similarity_search.sql
#   supabase/seed.sql

# 5. Verificar
.venv/bin/ruff check .
PYTHONPATH=src .venv/bin/pytest -q
# → 54 passed

# 6. Levantar la API
PYTHONPATH=src .venv/bin/uvicorn zolvo.api.main:app --reload
# → http://localhost:8000/health  {"status":"ok"}
# → http://localhost:8000/docs    Swagger UI
```

## Demo end-to-end

Con la API corriendo en otra terminal:

```bash
PYTHONPATH=src .venv/bin/python demo/run_happy_path.py
```

Flujo completo en ~30s:

```
STEP 1: Ingest Lead
  Lead : Diego Ramírez — CTO @ CredIMex
  ✓ Subject: [mensaje outbound generado]
  ✓ Body:    [cuerpo personalizado con hooks del ICP]

STEP 2: Turn 1 — Interés inicial
  Intent  : meeting_intent
  Action  : ✓ SEND  (score: 0.900)  [8.2s]
  Draft:  [respuesta generada con memoria dual]

STEP 3: Turn 2 — Objeción de precio
  Intent  : objection_price
  Action  : ✓ SEND  (score: 0.867)  [7.1s]

STEP 4: Turn 3 — Intent de meeting
  Intent  : meeting_intent
  Action  : ✓ SEND  (score: 0.900)  [6.8s]

PIPELINE SUMMARY
  Intent path  : meeting_intent → objection_price → meeting_intent
  Action path  : send → send → send
  Avg conf score: 0.889
  Stages: ingest → classify → generate → evaluate → route  ✓
```

### Métricas post-demo

Pegar `demo/metrics.sql` en el SQL Editor de Supabase para ver:
- Costo por agente (tokens, USD, latencia)
- Distribución de confidence scores
- Distribución de intents detectados
- Totales del pipeline

## Stack

| Capa | Tecnología |
|---|---|
| API | Python 3.11+ · FastAPI · Pydantic v2 |
| Base de datos | Supabase · Postgres + pgvector + RLS multi-tenant |
| Acceso a datos | supabase-py async (REST API via HTTPS) |
| LLM Gateway | Strategy pattern: OpenRouter (default) · Anthropic · OpenAI · Ollama |
| Orquestación | n8n self-hosted |
| Observabilidad | structlog · `agent_runs` table (costo, latencia, tokens por agente) |

## Arquitectura del pipeline

```
Lead ingested
      │
      ▼
 Researcher ──→ enriched_data + lead_embedding
      │
      ▼
 Copywriter ──→ outbound message (subject + body)
      │
      ▼
 [Reply received]
      │
      ▼
 IntentClassifier (Gate 1)
      │
      ├─ should_handoff=True ──→ HANDOFF (human review)
      │
      └─ should_handoff=False
            │
            ▼
       Conversationalist (memoria dual)
            │  ├─ short-term: últimos N mensajes
            │  └─ long-term: pgvector similarity search
            ▼
       EvaluatorAgent (Gate 2)
            │  score = (naturalidad + relevancia + (1−riesgo)) / 3
            │
            ├─ score ≥ 0.70 ──→ SEND
            └─ score < 0.70 ──→ ESCALATE
```

## Estructura del proyecto

```
zolvo-prototype/
├── src/zolvo/
│   ├── api/            # FastAPI: /health, /agents/ingest, /events/reply
│   ├── agents/         # Researcher, Copywriter, Conversationalist, Evaluator
│   ├── intent/         # IntentClassifier — 9 categorías
│   ├── orchestrator/   # Pipeline coordinator (dos puertas)
│   ├── memory/         # MemoryService — short-term + long-term (pgvector)
│   ├── llm/            # LLM Gateway + providers + prompts versionados
│   ├── repositories/   # Repository pattern — supabase-py async
│   ├── models/         # Pydantic domain models
│   └── config.py       # Settings via pydantic-settings
├── demo/
│   ├── run_happy_path.py   # Script demo end-to-end
│   └── metrics.sql         # Queries de métricas para Supabase SQL Editor
├── supabase/
│   ├── migrations/         # SQL versionado (3 archivos)
│   └── seed.sql            # Tenant demo
├── n8n/workflows/          # Exports JSON de workflows n8n
├── tests/
│   ├── unit/               # 49 tests con FakeLLMProvider (sin red)
│   └── integration/        # 5 tests contra Supabase real
└── docs/
    └── arquitectura-zolvo.md   # C4, ADRs, modelo de datos, máquina de estados
```

## Hitos completados

| # | Hito | Estado |
|---|---|---|
| 0 | Setup base (FastAPI, CI, Supabase schema) | ✅ |
| 1 | LLM Gateway con Strategy pattern | ✅ |
| 2 | Modelo de datos y repositorios (RLS multi-tenant) | ✅ |
| 3 | Researcher Agent (enrichment + embeddings) | ✅ |
| 4 | Copywriter Agent (mensaje outbound personalizado) | ✅ |
| 5 | Intent Classifier (Puerta 1, 9 categorías) | ✅ |
| 6 | Memory Service (short-term + long-term pgvector) | ✅ |
| 7 | Conversationalist Agent (multi-turn con memoria dual) | ✅ |
| 8 | Evaluator / Confidence Gate (Puerta 2, 3 ejes) | ✅ |
| 9 | Orchestrator (pipeline coordinado dos puertas) | ✅ |
| 10 | FastAPI endpoints + n8n workflows via API | ✅ |
| 11 | Demo end-to-end — happy path funcional | ✅ |
| 12 | Polish para el video | ✅ |

Ver [PROGRESS.md](PROGRESS.md) para el estado detallado y decisiones técnicas.

## Referencias

- [Arquitectura del sistema](docs/arquitectura-zolvo.md) — C4, ADRs, modelo de datos, máquina de estados
- [PROGRESS.md](PROGRESS.md) — estado de desarrollo y decisiones tomadas
- [Supabase setup](supabase/README.md)
