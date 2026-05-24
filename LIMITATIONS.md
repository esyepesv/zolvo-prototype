# LIMITATIONS.md — Brechas entre diseño y prototipo

> Este documento existe porque la honestidad técnica vale más que la apariencia de completitud. El sistema descrito en `docs/arquitectura-zolvo.md` es el diseño objetivo. Este prototipo cubre lo esencial del happy path en 48 horas, con trade-offs deliberados que se enumeran aquí.

**Audiencia:** evaluadores técnicos y futuros mantenedores. Si vas a revisar el código contra el diseño, lee esto primero.

---

## 1. Resumen ejecutivo

| Componente del diseño | Estado en el prototipo | Severidad |
|---|---|---|
| Strategy pattern para LLMs | ✅ Implementado completo (4 providers) | — |
| Multi-tenant con RLS | ✅ Implementado completo | — |
| Intent Classifier (Puerta 1) | ✅ Implementado completo | — |
| Confidence Gate (Puerta 2) | ✅ Implementado completo | — |
| Memoria dual (textual + pgvector) | ✅ Implementado completo | — |
| Observabilidad (`agent_runs`) | ✅ Implementado completo | — |
| Dashboard del operador | ✅ Implementado completo | — |
| Researcher Agent | ⚠️ Implementado sin fuentes externas | Media |
| Conversationalist (multi-turn) | ✅ Implementado completo | — |
| Scheduler Agent | ❌ Absorbido por Conversationalist | **Alta** |
| Debouncing + Advisory Lock (ADR-06) | ✅ Implementado (jitter async + in-memory lock) | — |
| Event Bus async (ADR-03) | ❌ Reemplazado por HTTP síncrono | Media |
| Circuit breaker (ADR-01) | ✅ Implementado (in-memory, per-provider) | — |
| Re-engagement de leads `dormant` | ❌ Estado definido, no automatizado | Baja |
| Objection Handler especializado | ❌ Absorbido por Conversationalist | Baja |
| Canales reales (LinkedIn/Email/Calendar) | ❌ Mocks con logs estructurados | Por diseño |
| Slack real | ❌ Stub con `log.warning` | Por diseño |

---

## 2. Brechas de alta severidad

### 2.1 Debouncing + Advisory Lock (ADR-06) — implementado ✅

**Lo que dice el diseño:** ADR-06 argumenta que el debouncing (30–90s con jitter) y el `pg_advisory_xact_lock(lead_id)` son los mecanismos que convierten la latencia en feature de humanización y eliminan race conditions en mensajes concurrentes del mismo lead.

**Lo que hace el código:**
- `POST /events/reply` persiste el mensaje inbound inmediatamente (antes del lock).
- Adquiere un `asyncio.Lock` por `conversation_id` (módulo-level dict `_conv_locks`).
- Dentro del lock: `asyncio.sleep(random.uniform(debounce_min, debounce_max))` con log estructurado.
- El pipeline completo y el routing de canal corren dentro del lock — imposible procesar la misma conversación en paralelo en un solo proceso.

**Limitación de producción:** `asyncio.Lock` es in-memory y single-process. En un deployment multi-worker (Gunicorn con varios workers), dos workers pueden adquirir locks distintos para el mismo `conversation_id`. Para multi-worker se necesita `pg_advisory_xact_lock` o Redis Distributed Lock (Redlock). En el prototipo single-worker con uvicorn, el lock es suficiente.

---

### 2.2 Scheduler Agent — absorbido por Conversationalist

**Lo que dice el diseño:** el C4 L3 muestra un `Scheduler Agent` como componente independiente con Strategy pattern. El diagrama de secuencia (Fase 4) detalla cómo el Scheduler consulta Calendar, propone slots naturales, espera confirmación, crea evento y notifica.

**Lo que hace el código:** cuando el Intent Classifier detecta `meeting_intent`, el flujo va al `ConversationalistAgent` con una guía de prompt específica en `_INTENT_GUIDANCE["meeting_intent"]` que le pide proponer 2-3 horarios. **No hay creación real de evento en Calendar.** En n8n existe un nodo "Google Calendar — Crear Evento" detrás de un `IF intent == meeting_intent`, pero el endpoint apunta a `googleapis.com/calendar/v3` sin OAuth configurado — el nodo está como blueprint, no ejecuta.

