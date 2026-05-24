# n8n — Capa de orquestación visible

## Por qué n8n tiene solo 3 nodos por workflow

Esta arquitectura adopta el **patrón híbrido** (ADR-01 en `docs/arquitectura-zolvo.md`): n8n es la capa de integración de canales y workflows visibles para el equipo de ventas; los servicios Python son donde reside la lógica de agentes, evaluación y memoria.

**n8n hace:**
- Recibir webhooks de canales externos (LinkedIn, email, formularios)
- Disparar la API de Zolvo con los datos correctos
- Enrutar según la respuesta (Slack si `handoff`, Calendar si `meeting_intent`)
- Dar visibilidad operativa al sales rep via su UI nativa
- Triggers programados (re-engagement de leads `dormant`)

**Python hace:**
- Lógica multi-agente (Researcher, Copywriter, Conversationalist, Evaluator)
- LLM Gateway con routing por costo
- Intent Classifier + Confidence Gate
- Memoria dual con pgvector
- Registros de trazabilidad y costo en `agent_runs`

La alternativa (poner toda la lógica en nodos n8n) era inmantenible: lógica en JSON, sin tests unitarios, sin Strategy pattern, sin versionado real.

---

## Workflows actuales

### 1 · Zolvo — New Lead Ingestion (`5VEfQA0VC44iM6Zs`)

```
[Webhook — New Lead]  →  [POST /agents/ingest]  →  [Respond to Webhook]
POST /webhook/zolvo-new-lead                           devuelve JSON con
                                                       lead_id, subject, body
```

**Qué hace:** recibe los datos de un lead nuevo (puede venir de un formulario, LinkedIn scraper, Airtable, Google Sheets) y dispara el pipeline completo: Researcher → enriquecimiento → Copywriter → mensaje outbound.

**Webhook URL:** `https://n8n.stivenyepes.com/webhook/zolvo-new-lead`

---

### 2 · Zolvo — Reply Received (`LDjEhcuc7DMNRywX`)

```
[Webhook — Reply]  →  [POST /events/reply]  →  [Respond to Webhook]
POST /webhook/zolvo-reply                          devuelve JSON con
                                                   action, intent, draft, score
```

**Qué hace:** recibe la respuesta de un prospecto (puede venir de un webhook de LinkedIn, de la bandeja de Gmail, de un CRM). Pasa el mensaje por el pipeline de dos puertas: Gate 1 (Intent Classifier) + Gate 2 (Confidence Gate) y devuelve la decisión de routing.

**Webhook URL:** `https://n8n.stivenyepes.com/webhook/zolvo-reply`

---

## Simulación de un flujo real en México

### El contexto del reto

El ICP de Zolvo en México son fintechs B2B: empresas de crédito digital, procesadores de pagos, plataformas de nómina, insurtech. Estos son los prospectos reales que el sistema debe poder convertir.

### Prerequisito

```bash
# Terminal 1 — API corriendo en 0.0.0.0 (necesario para que Docker pueda alcanzarla)
PYTHONPATH=src .venv/bin/uvicorn zolvo.api.main:app --host 0.0.0.0 --reload
```

> **Nota de red (WSL2 + Docker):** n8n corre en Docker (`172.18.0.2`). En WSL2 el bridge Docker no
> siempre expone la interfaz `172.18.0.1` al host. Si el webhook retorna error 37ms, el n8n container
> no alcanza la API. En ese caso usa el Python script para el pipeline y n8n para mostrar el diagrama visual.

### Lead ejemplo: Fernanda Garza — VP de Producto @ Konfío

Konfío es una plataforma mexicana de crédito para PyMEs con miles de solicitudes mensuales — caso de uso real para scoring automatizado.

```bash
# Paso 1 — Ingresar el lead vía n8n
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

Guarda los IDs de la respuesta:

```bash
# Extraer IDs (requiere jq)
RESPONSE=$(curl -s -X POST https://n8n.stivenyepes.com/webhook/zolvo-new-lead \
  -H "Content-Type: application/json" \
  -d '{"body": {"tenant_id": "00000000-0000-0000-0000-000000000001", "full_name": "Fernanda Garza", "email": "fernanda.garza@konfio.mx", "company": "Konfío", "role": "VP de Producto", "source": "linkedin", "channel": "linkedin"}}')

