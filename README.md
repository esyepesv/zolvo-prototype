# Zolvo AI Sales & Growth Engine — Prototipo

> Propuesta técnica · Coding Fellowship · Makers Admission 2026-2

Pipeline de ventas outbound multi-agente: enrichment de leads, generación de mensajes personalizados, clasificación de intent, memoria dual (textual + vectorial), gate de confianza antes de enviar cada respuesta, y dashboard del operador con métricas en tiempo real.

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
# → 52 passed (unit); integration tests require live Supabase

# 6. Levantar la API
PYTHONPATH=src .venv/bin/uvicorn zolvo.api.main:app --host 0.0.0.0 --reload
# → http://localhost:8000/health  {"status":"ok"}
# → http://localhost:8000/docs    Swagger UI
```

## Demo end-to-end

Con la API corriendo en otra terminal:

```bash
PYTHONPATH=src .venv/bin/python demo/run_happy_path.py
```

Flujo completo en ~60s con output visual usando `rich`:

```
╭─────────────────────────────────────────────────────────╮
│    ZOLVO AI SALES ENGINE                                │
│    Demo End-to-End · Happy Path · Fintech B2B México    │
╰─────────────────────────────────────────────────────────╯
  Terminal 1 shows live API logs: researcher, intent, evaluator,
  channel.linkedin.send, slack alerts

──────────────────── STEP 1 — Ingest Lead ────────────────────

  Lead : Diego Ramírez — CTO @ CredIMex  (diego.ramirez@credimex.com.mx)
  ✓ lead_id          0f694bfc-...
  ✓ conversation_id  e6a562bb-...
  ✓ elapsed          12.2s

╭──────────────── Outbound Message ─────────────────────╮
│ Subject: Diego, ¿cómo escalas tu outreach...          │
│                                                       │
│ Hola Diego, vi que eres CTO en CredIMex...            │
╰───────────────────────────────────────────────────────╯

──────────── STEP 2 — Turn 1 — Interés inicial ─────────────

╭─── PROSPECT ────────────────────────────────────────────╮
│  Hola, me llegó tu mensaje. Estamos evaluando...        │
╰─────────────────────────────────────────────────────────╯
  Intent  meeting_intent
  Action  ✓ SEND   score 0.867   [9.9s]

╭─── Agent Reply — enviado vía LinkedIn ──────────────────╮
│  Perfecto, me da gusto que te interese...               │
╰─────────────────────────────────────────────────────────╯

──────────── STEP 3 — Turn 2 — Objeción de precio ──────────

  Intent  objection_price
  Action  ✓ SEND   score 0.750   [9.8s]

──────────── STEP 4 — Turn 3 — Intent de meeting ───────────

  Intent  meeting_intent
  Action  ✓ SEND   score 0.867   [11.1s]

────────────── PIPELINE SUMMARY ────────────────────────────

╭──────┬──────────────────────┬──────────┬───────┬────────┬────────╮
│ Turn │ Intent               │  Action  │ Score │ Gate 1 │ Gate 2 │
├──────┼──────────────────────┼──────────┼───────┼────────┼────────┤
│  1   │ meeting_intent       │ ✓ SEND   │ 0.867 │  PASS  │  PASS  │
│  2   │ objection_price      │ ✓ SEND   │ 0.750 │  PASS  │  PASS  │
│  3   │ meeting_intent       │ ✓ SEND   │ 0.867 │  PASS  │  PASS  │
╰──────┴──────────────────────┴──────────┴───────┴────────┴────────╯

  Intent path       meeting_intent → objection_price → meeting_intent
  Avg conf score    0.828
  Sends / Escalations / Handoffs   3 / 0 / 0

──────── VISTA DEL PROSPECTO — LinkedIn Inbox ───────────────

  Lo que Diego Ramírez ve en su bandeja de LinkedIn