**Por qué se dejó así:**
- Crear un agente Python aparte por una guía de prompt aplicada al mismo LLM no aporta valor real: sería duplicación con otro nombre.
- La integración real con Google Calendar requiere OAuth + credentials de Google Workspace, fuera del alcance de un prototipo de 48h.
- La detección de slots disponibles, parseo de confirmación del prospect y creación de evento son **3 sub-features distintos**, cada uno con su propia complejidad.

**Impacto real:**
- En el demo, el sistema "responde como si fuera a agendar" pero **no agenda nada**. El brief pide "book meetings".
- Es la brecha más visible si el evaluador hace el demo manualmente y verifica calendar.

**Qué requiere para producción:**
1. `SchedulerAgent` como Strategy con dependencias inyectadas: `CalendarAdapter`, `LLMGateway`, `MemoryService`
2. `CalendarAdapter` con implementaciones reales (`GoogleCalendarAdapter`, `OutlookAdapter`) + mock para tests
3. Parser de intent secundario: "user confirmed slot X" vs "user proposed alternative" vs "user backed out"
4. Estado `scheduling` activo en la máquina de estados (ya definido en `docs/arquitectura-zolvo.md` §8)
5. Workflow en n8n con OAuth de Google Calendar y envío de `.ics`

**Estimación:** 8-12h de desarrollo para un Scheduler funcional sin canales reales; +15h para integraciones OAuth en producción.

---

## 3. Brechas de severidad media

### 3.1 Event Bus async (ADR-03) — reemplazado por HTTP síncrono

**Diseño:** Supabase Realtime + outbox pattern. Eventos `lead.created`, `reply.received`, `message.sent` publicados asincrónicamente. Workers suscriptos los consumen sin bloqueo.

**Código:** la API recibe HTTP, ejecuta el pipeline completo en el mismo request, responde con el resultado. La tabla `events_outbox` está en migrations pero **ninguna escritura la usa**.

**Por qué:** un demo síncrono es más fácil de mostrar en video. El `POST /events/reply` retorna `{intent, action, confidence}` en la respuesta, lo cual es ideal para grabar logs en tiempo real. Hacerlo async habría requerido un consumidor de eventos corriendo aparte y un mecanismo de polling/SSE para que el demo viera el resultado.

**Trade-off honesto:**
- ✅ Demo más visible y debuggeable
- ❌ Latencia bloqueante en el request del prospect (en producción real, LinkedIn no espera 8 segundos)
- ❌ Sin backpressure cuando entren picos de mensajes
- ❌ `events_outbox` definido pero inútil

**Qué requiere para producción:**
- Worker async consumiendo de Supabase Realtime (canal por tipo de evento)
- `events_outbox` escrito en la misma transacción que los cambios de estado
- Publisher worker que lee `events_outbox` y emite a Realtime con dedupe por `id`
- Retry policy con DLQ para eventos que fallan 3 veces
- Tests de integración que validen entrega at-least-once

---

### 3.2 Researcher Agent — enrichment sin fuentes externas

**Diseño:** el Researcher enriquece el lead con datos externos antes de generar embedding.

**Código:** el Researcher recibe `{full_name, email, company, role}`, lo pasa a un LLM con un prompt de enrichment, y persiste el resultado como JSON en `leads.enriched_data` + embedding en `lead_embeddings`. **No consulta LinkedIn API, Crunchbase, Apollo, ZoomInfo ni ninguna fuente externa.** El LLM "infiere" un perfil plausible a partir del nombre de la empresa y el rol.

**Por qué:** las APIs reales de enrichment requieren contratos con vendors (Apollo cuesta $99/mes mínimo) o aprobación de LinkedIn (proceso de semanas). En un prototipo, usar un LLM como enrichment sintético demuestra el patrón sin el costo.

**Riesgo en producción:**
- El enrichment alucinado puede contener información incorrecta del prospect
- Los embeddings construidos sobre enrichment ficticio degradan la calidad del RAG
- En un caso real, podrías mandar un mensaje personalizado con datos inventados — peor que un mensaje genérico

**Qué requiere para producción:**
- `EnrichmentProvider` con Strategy pattern: `ApolloProvider`, `ClearbitProvider`, `LinkedInScraperProvider`, `LLMFallbackProvider` (para cuando los anteriores fallan)
- Cache de enrichment en Supabase con TTL (los datos del lead no cambian cada hora)
- Validación cruzada: si dos providers difieren, marcar para revisión

---

### 3.3 Circuit breaker (ADR-01) — implementado ✅

**Diseño:** ADR-01 menciona circuit breaker para protección ante caídas de proveedores LLM.

