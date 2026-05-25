# n8n — Visible Orchestration Layer

## Why n8n workflows have only 3 nodes each

This architecture uses the **hybrid pattern** (ADR-01 in `docs/arquitectura-zolvo.md`): n8n is the channel integration and workflow visibility layer for the sales team; the Python services hold the agent logic, evaluation, and memory.

**n8n handles:**
- Receiving webhooks from external channels (LinkedIn, email, forms)
- Triggering the Zolvo API with the right data
- Routing based on the API response (Slack if `handoff`, Calendar if `meeting_intent`)
- Operational visibility for the sales rep via its native UI
- Scheduled triggers (re-engagement of `dormant` leads)

**Python handles:**
- Multi-agent logic (Researcher, Copywriter, Conversationalist, Evaluator)
- LLM Gateway with cost-based routing
- Intent Classifier + Confidence Gate
- Dual memory with pgvector
- Traceability and cost records in `agent_runs`

The alternative — putting all logic in n8n nodes — was not maintainable: logic in JSON, no unit tests, no real versioning, no Strategy pattern.

---

## Current workflows

### 1 · Zolvo — New Lead Ingestion (`5VEfQA0VC44iM6Zs`)

```
[Webhook — New Lead]  →  [POST /agents/ingest]  →  [Respond to Webhook]
POST /webhook/zolvo-new-lead                           returns JSON with
                                                       lead_id, subject, body
```

**What it does:** receives new lead data (from a form, LinkedIn scraper, Airtable, Google Sheets) and triggers the full pipeline: Researcher → enrichment → Copywriter → outbound message.

**Webhook URL:** `https://n8n.stivenyepes.com/webhook/zolvo-new-lead`

---

### 2 · Zolvo — Reply Received (`LDjEhcuc7DMNRywX`)

```
[Webhook — Reply]  →  [POST /events/reply]  →  [Respond to Webhook]
POST /webhook/zolvo-reply                          returns JSON with
                                                   action, intent, draft, score
```

**What it does:** receives a prospect's reply (from a LinkedIn webhook, Gmail inbox, or CRM). Passes the message through the two-gate pipeline: Gate 1 (Intent Classifier) + Gate 2 (Confidence Gate) and returns the routing decision.

**Webhook URL:** `https://n8n.stivenyepes.com/webhook/zolvo-reply`

---

## Simulating a real Mexico B2B flow

### Background

Zolvo's ICP in Mexico is B2B fintechs: digital lending companies, payment processors, payroll platforms, insurtech. These are the real prospects the system is designed to convert.

### Prerequisite

```bash
# Terminal 1 — API running on 0.0.0.0 (required for Docker to reach it)
PYTHONPATH=src .venv/bin/uvicorn zolvo.api.main:app --host 0.0.0.0 --reload
```

> **Network note (WSL2 + Docker):** n8n runs in Docker (`172.18.0.2`). In WSL2 the Docker bridge
> does not always expose the `172.18.0.1` interface to the host. If the webhook returns a 37ms error,
> the n8n container cannot reach the API. Use the Python script for the pipeline and n8n to display
> the visual workflow diagram.

### Example lead: Fernanda Garza — VP of Product @ Konfío

Konfío is a Mexican SME credit platform handling thousands of monthly requests — a real use case for automated scoring.

```bash
# Step 1 — Ingest the lead via n8n
curl -s -X POST https://n8n.stivenyepes.com/webhook/zolvo-new-lead \
  -H "Content-Type: application/json" \
  -d '{
    "body": {
      "tenant_id": "00000000-0000-0000-0000-000000000001",
      "full_name": "Fernanda Garza",
      "email": "fernanda.garza@konfio.mx",
      "linkedin_url": "https://linkedin.com/in/fernanda-garza-konfio",
      "company": "Konfío",
      "role": "VP de Producto",
      "source": "linkedin",
      "channel": "linkedin"
    }
  }' | python3 -m json.tool
```

Save the IDs from the response:

```bash
RESPONSE=$(curl -s -X POST https://n8n.stivenyepes.com/webhook/zolvo-new-lead \
  -H "Content-Type: application/json" \
  -d '{"body": {"tenant_id": "00000000-0000-0000-0000-000000000001", "full_name": "Fernanda Garza", "email": "fernanda.garza@konfio.mx", "company": "Konfío", "role": "VP de Producto", "source": "linkedin", "channel": "linkedin"}}')

CONV_ID=$(echo $RESPONSE | python3 -c "import sys,json; print(json.load(sys.stdin)['conversation_id'])")
echo "conversation_id: $CONV_ID"
```