╭─── Sales Rep @ Zolvo  ← recibido ──────────────────────╮
│  Subject: Diego, ¿cómo escalas tu outreach...          │
╰────────────────────────────────────────────────────────╯
╭─── Diego Ramírez  → enviado ───────────────────────────╮
│  Hola, me llegó tu mensaje...                          │
╰────────────────────────────────────────────────────────╯
╭─── Sales Rep @ Zolvo  ← recibido ──────────────────────╮
│  Perfecto, me da gusto...                              │
╰────────────────────────────────────────────────────────╯
... (todos los turnos del hilo) ...

──────────── DASHBOARD DEL OPERADOR ─────────────────────────

   Leads en pipeline           154
   Conversaciones               91
   Mensajes recibidos           17
   Mensajes enviados            42
   Escalaciones pendientes       1
   Costo total USD         $0.0799

  Costo por agente:
╭───────────────────┬───────────╮
│ Agente            │       USD │
├───────────────────┼───────────┤
│ conversationalist │ $0.027439 │
│ evaluator         │ $0.020127 │
│ copywriter        │ $0.016657 │
│ researcher        │ $0.015700 │
│ intent_classifier │ $0.000000 │
╰───────────────────┴───────────╯

  Distribución de intents:
╭─────────────────┬───────╮
│ Intent          │ Count │
├─────────────────┼───────┤
│ meeting_intent  │     2 │
│ objection_price │     1 │
╰─────────────────┴───────╯

╭────────────────────────────────────────────────────╮
│  ingest → classify → generate → evaluate → route ✓ │
╰────────────────────────────────────────────────────╯
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
| **IntentClassifier** | Clasifica cada respuesta del prospecto en una de 9 categorías. Decide si el agente puede responder o si se necesita un humano. Persiste en `agent_runs`. | `claude-haiku-4.5` (temperatura 0.1) |
| **Conversationalist** | Genera la respuesta multi-turn. Usa memoria dual: los últimos 15 mensajes del hilo + búsqueda semántica en embeddings históricos. Adapta el tono según el intent detectado. | `claude-haiku-4.5` |
| **Evaluator** | Evalúa el borrador antes de enviarlo en 3 ejes: naturalidad (¿suena humano?), relevancia (¿responde al intent?), riesgo (¿podría dañar la relación?). Bloquea el envío si el score es bajo. | `claude-haiku-4.5` (temperatura 0) |

### Los adaptadores de canal

Los canales están implementados como stubs que loguean via structlog — visibles en los logs de la API (Terminal 1 durante la demo):

| Adaptador | Qué hace | Log visible en Terminal 1 |
|---|---|---|
| `LinkedInMockAdapter` | Simula envío de DM en LinkedIn | `channel.linkedin.send` |
| `EmailMockAdapter` | Simula envío de email | `channel.email.send` |
| `SlackStub` | Notifica handoffs y escalaciones al operador | `slack.handoff_alert` / `slack.escalation_alert` |

En producción, cada mock se reemplaza con un adaptador real (API de LinkedIn, SMTP, Slack Webhooks) sin cambiar la lógica de negocio.

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
        │                                           Slack: slack.handoff_alert
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
        │  Quality Gate   │  pre-filter (regex determinístico) → LLM score
        │                 │  score = (naturalidad + relevancia + (1−riesgo)) / 3
        └─────────────────┘
                │
                ├── score ≥ 0.70 ──→ SEND      (LinkedIn mock: channel.linkedin.send)
                └── score < 0.70 ──→ ESCALATE  (Slack: slack.escalation_alert)
