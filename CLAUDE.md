# CLAUDE.md — Guía operativa para Claude Code

> Este archivo es la especificación operativa del proyecto. Léelo completo antes de cualquier acción. Es la fuente de verdad sobre objetivos, restricciones, alcance y convenciones.

---

## 1. Contexto del proyecto

Este repositorio implementa el **prototipo del AI Sales & Growth Engine de Zolvo**, propuesta técnica para el reto de Coding Fellowship de Makers Admission 2026-2.

**Eres el desarrollador principal.** Vas a planear y construir el código bajo supervisión del autor (Stiven). El objetivo final del proyecto es demostrar — en un video de 5 minutos — una arquitectura de calidad de ingeniería con un prototipo funcional que cubra el happy path.

**Lectura obligatoria antes de codear:**
- `docs/arquitectura-zolvo.md` — diseño completo del sistema (C4, ADRs, modelo de datos, máquina de estados). Toda decisión de implementación se justifica contra este documento.

Si encuentras contradicción entre este `CLAUDE.md` y el documento de arquitectura, **detente y pregunta**. No asumas.

---

## 2. Objetivos del prototipo

**Objetivo del demo (5 min de video):** mostrar el happy path end-to-end con datos reales, demostrando:

1. Ingesta de un lead con enrichment automático
2. Generación de mensaje inicial outbound
3. Recepción de respuesta del prospect (simulada o real)
4. Pipeline de dos puertas: Intent Classifier + Confidence Gate
5. Respuesta multi-turn con memoria dual
6. Detección de intent de meeting y agendamiento

**Lo que NO es el objetivo:** un producto desplegado en producción. Esto es un prototipo demostrativo con énfasis en calidad de diseño, no en cobertura de features.

---

## 3. Restricciones reales

| Restricción | Valor |
|---|---|
| Deadline absoluto | 48h desde 23 may 2026, 17:58 (hora Colombia) |
| Tiempo de desarrollo efectivo | ~30h (resto para guion, grabación, edición, buffer) |
| Mercado del demo | México (ICP: fintech B2B) |
| Idioma de prompts/UX | Español |
| Costo de APIs | Mínimo necesario. Preferir modelos baratos donde se pueda. |

**Si el tiempo se acaba, el prototipo NO debe estar incompleto en lo crítico.** Mejor entregar menos features bien hechas que muchas a medias.

---

## 4. Stack tecnológico

### Backend (Agent Services API)
- **Python 3.11+** con tipado estricto (mypy si hay tiempo)
- **FastAPI** para HTTP
- **Pydantic v2** para schemas y validación
- **SQLAlchemy 2.x** + **asyncpg** para Postgres
- **pgvector** vía `pgvector-python`
- **httpx** para llamadas HTTP async
- **structlog** o logging estándar bien configurado

### Datos
- **Supabase** (Postgres + pgvector + Realtime + RLS)
- Migrations versionadas (Supabase CLI o Alembic)

### Orquestación
- **n8n** — disponible vía MCP server. **Usa el MCP de n8n** para crear y actualizar workflows. No edites JSON de n8n a mano.

### LLM providers (Strategy pattern obligatorio)
- **OpenAI** (gpt-4o-mini para barato, gpt-4o para premium)
- **Anthropic** (claude-haiku-4-5 para barato, claude-sonnet-4-5 para premium)
- **Ollama** (local, opcional — útil para PII sensible)
- **OpenRouter** (acceso a Llama, Mistral, etc.)

**El código nunca debe importar SDKs de proveedores directamente fuera del módulo `llm/`.** Todo pasa por `LLMGateway`.

### Tooling
- **uv** o **poetry** para gestión de dependencias
- **ruff** para linting
- **pytest** para tests
- **Claude Code** para desarrollo (tú)

---

## 5. Estructura del proyecto

Monorepo con paquetes. Estructura propuesta:

```
zolvo-prototype/
├── CLAUDE.md                       # este archivo
├── README.md                       # quickstart y demo guide
├── docs/
│   ├── arquitectura-zolvo.md       # diseño completo
│   └── diagrams/                   # PlantUML renderizado (PNG/SVG)
├── pyproject.toml
├── .env.example
├── .gitignore
├── supabase/
│   ├── migrations/                 # SQL versionado
│   └── seed.sql                    # datos de prueba (ICP mexicano)
├── n8n/
│   └── workflows/                  # exports JSON de los flows creados vía MCP
├── src/
│   └── zolvo/
│       ├── __init__.py
│       ├── api/                    # FastAPI controllers
│       │   ├── main.py
│       │   ├── routes/
│       │   └── deps.py
│       ├── agents/                 # cada agente como Strategy
│       │   ├── base.py             # AgentBase abstracto
│       │   ├── researcher.py
│       │   ├── copywriter.py
│       │   ├── conversationalist.py
│       │   ├── scheduler.py
│       │   └── evaluator.py        # Confidence Gate
│       ├── intent/
│       │   └── classifier.py       # Intent Classifier (Puerta 1)
│       ├── orchestrator/
│       │   └── orchestrator.py     # decide a quién invocar
│       ├── llm/                    # Strategy pattern para proveedores
│       │   ├── base.py             # LLMProvider interface
│       │   ├── openai_provider.py
│       │   ├── anthropic_provider.py
│       │   ├── ollama_provider.py
│       │   ├── openrouter_provider.py
│       │   ├── gateway.py          # LLMGateway con routing por costo
│       │   └── prompts/            # prompts versionados, uno por agente
│       ├── memory/
│       │   └── service.py          # Memoria dual: textual + semántica
│       ├── channels/               # adapters para canales
│       │   ├── base.py
│       │   ├── linkedin_mock.py    # mock para el prototipo
│       │   └── email_mock.py
│       ├── repositories/           # Repository pattern
│       │   ├── base.py
│       │   ├── leads.py
│       │   ├── conversations.py
│       │   ├── messages.py
│       │   └── agent_runs.py
│       ├── models/                 # Pydantic + SQLAlchemy models
│       │   └── domain.py
│       ├── events/
│       │   └── bus.py              # Event bus (Supabase Realtime + outbox)
│       ├── observability/
│       │   ├── logging.py
│       │   └── metrics.py
│       └── config.py               # settings via Pydantic Settings
└── tests/
    ├── unit/
    ├── integration/
    └── fixtures/                   # dataset sintético ICP mexicano
```

**No crees módulos que no estén en esta estructura sin pedir permiso.** Si necesitas uno nuevo, pregunta.

---

## 6. Convenciones de código

### Principios (aplicar con criterio, no dogmáticamente)

- **SOLID donde aporta valor.** Strategy pattern para `LLMProvider`, `AgentBase`, `ChannelAdapter` y `Repository`. **No abstraigas lo que solo tiene una implementación y no la va a tener pronto.**
- **Composition over inheritance.** Agentes reciben dependencias por constructor.
- **Dependency injection vía FastAPI.** Sin frameworks DI externos.
- **Inmutabilidad por default.** Modelos Pydantic con `frozen=True` cuando aplique.
- **Async/await en todo el path I/O.** Nada de `requests` síncrono.

### Reglas duras

- Tipado obligatorio en signatures públicas. `from __future__ import annotations` en todos los módulos.
- Docstrings cortos en clases públicas y funciones no triviales. Idioma: inglés (estándar del ecosistema Python).
- Logs estructurados con `extra={...}`, nunca con f-strings.
- Errores de dominio como excepciones específicas (`LLMProviderError`, `ConfidenceTooLowError`, `IntentClassificationError`). Nunca `except Exception` salvo en el borde HTTP.
- Sin código muerto, sin TODOs sin issue/owner asociado, sin comentarios `# this is hacky`.
- **Sin secretos en código.** Todo vía `.env` y `Settings`.