```bash
# Step 2 — Fernanda replies with interest (meeting_intent)
curl -s -X POST https://n8n.stivenyepes.com/webhook/zolvo-reply \
  -H "Content-Type: application/json" \
  -d "{
    \"body\": {
      \"conversation_id\": \"$CONV_ID\",
      \"tenant_id\": \"00000000-0000-0000-0000-000000000001\",
      \"message\": \"Hola, me llegó tu mensaje. En Konfío manejamos miles de solicitudes de crédito PyME al mes y estamos evaluando cómo mejorar la calificación inicial. ¿Cuándo podemos hablar?\"
    }
  }" | python3 -m json.tool
# Expected: intent=meeting_intent, action=send
```

```bash
# Step 3 — Technical objection (common in MX fintech: in-house legacy stack)
curl -s -X POST https://n8n.stivenyepes.com/webhook/zolvo-reply \
  -H "Content-Type: application/json" \
  -d "{
    \"body\": {
      \"conversation_id\": \"$CONV_ID\",
      \"tenant_id\": \"00000000-0000-0000-0000-000000000001\",
      \"message\": \"El concepto suena bien, pero ya tenemos un modelo de scoring propio con 3 años de datos históricos. ¿Cómo se integraría sin reemplazar lo que ya funciona?\"
    }
  }" | python3 -m json.tool
# Expected: intent=complex_technical or objection_timing, action=send or handoff
```

```bash
# Step 4 — Confirms meeting in CDMX
curl -s -X POST https://n8n.stivenyepes.com/webhook/zolvo-reply \
  -H "Content-Type: application/json" \
  -d "{
    \"body\": {
      \"conversation_id\": \"$CONV_ID\",
      \"tenant_id\": \"00000000-0000-0000-0000-000000000001\",
      \"message\": \"Me convence el enfoque. ¿Pueden venir a nuestras oficinas en Reforma el martes o miércoles? Quiero que lo vea también nuestra CTO.\"
    }
  }" | python3 -m json.tool
# Expected: intent=meeting_intent, action=send or escalate (Gate 2 decides)
```

### Other Mexican leads to vary the demo

```bash
# Lead 2 — Kueski (consumer lending)
"full_name": "Rodrigo Méndez", "company": "Kueski", "role": "Director de Operaciones"

# Lead 3 — Clip (SME payment processor)
"full_name": "Ana Martínez", "company": "Clip", "role": "Head of Growth"

# Lead 4 — Clara (corporate expense management)
"full_name": "Miguel Ángel Torres", "company": "Clara", "role": "CTO"

# Lead 5 — Conekta (payment gateway)
"full_name": "Sofía Herrera", "company": "Conekta", "role": "VP de Ventas B2B"
```

---

## What n8n would add in production

The current workflows are the skeleton of the hybrid pattern. In production each workflow would grow with additional nodes:

### Ingestion workflow (production)

```
[LinkedIn Webhook]
        ↓
[Enrich — LinkedIn API]
        ↓
[POST /agents/ingest]       ← same as now
        ↓
[IF action = send]
   ↓ Yes                         ↓ No
[LinkedIn — Send Message]   [Slack — Notify SDR]
        ↓
[Wait 2-3 days]
        ↓
[Supabase — Mark Sent]
```

### Reply workflow (production)

```
[Gmail / LinkedIn Webhook]
        ↓
[POST /events/reply]        ← same as now
        ↓
[Switch by action]
   ↓ send          ↓ handoff              ↓ escalate
[Send Message]  [Slack Alert]          [Slack Alert]
                [Assign to SDR]        [Draft ready for review]
        ↓
[IF intent = meeting_intent]
        ↓
[Google Calendar — Create event]
[Send invitation]
```

### Why these integrations are not in the prototype

The brief asks to demonstrate the **architecture**, not to wire up LinkedIn OAuth. Real channel integrations require:
- An approved LinkedIn app (weeks-long review process)
- Gmail OAuth with Google Workspace
- Google Calendar credentials

The prototype demonstrates the agent architecture. The n8n workflows are the blueprint for how channels would plug in for production.

---

## Viewing executions in n8n

Go to `https://n8n.stivenyepes.com` → **Executions** section to see all runs with the received input, each node's output, timing, and errors. This is what the sales team would use to audit which messages the system processed.