```

### La memoria dual

El Conversationalist tiene dos capas de memoria:

- **Short-term (textual):** los últimos 15 mensajes del hilo actual. Se pasan directamente al prompt como contexto de conversación.
- **Long-term (semántica):** búsqueda vectorial en pgvector. Al generar la respuesta, se embeddea el mensaje del prospecto y se buscan:
  - **`lead_embeddings`** — perfil semántico del lead generado por el Researcher.
  - **`conversation_summaries_embeddings`** — resúmenes de conversaciones anteriores.

### Observabilidad: la tabla `agent_runs`

Cada agente registra una fila en `agent_runs` con:
- `agent_name` — qué agente fue (`researcher`, `copywriter`, `conversationalist`, `evaluator`, `intent_classifier`)
- `tokens_in / tokens_out` — consumo exacto de tokens
- `cost_usd` — costo calculado por el provider
- `latency_ms` — tiempo de respuesta del LLM
- `output_payload` — qué devolvió (intent, score, draft, etc.)

### El dashboard del operador

El endpoint `GET /operator/dashboard?tenant_id=...` agrega métricas en tiempo real:

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

El endpoint `GET /operator/conversations?tenant_id=...&status=dormant` lista conversaciones por estado para colas de re-engagement.

---

## Guía de la demo

### Preparación (hacer antes de grabar)

```bash
# Terminal 1 — la API debe estar corriendo
PYTHONPATH=src .venv/bin/uvicorn zolvo.api.main:app --host 0.0.0.0 --reload

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

| Paso | Qué pasa | Qué se ve en Terminal 2 | Qué se ve en Terminal 1 (API logs) |
|---|---|---|---|
| Ingest | Lead Diego Ramírez (CTO @ CredIMex) es creado, enriquecido, y el Copywriter genera el mensaje outbound | Subject + body del mensaje inicial | `researcher.completed`, `copywriter.completed` |
| Turn 1 | Prospecto responde con interés y pide una llamada | Intent: `meeting_intent` → Action: `✓ SEND` + borrador | `intent_classifier.classified`, `channel.linkedin.send` |
| Turn 2 | Prospecto objeta el precio | Intent: `objection_price` → Action: `✓ SEND` + manejo de objeción | `evaluator.completed`, `channel.linkedin.send` |
| Turn 3 | Prospecto confirma meeting con CEO | Intent: `meeting_intent` → `✓ SEND` (o `↑ ESCALATE` si Gate 2 bloquea) | `orchestrator.evaluated`, `channel.linkedin.send` |
| Prospect view | Simulación de inbox LinkedIn mostrando el hilo completo | Panels blancos (agente) + azules (prospecto) | — |
| Dashboard | Métricas del operador en tiempo real | Tabla de costos por agente + distribución de intents | — |
| Summary | Resumen del pipeline | Intent path, action path, confidence scores | — |

> **Nota sobre Gate 2:** En el happy path, los 3 turnos pasan con scores ≥ 0.70.
> Si el evaluador decide `↑ ESCALATE` en algún turno, se verá `slack.escalation_alert`
> en Terminal 1 y el borrador quedará marcado como "pendiente revisión" en la vista del prospecto.

### Paso 2 — Mostrar métricas en Supabase

Después de correr el demo, abrir el **SQL Editor** en supabase.com y pegar el contenido de `demo/metrics.sql`.

### Paso 3 — Mostrar la API en Swagger (opcional)

Abrir `http://localhost:8000/docs` y ejecutar manualmente un `POST /agents/ingest` con un lead diferente.

Payload de ejemplo:
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

```
researcher.completed    lead_id=... icp_fit=alto embedding_saved=True cost_usd=0.000312
copywriter.completed    lead_id=... channel=email subject="..." cost_usd=0.000089
intent_classifier.classified  intent=meeting_intent should_handoff=False
channel.linkedin.send   to=<conv_id> chars=420
evaluator.completed     score=0.867 should_send=True latency_ms=1823
orchestrator.evaluated  score=0.867 should_send=True

# Si action=handoff:
slack.handoff_alert     conversation_id=... intent=opt_out  action_required="Assign to SDR"

# Si action=escalate:
slack.escalation_alert  conversation_id=... confidence_score=0.45  action_required="Review and approve/edit draft"
```

---