**Código:** `src/zolvo/llm/circuit_breaker.py` implementa un circuit breaker in-memory por provider con tres estados (closed → open → half-open). `LLMGateway.complete()` lo consulta antes de cada llamada: si el circuito está abierto, intenta automáticamente el siguiente provider disponible. Los fallos sucesivos (`failure_threshold=3`) abren el circuito por `recovery_timeout=60s`, luego pasa a half-open para probar recuperación.

---

## 4. Brechas de severidad baja

### 4.1 Re-engagement automático de leads `dormant`

**Diseño:** la máquina de estados (§8 de arquitectura) define `dormant` con máximo 2 reintentos espaciados.

**Código:** el estado está en `conversations.status` pero **no hay job programado que lo escanee** y dispare re-engagement.

**Qué requiere:** un workflow en n8n con trigger Cron diario que consulte `conversations WHERE status='dormant' AND updated_at < NOW() - INTERVAL '7 days'` y dispare `POST /events/reengage`.

---

### 4.2 Objection Handler especializado

**Diseño:** componente independiente para objeciones complejas (precio, autoridad, timing).

**Código:** absorbido por el `ConversationalistAgent` con `_INTENT_GUIDANCE` específico por tipo de objeción.

**Decisión consciente:** un agente aparte habría sido duplicación. La guía por intent ya genera respuestas diferenciadas. Si en producción se valida que el copy de objeciones se beneficia de prompts más largos o RAG separado de casos exitosos, vale la pena fragmentar. Por ahora es prematuro.

---

### 4.3 Confidence Gate "circular"

**Crítica legítima:** el Evaluator usa un LLM (modelo barato) para evaluar lo que otro LLM (modelo caro) generó. Si ambos comparten sesgos del entrenamiento, el evaluador puede aprobar respuestas que un humano rechazaría.

**Por qué se aceptó:**
- Sigue siendo mejor que NO tener evaluador
- Captura los casos obvios: tono incorrecto, promesas explícitas de ROI, riesgos legales
- El umbral 0.70 permite calibrar conservadoramente

**Mejora para producción:**
- Reglas determinísticas como pre-filtro antes del evaluador LLM (regex para precios prometidos, palabras prohibidas, longitud máxima, ratio mayúsculas/minúsculas)
- Evaluador con modelo de familia diferente al generador (Anthropic genera, OpenAI evalúa) para reducir sesgo compartido
- Sample manual periódico (10% de mensajes aprobados) para auditoría humana → dataset de fine-tuning

---

## 5. Decisiones explícitas de mock vs real (por diseño, no por tiempo)

Estas no son brechas, son trade-offs deliberados:

| Mock | Razón |
|---|---|
| `LinkedInMockAdapter` | App de LinkedIn requiere aprobación (semanas). Diseñar el adapter con interfaz clara es el aporte arquitectónico. |
| `EmailMockAdapter` | OAuth de Google Workspace fuera de alcance de 48h. |
| `SlackStub` | Sin webhook real configurado. El log estructurado cumple la función demostrativa. |
| Calendar real | Mismo motivo que LinkedIn. |
| n8n con OAuth completo | Mismo motivo. Workflows quedan como blueprint estructural. |

En todos los casos, **la abstracción (ABC + Strategy) está implementada**. Cambiar el mock por la implementación real es localizable a un solo archivo, sin tocar agentes, orchestrator ni intent classifier.

---

## 6. Crítica honesta al rol de n8n en el prototipo

Esta es la observación más probable de un evaluador técnico, así que la abordo directo:

**Realidad del demo:** los dos workflows de n8n (`zolvo-new-lead-ingestion` y `zolvo-reply-received`) actúan principalmente como **proxies HTTP**: reciben un webhook, hacen un POST a la API FastAPI, devuelven la respuesta. n8n no está orquestando lógica compleja en este demo.

**Por qué se hizo así:**
- El brief pide "pipeline con n8n + Supabase + LLMs". Tener n8n disparando workflows visibles cumple ese pedido literalmente.
- La lógica compleja (multi-agente, Strategy pattern, evaluación) vive en Python por las razones del ADR-01 (testeabilidad, mantenibilidad, versionado). Llevarla a nodos de n8n habría sacrificado eso.
- En producción n8n crece con: nodos de LinkedIn API, Gmail, Google Calendar, schedulers Cron, alertas Slack/Discord, branches por canal/segmento. El `n8n/README.md` describe ese estado objetivo.

**Lo que un evaluador exigente podría argumentar:** "el demo no demuestra el valor real de n8n, solo lo usa como proxy". Es una crítica válida y reconocida.

