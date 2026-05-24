# Supabase Setup

## 1. Crear proyecto

1. Ve a [supabase.com](https://supabase.com) → New Project.
2. Elige región: us-east-1 o sa-east-1 (más cerca de México).
3. Anota `Project URL` y las keys (`anon`, `service_role`).

## 2. Configurar variables de entorno

Copia `.env.example` → `.env` y llena:

```
DATABASE_URL=postgresql+asyncpg://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres
SUPABASE_URL=https://[PROJECT_REF].supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
```

## 3. Correr migrations

Desde el SQL Editor de Supabase (o con psql si tienes acceso directo):

```sql
-- Pega el contenido de:
supabase/migrations/00000000000000_init.sql
```

O con psql:

```bash
psql "$DATABASE_URL" -f supabase/migrations/00000000000000_init.sql
```

## 4. Correr seed

```bash
psql "$DATABASE_URL" -f supabase/seed.sql
```

## Migrations futuras

| Archivo | Hito | Contenido |
|---|---|---|
| `00000000000001_domain_tables.sql` | Hito 2 | leads, conversations, messages, agent_runs, lead_embeddings, events_outbox |