## Endpoints de la API

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/health` | Estado de la API |
| `POST` | `/agents/ingest` | Crea lead → Researcher → Copywriter → mensaje outbound |
| `POST` | `/events/reply` | Recibe respuesta del prospecto → pipeline de dos puertas → route |
| `GET` | `/operator/dashboard` | Métricas del pipeline en tiempo real (param: `tenant_id`) |
| `GET` | `/docs` | Swagger UI |

---

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| API | Python 3.11+ · FastAPI · Pydantic v2 |
| Base de datos | Supabase · Postgres + pgvector + RLS multi-tenant |
| Acceso a datos | supabase-py async (REST API via HTTPS) |
| LLM Gateway | Strategy pattern: OpenRouter (default) · Anthropic · OpenAI · Ollama |
| Canales | LinkedInMockAdapter · EmailMockAdapter · SlackStub (logs en Terminal 1) |
| Orquestación | n8n self-hosted |
| Observabilidad | structlog · tabla `agent_runs` (costo, latencia, tokens por agente) |

## Arquitectura del pipeline

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
 IntentClassifier (Gate 1) ──→ persiste en agent_runs
      │
      ├─ should_handoff=True ──→ HANDOFF → SlackStub.notify_handoff()
      │
      └─ should_handoff=False
            │
            ▼
       Conversationalist (memoria dual)
            │  ├─ short-term: últimos 15 msgs
            │  └─ long-term: pgvector similarity search
            ▼
       EvaluatorAgent (Gate 2)
            │  score = (naturalidad + relevancia + (1−riesgo)) / 3
            │
            ├─ score ≥ 0.70 ──→ SEND → LinkedInMockAdapter.send_message()
            └─ score < 0.70 ──→ ESCALATE → SlackStub.notify_escalation()
```

## Estructura del proyecto

```
zolvo-prototype/
├── src/zolvo/
│   ├── api/
│   │   ├── main.py             # FastAPI app + lifespan
│   │   ├── deps.py             # FastAPI dependency injection
│   │   └── routes/
│   │       ├── agents.py       # POST /agents/ingest
│   │       ├── events.py       # POST /events/reply
│   │       └── operator.py     # GET /operator/dashboard
│   ├── agents/                 # Researcher, Copywriter, Conversationalist, Evaluator
│   ├── channels/               # Adaptadores de canal
│   │   ├── base.py             # ChannelAdapter ABC + SendResult
│   │   ├── linkedin_mock.py    # LinkedInMockAdapter (log: channel.linkedin.send)
│   │   ├── email_mock.py       # EmailMockAdapter (log: channel.email.send)
│   │   └── slack_stub.py       # SlackStub (log: slack.handoff_alert / escalation_alert)
│   ├── intent/                 # IntentClassifier — 9 categorías
│   ├── orchestrator/           # Pipeline coordinator (dos puertas)
│   ├── memory/                 # MemoryService — short-term + long-term (pgvector)
│   ├── llm/                    # LLM Gateway + providers + prompts versionados
│   ├── repositories/           # Repository pattern — supabase-py async
│   ├── models/                 # Pydantic domain models
│   ├── schemas.py              # Request/Response schemas FastAPI
│   └── config.py               # Settings via pydantic-settings
├── demo/
│   ├── run_happy_path.py       # Script demo end-to-end (rich terminal UI)
│   └── metrics.sql             # Queries de métricas para Supabase SQL Editor
├── supabase/
│   ├── migrations/             # SQL versionado (3 archivos)
│   └── seed.sql                # Tenant demo
├── n8n/
│   ├── workflows/              # Exports JSON de workflows n8n
│   └── README.md               # Qué hace n8n, curl commands, escenario Konfío
├── tests/
│   ├── unit/                   # 49 tests con FakeLLMProvider (sin red)
│   └── integration/            # 5 tests contra Supabase real
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
| 12 | Polish para el video (channel stubs, operator dashboard, prospect view) | ✅ |

Ver [PROGRESS.md](PROGRESS.md) para el estado detallado y decisiones técnicas.

## Referencias

- [Arquitectura del sistema](docs/arquitectura-zolvo.md) — C4, ADRs, modelo de datos, máquina de estados
- [PROGRESS.md](PROGRESS.md) — estado de desarrollo y decisiones tomadas
- [n8n — workflows y simulación México](n8n/README.md) — qué hace n8n, curl commands, escenario Konfío
- [Supabase setup](supabase/README.md)