**Defensa:** el demo prioriza demostrar la arquitectura de agentes y el pipeline de dos puertas, donde está el aporte técnico genuino. n8n es la fachada operacional para el sales rep, no el núcleo computacional. Mover el núcleo a n8n habría sido cumplimiento literal sacrificando atributos de calidad.

---

## 7. Qué NO se debe interpretar como brecha

Algunas críticas posibles que **no son fallas sino decisiones explícitas**:

- **"El prototipo solo usa un tenant"** — el diseño multi-tenant está completo en migrations + RLS + filtrado por `tenant_id`. La demo usa un tenant porque mostrar dos no agrega información, solo ruido.
- **"Los tests usan FakeLLMProvider"** — esto es **correcto por diseño**, no atajo. Tests determinísticos sin red ni costo. Los tests de integración contra Supabase real existen aparte.
- **"No hay dashboard web"** — el dashboard es endpoint JSON (`GET /operator/dashboard`) que se renderiza con `rich` en el demo. Un frontend separado habría sido scope creep.
- **"El demo usa solo 1 lead"** — el script `demo/run_happy_path.py` es secuencial por claridad. El sistema procesa N leads paralelos sin cambios; el demo está optimizado para video.

---

## 8. Roadmap de cierre de brechas, priorizado

Si tuviera 1 semana más de desarrollo, este es el orden de implementación:

| Día | Brecha | Razón de prioridad |
|---|---|---|
| ✅ | Debouncing con jitter | Implementado — falta advisory lock para race conditions reales |
| ✅ | Circuit breaker in-memory | Implementado — falta estado distribuido (Redis) para multi-worker |
| 1 | Advisory lock (`pg_advisory_xact_lock`) | Cierra la parte faltante del ADR-06 |
| 1-2 | Scheduler Agent + Google Calendar real | El brief pide book meetings — sin esto, el sistema queda incompleto |
| 2-3 | Event Bus async + outbox pattern | Habilita escalabilidad real y elimina latencia bloqueante |
| 3-4 | Researcher con Apollo/Clearbit | Sin enrichment real, el copy puede tener datos inventados |
| 4-5 | Re-engagement de `dormant` + objection handler | Refinamientos del funnel |
| 5-6 | Tests de carga, auditoría manual de mensajes, hardening | Pre-producción |

---

## 9. Lo que el prototipo SÍ demuestra (para balance)

Para no terminar este documento solo en lo que falta:

- **Diseño con criterio de ingeniería:** atributos de calidad priorizados explícitamente, ADRs con trade-offs honestos, C4 a 3 niveles, máquina de estados modelada.
- **Strategy pattern real:** 4 proveedores de LLM intercambiables con routing por costo. Cambiar de OpenRouter a Anthropic toma 1 línea en `.env`.
- **Observabilidad como first-class citizen:** cada decisión de cada agente queda en `agent_runs` con costo, latencia, tokens, payloads. El ROI es computable, no estimado.
- **Multi-tenant desde día 1:** RLS implementado en todas las tablas. Filtrado por `tenant_id` defendido a nivel de base de datos.
- **Pipeline de dos puertas funcional:** Intent Classifier filtra qué intentar, Confidence Gate valida lo intentado. Documentado en ADR-04 e implementado.
- **Memoria dual real:** short-term textual (últimos 15 msgs) + long-term vectorial (pgvector con `match_lead_embeddings` y `match_conversation_summaries`). Las dos consultadas en cada turno.
- **Demo end-to-end ejecutable:** un script reproduce el happy path en ~60 segundos con UI visual. Los datos quedan persistidos en Supabase real.
- **Tests con FakeLLMProvider:** 54 tests pasando sin costo de API ni dependencia de red.

---

## 10. Cómo defender este documento ante un evaluador

Si un evaluador pregunta "¿por qué X no está implementado?", la respuesta está aquí. Si pregunta algo no listado aquí, eso es genuinamente un gap que no anticipé y vale la pena anotar para el siguiente ciclo.

**El principio detrás de este archivo:** prefiero que un evaluador me lea decir "esto no lo hice y aquí está por qué" antes que descubrirlo él mismo y concluir que no me di cuenta. La diferencia entre un junior y un senior frecuentemente es saber qué dejaste fuera y poder justificarlo.

---

**Autor:** Stiven Yepes Vanegas
**Fecha:** 24 de mayo de 2026
**Última actualización:** corte de prototipo para entrega del reto Coding Fellowship · Makers Admission 2026-2