### Tests

- **Unit tests obligatorios** para: `LLMGateway` (routing), `IntentClassifier`, `Evaluator`, `MemoryService`, `Orchestrator`.
- **Integration test obligatorio** para el happy path completo (con mocks de LLM providers).
- **NO escribir tests para Pydantic models simples ni para wrappers triviales.** Tiempo es escaso, prioriza tests con señal.
- Mocks de LLM providers vía interfaz `LLMProvider`. Un `FakeLLMProvider` con respuestas predefinidas debe existir desde temprano.

---

## 7. Workflow de desarrollo

### Regla número 1: planea antes de actuar

**Para cada hito de la sección 8, sigue este protocolo:**

1. Lee el hito y el documento de arquitectura relevante.
2. **Antes de escribir código**, produce un plan corto en este formato:

   ```
   ## Plan: [nombre del hito]

   ### Archivos a crear/modificar
   - path/to/file.py — qué hace

   ### Decisiones técnicas
   - decisión 1 y por qué
   - decisión 2 y por qué

   ### Riesgos / preguntas
   - cosa que no está clara
   - decisión que requiere validación

   ### Tests
   - qué se va a testear

   ### Tiempo estimado: X minutos
   ```

3. Espera aprobación del autor antes de codear.
4. Implementa.
5. Corre tests.
6. Reporta hito completado con: archivos creados, tests pasando, próximo paso sugerido.

**Si el plan está claro y es obviamente correcto, dilo y procede sin esperar.** No introduzcas fricción innecesaria.

### Regla número 2: commits pequeños y descriptivos

