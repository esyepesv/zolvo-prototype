# Supabase Setup

## 1. Create a project

1. Go to [supabase.com](https://supabase.com) → New Project.
2. Choose a region: us-east-1 or sa-east-1 (closest to Mexico).
3. Note down the `Project URL` and the keys (`anon`, `service_role`).

## 2. Configure environment variables

Copy `.env.example` → `.env` and fill in:

```
SUPABASE_URL=https://[PROJECT_REF].supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
```

> **Note:** This project uses `supabase-py` (REST/HTTPS) instead of direct asyncpg.
> The direct Supabase host (`db.[ref].supabase.co`) is IPv6-only — unreachable from WSL2.
> `supabase-py` resolves to the CloudFlare CDN (IPv4) without issues. `DATABASE_URL` is not needed.

## 3. Apply migrations

From the Supabase SQL Editor, paste and run in order:

```
supabase/migrations/00000000000000_init.sql
supabase/migrations/00000000000001_domain_tables.sql
supabase/migrations/00000000000002_similarity_search.sql
```

## 4. Run the seed

```
supabase/seed.sql
```

Inserts the demo tenant with UUID `00000000-0000-0000-0000-000000000001`.

## Migrations

| File | Contents |
|---|---|
| `00000000000000_init.sql` | Extensions (`pgvector`, `uuid-ossp`), `tenants` table, base RLS |
| `00000000000001_domain_tables.sql` | `leads`, `conversations`, `messages`, `agent_runs`, `lead_embeddings`, `events_outbox`, RLS policies + indexes |
| `00000000000002_similarity_search.sql` | `match_lead_embeddings()` and `match_conversation_summaries()` functions for pgvector similarity search |

> **Note on `search_path`:** the SECURITY DEFINER functions in migration 002 use
> `set search_path = public` (not `''`). Required so that the pgvector `<=>` operator
> resolves correctly in SECURITY DEFINER context.

## Main tables

| Table | Description |
|---|---|
| `tenants` | System tenants (multi-tenant) |
| `leads` | Leads enriched by the Researcher agent |
| `lead_embeddings` | Vector embeddings of lead profiles (1536-dim, `openai/text-embedding-3-small`) |
| `conversations` | Conversations per lead and channel |
| `messages` | Inbound/outbound messages with `confidence_score` and `generated_by_agent` |
| `agent_runs` | Full traceability: agent, model, tokens, cost, latency, `input_payload`, `output_payload` |
| `conversation_summaries_embeddings` | Long-term memory: vector-indexed summaries of closed conversations |
| `events_outbox` | Outbox pattern for reliable domain event delivery |

## Demo tenant

The seed inserts tenant `00000000-0000-0000-0000-000000000001`, used by the demo script and integration tests.
