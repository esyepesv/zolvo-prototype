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

---

## Cómo funciona el sistema

El sistema es un **pipeline de ventas outbound completamente automatizado**. Toma un lead (nombre, empresa, rol) y lleva la conversación desde el primer mensaje hasta detectar cuándo el prospecto quiere una reunión — sin intervención humana salvo en casos que lo requieran.

### Los agentes

| Agente | Qué hace | Modelo usado |
|---|---|---|
| **Researcher** | Analiza al lead y genera un perfil de ICP: fit, pain points, hooks de conversación, tamaño de empresa. Guarda un embedding semántico para RAG. | `claude-haiku-4.5` (barato) |
| **Copywriter** | Genera el primer mensaje outbound: subject + body personalizados con los hooks del Researcher. Devuelve JSON `{subject, body, channel}`. | `claude-haiku-4.5` |
| **IntentClassifier** | Clasifica cada respuesta del prospecto en una de 9 categorías. Decide si el agente puede responder o si se necesita un humano. | `claude-haiku-4.5` (temperatura 0.1) |
| **Conversationalist** | Genera la respuesta multi-turn. Usa memoria dual: los últimos 15 mensajes del hilo + búsqueda semántica en embeddings históricos. Adapta el tono según el intent detectado. | `claude-haiku-4.5` |
| **Evaluator** | Evalúa el borrador antes de enviarlo en 3 ejes: naturalidad (¿suena humano?), relevancia (¿responde al intent?), riesgo (¿podría dañar la relación?). Bloquea el envío si el score es bajo. | `claude-haiku-4.5` (temperatura 0) |

### Las 9 categorías de intent

| Intent | Descripción | ¿Handoff? |
|---|---|---|
| `interested` | Interés general, quiere saber más | No — el agente responde |
| `objection_price` | Objeción de precio o presupuesto | No — el agente negocia |
| `objection_authority` | No tiene poder de decisión | No — el agente educa |
| `objection_timing` | No es el momento adecuado | No — el agente trabaja el timing |
| `meeting_intent` | Quiere agendar una llamada o demo | No — el agente confirma |
| `complaint` | Queja o experiencia negativa | **Sí** → humano |
| `complex_technical` | Pregunta técnica profunda fuera del alcance | **Sí** → humano |
| `out_of_scope` | No relacionado con el producto | **Sí** → humano |
| `opt_out` | Quiere que no le escriban más | **Sí** → humano |

### El pipeline de dos puertas

Cada respuesta del prospecto pasa por dos puertas antes de que el agente responda:

```
Respuesta del prospecto
        │
        ▼
  ┌─────────────────┐
  │  PUERTA 1       │  IntentClassifier
  │  Intent Check   │  ¿puede el agente manejar esto?
  └─────────────────┘
        │
        ├── should_handoff=True ──────────────────→ HANDOFF
        │                                           (acción: "handoff")
        │
        └── should_handoff=False
                │
                ▼
         Conversationalist
         (short-term: últimos 15 msgs)
         (long-term: pgvector similarity search)
                │
                ▼ borrador generado
        ┌─────────────────┐
        │  PUERTA 2       │  EvaluatorAgent
        │  Quality Gate   │  score = (naturalidad + relevancia + (1−riesgo)) / 3
        └─────────────────┘
                │
                ├── score ≥ 0.70 ──→ SEND      (mensaje persistido + enviado)
                └── score < 0.70 ──→ ESCALATE  (borrador guardado para revisión)
```

### La memoria dual

El Conversationalist tiene dos capas de memoria:

- **Short-term (textual):** los últimos 15 mensajes del hilo actual. Se pasan directamente al prompt como contexto de conversación. Costo: cero (ya están en DB).
- **Long-term (semántica):** búsqueda vectorial en pgvector. Al generar la respuesta, se embeddea el mensaje del prospecto y se buscan:
  - **`lead_embeddings`** — perfil semántico del lead generado por el Researcher.
  - **`conversation_summaries_embeddings`** — resúmenes de conversaciones anteriores con este u otros leads del tenant.
  
  Esto permite que el agente "recuerde" contexto de interacciones previas aunque no estén en el hilo actual.

### Observabilidad: la tabla `agent_runs`

