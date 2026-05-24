# Supabase Setup

## 1. Crear proyecto

1. Ve a [supabase.com](https://supabase.com) → New Project.
2. Elige región: us-east-1 o sa-east-1 (más cerca de México).
3. Anota `Project URL` y las keys (`anon`, `service_role`).

## 2. Configurar variables de entorno

Copia `.env.example` → `.env` y llena:

```
SUPABASE_URL=https://[PROJECT_REF].supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
```

> **Nota:** Este proyecto usa `supabase-py` (REST/HTTPS) en lugar de asyncpg directo.
> El host directo de Supabase (`db.[ref].supabase.co`) sólo tiene IPv6 — no alcanzable desde WSL2.
> `supabase-py` resuelve al CDN CloudFlare (IPv4) sin problema. No es necesario `DATABASE_URL`.

## 3. Correr migrations

Desde el SQL Editor de Supabase, pega y ejecuta en orden:

```
supabase/migrations/00000000000000_init.sql
supabase/migrations/00000000000001_domain_tables.sql
supabase/migrations/00000000000002_similarity_search.sql
```

## 4. Correr seed

```
supabase/seed.sql
```

Inserta el tenant demo con UUID `00000000-0000-0000-0000-000000000001`.

## Migrations

| Archivo | Contenido |
|---|---|
| `00000000000000_init.sql` | Extensiones (`pgvector`, `uuid-ossp`), tabla `tenants`, RLS base |
| `00000000000001_domain_tables.sql` | `leads`, `conversations`, `messages`, `agent_runs`, `lead_embeddings`, `events_outbox`, RLS policies + índices |
| `00000000000002_similarity_search.sql` | Funciones `match_lead_embeddings()` y `match_conversation_summaries()` para similarity search con pgvector |

> **Nota sobre `search_path`:** las funciones SECURITY DEFINER de la migración 002 usan
> `set search_path = public` (no `''`). Necesario para que el operador `<=>` de pgvector
> resuelva en contexto SECURITY DEFINER.

## Tablas principales

| Tabla | Descripción |
|---|---|
| `tenants` | Tenants del sistema (multi-tenant) |
| `leads` | Leads enriquecidos por el Researcher |
| `lead_embeddings` | Embeddings vectoriales de perfiles de leads (1536-dim, `openai/text-embedding-3-small`) |
| `conversations` | Conversaciones por lead y canal |
| `messages` | Mensajes inbound/outbound con `confidence_score` y `generated_by_agent` |
| `agent_runs` | Trazabilidad: agente, modelo, tokens, costo, latencia, `input_payload`, `output_payload` |
| `conversation_summaries_embeddings` | Memoria de largo plazo: resúmenes vectorizados de conversaciones cerradas |
| `events_outbox` | Outbox pattern para entrega confiable de eventos de dominio |

## Tenant demo

El seed inserta el tenant `00000000-0000-0000-0000-000000000001` usado por el demo script y los tests de integración.