CONV_ID=$(echo $RESPONSE | python3 -c "import sys,json; print(json.load(sys.stdin)['conversation_id'])")
echo "conversation_id: $CONV_ID"
```

```bash
# Paso 2 — Fernanda responde con interés (meeting_intent)
curl -s -X POST https://n8n.stivenyepes.com/webhook/zolvo-reply \
  -H "Content-Type: application/json" \
  -d "{
    \"body\": {
      \"conversation_id\": \"$CONV_ID\",
      \"tenant_id\": \"00000000-0000-0000-0000-000000000001\",
      \"message\": \"Hola, me llegó tu mensaje. En Konfío manejamos miles de solicitudes de crédito PyME al mes y estamos evaluando cómo mejorar la calificación inicial. ¿Cuándo podemos hablar?\"
    }
  }" | python3 -m json.tool
# Esperado: intent=meeting_intent, action=send
```

```bash
# Paso 3 — Objeción técnica (frecuente en fintech MX: stack legacy propio)
curl -s -X POST https://n8n.stivenyepes.com/webhook/zolvo-reply \
  -H "Content-Type: application/json" \
  -d "{
    \"body\": {
      \"conversation_id\": \"$CONV_ID\",
      \"tenant_id\": \"00000000-0000-0000-0000-000000000001\",
      \"message\": \"El concepto suena bien, pero ya tenemos un modelo de scoring propio con 3 años de datos históricos. ¿Cómo se integraría sin reemplazar lo que ya funciona?\"
    }
  }" | python3 -m json.tool
# Esperado: intent=complex_technical o objection_timing, action=send o handoff
```

```bash
# Paso 4 — Confirma reunión en CDMX
curl -s -X POST https://n8n.stivenyepes.com/webhook/zolvo-reply \
  -H "Content-Type: application/json" \
  -d "{
    \"body\": {
      \"conversation_id\": \"$CONV_ID\",
      \"tenant_id\": \"00000000-0000-0000-0000-000000000001\",
      \"message\": \"Me convence el enfoque. ¿Pueden venir a nuestras oficinas en Reforma el martes o miércoles? Quiero que lo vea también nuestra CTO.\"
    }
  }" | python3 -m json.tool
# Esperado: intent=meeting_intent, action=send o escalate (Gate 2 decide)
```

### Otros leads mexicanos para variar el demo

```bash
# Lead 2 — Kueski (crédito al consumo)
"full_name": "Rodrigo Méndez", "company": "Kueski", "role": "Director de Operaciones"

# Lead 3 — Clip (procesador de pagos PyME)
"full_name": "Ana Martínez", "company": "Clip", "role": "Head of Growth"

# Lead 4 — Clara (gestión de gastos corporativos)
"full_name": "Miguel Ángel Torres", "company": "Clara", "role": "CTO"

# Lead 5 — Conekta (pasarela de pagos)
"full_name": "Sofía Herrera", "company": "Conekta", "role": "VP de Ventas B2B"
```

---

## Qué añadiría n8n en producción

Los workflows actuales son el esqueleto del patrón híbrido. En producción, cada workflow crecería con nodos adicionales:

### Workflow de ingesta (producción)

```
[LinkedIn Webhook]
        ↓
[Enrich — LinkedIn API]
        ↓
[POST /agents/ingest]       ← igual que ahora
        ↓
[IF action = send]
   ↓ Sí                          ↓ No
[LinkedIn — Send Message]   [Slack — Notificar SDR]
        ↓
[Wait 2-3 días]
        ↓
[Supabase — Mark Sent]
```

### Workflow de reply (producción)

```
[Gmail / LinkedIn Webhook]
        ↓
[POST /events/reply]        ← igual que ahora
        ↓
[Switch por action]
   ↓ send          ↓ handoff              ↓ escalate
[Send Message]  [Slack Alert]          [Slack Alert]
                [Asignar a SDR]        [Draft listo para revisar]
        ↓
[IF intent = meeting_intent]
        ↓
[Google Calendar — Crear evento]
[Enviar invitación]
```

### Por qué estas integraciones no están en el prototipo

El brief pide demostrar la **arquitectura**, no conectar OAuth de LinkedIn. Integrar canales reales requiere:
- App de LinkedIn aprobada (proceso de semanas)
- OAuth de Gmail con Google Workspace
- Credenciales de Google Calendar

El prototipo demuestra la arquitectura de agentes. Los workflows de n8n son el blueprint de cómo encajarían los canales en producción.

---

## Ver ejecuciones en n8n

En `https://n8n.stivenyepes.com` → sección **Executions** se ven todas las ejecuciones con input recibido, output de cada nodo, tiempo y errores. Esto es lo que mostraría el equipo de ventas para auditar qué mensajes procesó el sistema.