Cada vez que un agente corre, registra una fila en `agent_runs` con:
- `agent_name` — qué agente fue
- `tokens_in / tokens_out` — consumo exacto de tokens
- `cost_usd` — costo calculado por el provider
- `latency_ms` — tiempo de respuesta del LLM
- `input_payload / output_payload` — qué recibió y qué devolvió
- `llm_provider / llm_model` — qué modelo se usó en esta llamada

Esto permite auditar el costo por conversación, detectar agentes lentos, y comparar modelos.

---

## Guía de la demo

### Preparación (hacer antes de grabar)

```bash
# Terminal 1 — la API debe estar corriendo
PYTHONPATH=src .venv/bin/uvicorn zolvo.api.main:app --reload

# Verificar que responde
curl http://localhost:8000/health
# → {"status":"ok","env":"dev"}

# Verificar Swagger UI
# Abrir http://localhost:8000/docs en el navegador
```

### Paso 1 — Correr el happy path

```bash
# Terminal 2
PYTHONPATH=src .venv/bin/python demo/run_happy_path.py
```

El script ejecuta este escenario automáticamente:

| Paso | Qué pasa | Qué se ve en consola |
|---|---|---|
| Ingest | Lead Diego Ramírez (CTO @ CredIMex) es creado, enriquecido por el Researcher, y el Copywriter genera el primer mensaje outbound | Subject + body del mensaje inicial |
| Turn 1 | Prospecto responde con interés y pide una llamada | Intent: `meeting_intent` → Action: `✓ SEND` + borrador de respuesta |
| Turn 2 | Prospecto objeta el precio ("somos una startup de 30 personas") | Intent: `objection_price` → Action: `✓ SEND` + respuesta que maneja la objeción |
| Turn 3 | Prospecto confirma meeting ("¿pueden el jueves o viernes?") | Intent: `meeting_intent` → Action: `✓ SEND` + respuesta que confirma |
| Summary | Resumen del pipeline | Intent path, action path, confidence scores |

### Paso 2 — Mostrar métricas en Supabase

Después de correr el demo, abrir el **SQL Editor** en supabase.com y pegar el contenido de `demo/metrics.sql`. Ejecutar cada query por separado para mostrar:

**Query 1 — Costo por agente:**
```sql
-- muestra: researcher, copywriter, conversationalist, evaluator, intent_classifier
-- columnas: runs, tokens_in, tokens_out, total_cost_usd, avg_latency_ms
```

**Query 2 — Confidence scores del Evaluator:**
```sql
-- muestra: score numérico + should_send por cada evaluación
-- permite ver que todos los drafts pasaron el gate (score > 0.70)
```

**Query 3 — Distribución de intents:**
```sql
-- muestra: meeting_intent x2, objection_price x1
-- evidencia que el clasificador funcionó correctamente
```

**Query 4 — Totales del pipeline:**
```sql
-- muestra: 1 lead, 1 conversación, 3 mensajes inbound, 3 outbound, costo total USD
```

### Paso 3 — Mostrar la API en Swagger (opcional)

Abrir `http://localhost:8000/docs` y ejecutar manualmente un `POST /agents/ingest` con un lead diferente para mostrar el sistema en tiempo real.

Payload de ejemplo para Swagger:
```json
{
  "tenant_id": "00000000-0000-0000-0000-000000000001",
  "full_name": "Ana Torres",
  "email": "ana.torres@fintechpyme.mx",
  "company": "FintechPyme",
  "role": "CEO",
  "source": "linkedin",
  "channel": "linkedin"
}
```

### Qué mostrar en los logs (Terminal 1)

Mientras corre el demo, la API imprime logs estructurados en tiempo real. Los más relevantes para la demo:

```
researcher.completed    lead_id=... icp_fit=alto embedding_saved=True cost_usd=0.000312
copywriter.completed    lead_id=... channel=email subject="..." cost_usd=0.000089
intent_classifier.classified  intent=meeting_intent should_handoff=False confidence=0.95
conversationalist.completed   conversation_id=... cost_usd=0.000421 latency_ms=3241
evaluator.completed     score=0.9 should_send=True latency_ms=1823
orchestrator.evaluated  score=0.9 should_send=True
```

Estos logs evidencian que cada componente del pipeline corre de forma independiente, con su propio modelo y su propio registro de costos.

---

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