- Un commit por unidad funcional cerrada (`feat: add LLMGateway with OpenAI provider`, no `wip`).
- Conventional commits: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`.
- Sin commits con código roto en `main`.

### Regla número 3: cuando dudes, pregunta

- Mejor 30 segundos de pregunta que 30 minutos de código equivocado.
- Si encuentras una ambigüedad en la arquitectura, **detente y pregunta** antes de improvisar.

---

## 8. Hitos de entrega

Cada hito es **demoable**: al terminar, debe haber algo concreto que se pueda mostrar.

### Hito 0 — Setup (estimado 2h)
- Estructura de carpetas
- `pyproject.toml` con dependencias
- `.env.example` con todas las variables
- Supabase: proyecto creado, migrations base, RLS habilitado
- README con quickstart
- CI mínimo: ruff + pytest en GitHub Actions

**DoD:** `uvicorn zolvo.api.main:app` levanta sin errores; `pytest` corre sin tests pero sin fallos.

### Hito 1 — LLM Gateway con Strategy pattern (estimado 3h)
- Interfaz `LLMProvider` abstracta
- Implementaciones: `OpenAIProvider`, `AnthropicProvider`, `FakeLLMProvider` (para tests)
- `LLMGateway` con routing por tipo de tarea (`classification` → barato; `generation_critical` → premium)
- Registro automático de `agent_runs` (costo, latencia, tokens)
- Tests unitarios: routing decide correctamente; provider llamado con params correctos; `agent_runs` se persiste

**DoD:** `gateway.complete(task_type="classification", prompt="...")` funciona con al menos 2 proveedores reales.

### Hito 2 — Modelo de datos y repositorios (estimado 3h)
- Migrations en `supabase/migrations/` para todas las tablas del modelo (sección 9 de arquitectura)
- RLS policies por `tenant_id`
- Repositorios para `leads`, `conversations`, `messages`, `agent_runs`
- Test de integración: insertar lead, leer lead, RLS bloquea cross-tenant

**DoD:** `LeadRepository.create()` y `LeadRepository.get_by_id()` funcionan contra Supabase real.

### Hito 3 — Researcher Agent (estimado 2h)
- `Researcher` implementa `AgentBase`
- Genera enrichment + embedding del lead
- Persiste en `lead_embeddings`
- Registra `agent_runs`

**DoD:** `researcher.run(lead_id)` enriquece un lead de prueba y guarda el embedding.

### Hito 4 — Copywriter Agent (estimado 2h)
- `Copywriter` genera mensaje inicial outbound
- Recupera ejemplos del ICP vía RAG (placeholder si no hay ICP data aún)
- Prompts en español, tono profesional pero cercano (ICP México)
- Registra `agent_runs`

**DoD:** `copywriter.run(lead_id)` produce un mensaje plausible para un lead de fintech mexicana.

### Hito 5 — Intent Classifier (Puerta 1) (estimado 2h)
- `IntentClassifier` clasifica en las 9 categorías del ADR-04
- Usa modelo barato vía `LLMGateway` con `task_type="classification"`
- Retorna `IntentResult(intent: str, should_handoff: bool, reason: str)`
- Tests unitarios con casos de cada categoría usando `FakeLLMProvider`

**DoD:** dado un mensaje de objeción de precio, retorna `objection_price` y `should_handoff=False`. Dado un mensaje de queja, retorna `complaint` y `should_handoff=True`.

### Hito 6 — Memory Service (memoria dual) (estimado 3h)
- `MemoryService.get_short_term(conversation_id, n=15)` → últimos N mensajes textuales
- `MemoryService.get_long_term(query_embedding, top_k=5)` → similarity search en `conversation_summaries_embeddings` y `lead_embeddings`
- `MemoryService.summarize_and_index(conversation_id)` → genera resumen al cerrar conversación
- Tests unitarios con dataset sintético

**DoD:** ambos métodos funcionan; el agente puede consultarlos.

### Hito 7 — Conversationalist Agent (estimado 3h)
- `Conversationalist` mantiene threads multi-turn
- Consume memoria dual vía `MemoryService`
- Recibe el `intent` ya clasificado y ajusta el prompt según categoría
- Registra `agent_runs`

**DoD:** mantiene un thread de 3-4 turnos con coherencia y respondiendo según el intent detectado.

### Hito 8 — Evaluator / Confidence Gate (Puerta 2) (estimado 2h)
- `Evaluator.evaluate(draft, context)` → `EvaluationResult(score, breakdown, should_send, reason)`
- Score en 3 ejes: naturalidad, relevancia, riesgo
- Umbral configurable vía settings
- Tests con drafts buenos y malos usando `FakeLLMProvider`

**DoD:** drafts obviamente malos son rechazados; drafts buenos pasan.

### Hito 9 — Orchestrator (estimado 2h)
- `Orchestrator` coordina el flujo:
  1. Recibe evento `reply.received`
  2. Carga conversación y memoria
  3. Llama a `IntentClassifier`
  4. Si handoff → notifica Slack (puede ser mock); si no → llama al agente apropiado
  5. Llama a `Evaluator`
  6. Si aprobado → persiste y envía vía `ChannelAdapter`; si no → escala
- Test de integración del happy path completo

**DoD:** un evento `reply.received` recorre todo el pipeline sin errores con datos sintéticos.

### Hito 10 — n8n workflow vía MCP (estimado 3h)
- Crear workflow en n8n usando el MCP:
  - Trigger: webhook para nuevo lead
  - HTTP node llama a `/agents/ingest` de la API
  - Trigger: webhook para reply entrante (simulando LinkedIn)
  - HTTP node llama a `/events/reply` de la API
- Export del workflow a `n8n/workflows/`
- README explica cómo importar y correr

**DoD:** disparar un webhook desde curl recorre todo el flujo y deja registro en Supabase.

### Hito 11 — Dataset sintético y demo end-to-end (estimado 2h)
- Crear 5-10 leads realistas de fintech B2B mexicana
- Crear secuencia de respuestas simuladas que cubran: interés, objeción, intent de meeting
- Script `demo/run_happy_path.py` que dispara el flujo completo
- Validar que las respuestas generadas son coherentes y "indistinguibles"

**DoD:** corres `python demo/run_happy_path.py` y todo el pipeline se ejecuta visiblemente; la base queda en estado limpio para grabar el video.

### Hito 12 — Polish para el video (estimado 2h, opcional según tiempo)
- Logs legibles para grabar en pantalla
- Pequeño dashboard CLI o queries SQL preparadas para mostrar métricas (`cost_per_message`, `confidence_score_avg`, `intent_distribution`)
- README final con instrucciones reproducibles

**DoD:** el repo se ve profesional al primer scroll.

---

## 9. Acceso a herramientas (MCP)

**Tienes MCP a n8n disponible.** Úsalo para:
- Crear workflows (en lugar de editar JSON manualmente)
- Listar workflows existentes
- Disparar webhooks de prueba
- Exportar workflows a JSON para versionarlos en `n8n/workflows/`

**Si necesitas información de Supabase, Anthropic API u otra herramienta,** dilo explícitamente. No asumas que tienes acceso a algo no listado.

---

## 10. Anti-patrones a evitar

Estos errores son recurrentes en proyectos rápidos. Evítalos activamente.

- **Abstraer en exceso.** No crees `BaseAbstractFactoryStrategy` para algo que solo tiene una implementación.
- **Tests con mocks anidados.** Si necesitas 4 mocks para un test, el diseño está mal.
- **Hardcodear modelos o prompts.** Modelos van por config; prompts viven en `llm/prompts/` versionados.
- **Logs vacíos o ruidosos.** Loguea decisiones del sistema (qué intent se detectó, qué modelo eligió el router, qué score dio el evaluator). No loguees "function called" en cada función.
- **Try/except con `pass` o `print(e)`.** Errores se propagan o se manejan con criterio.
- **Funciones largas.** Si pasa de 50 líneas, hay un problema de cohesión.
- **Acoplarse al SDK de un LLM en lógica de negocio.** Todo pasa por `LLMGateway`.
- **Olvidar `tenant_id`.** Todas las queries filtran por tenant. RLS es el último guardián, no el primero.
- **"Lo arreglo después".** No queda tiempo de después. O se arregla ya, o se documenta como deuda explícita.

---

## 11. Definition of Done global

El prototipo está terminado cuando:

- [ ] Hitos 0-11 completados
- [ ] `pytest` pasa sin fallos
- [ ] `ruff check .` sin errores
- [ ] Demo end-to-end corre sin intervención manual
- [ ] README en raíz permite a alguien externo clonar, instalar y correr en menos de 10 minutos
- [ ] Métricas básicas se ven al final del happy path
- [ ] El código refleja las decisiones del documento de arquitectura

El video se graba **solo después** de esto. No antes.

---

## 12. Comunicación con el autor

- **Idioma:** español por default. Inglés si es jerga técnica estándar (commits, docstrings).
- **Tono:** directo, sin floritura. Reportes cortos.
- **Cuando termines un hito:** mensaje corto con: archivos creados, tests pasando, comando para validar, próximo hito propuesto.
- **Cuando dudes:** pregunta antes de improvisar.
- **Cuando encuentres deuda:** documéntala explícita en código (`# DEBT: razón. ver issue X.`) y reporta.

---

## 13. Referencias rápidas

- Documento de arquitectura: `docs/arquitectura-zolvo.md`
- Brief original del reto: `docs/zolvo-challenge.pdf` (si está subido)
- Stack docs:
  - Supabase: https://supabase.com/docs
  - pgvector: https://github.com/pgvector/pgvector
  - FastAPI: https://fastapi.tiangolo.com
  - n8n: https://docs.n8n.io

---

## 14. Primera acción esperada

Cuando empiece la sesión de desarrollo, tu primera acción es:

1. Leer `CLAUDE.md` (este archivo) completo
2. Leer `docs/arquitectura-zolvo.md` completo
3. Producir un **plan de ataque para Hito 0** según el formato de la sección 7
4. Esperar aprobación

No empieces a crear archivos antes de eso.
