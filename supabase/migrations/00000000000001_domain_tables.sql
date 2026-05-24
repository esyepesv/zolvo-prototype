-- Migration: domain_tables
-- Tablas operacionales del AI Sales Engine. Todas con tenant_id + RLS.
-- Prerequisito: 00000000000000_init.sql (extensions + tenants).

-- ─── leads ───────────────────────────────────────────────────────────────────
create table leads (
    id              uuid primary key default uuid_generate_v4(),
    tenant_id       uuid not null references tenants(id),
    source          text not null default 'manual',
    full_name       text not null,
    email           text,
    linkedin_url    text,
    company         text,
    role            text,
    enriched_data   jsonb,
    status          text not null default 'researching',
    owner_id        uuid,
    created_at      timestamptz not null default now()
);
create index idx_leads_tenant_id on leads(tenant_id);
create index idx_leads_tenant_status on leads(tenant_id, status);
alter table leads enable row level security;
create policy leads_tenant_isolation on leads
    using (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ─── lead_embeddings ─────────────────────────────────────────────────────────
create table lead_embeddings (
    id          uuid primary key default uuid_generate_v4(),
    lead_id     uuid not null references leads(id) on delete cascade,
    tenant_id   uuid not null references tenants(id),
    embedding   vector(1536),
    source_text text,
    model_used  text,
    created_at  timestamptz not null default now()
);
create index idx_lead_embeddings_tenant on lead_embeddings(tenant_id);
create index idx_lead_embeddings_lead on lead_embeddings(lead_id);
alter table lead_embeddings enable row level security;
create policy lead_embeddings_tenant_isolation on lead_embeddings
    using (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ─── conversations ────────────────────────────────────────────────────────────
create table conversations (
    id              uuid primary key default uuid_generate_v4(),
    tenant_id       uuid not null references tenants(id),
    lead_id         uuid not null references leads(id) on delete cascade,
    channel         text not null default 'linkedin',
    started_at      timestamptz not null default now(),
    status          text not null default 'researching',
    current_stage   text,
    loss_reason     text
);
create index idx_conversations_tenant on conversations(tenant_id);
create index idx_conversations_lead on conversations(tenant_id, lead_id);
alter table conversations enable row level security;
create policy conversations_tenant_isolation on conversations
    using (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ─── conversation_summaries_embeddings ────────────────────────────────────────
create table conversation_summaries_embeddings (
    id              uuid primary key default uuid_generate_v4(),
    conversation_id uuid not null references conversations(id) on delete cascade,
    tenant_id       uuid not null references tenants(id),
    embedding       vector(1536),
    summary_text    text,
    outcome         text,
    loss_reason     text,
    model_used      text,
    created_at      timestamptz not null default now()
);
create index idx_conv_summaries_tenant on conversation_summaries_embeddings(tenant_id);
alter table conversation_summaries_embeddings enable row level security;
create policy conv_summaries_tenant_isolation on conversation_summaries_embeddings
    using (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ─── messages ────────────────────────────────────────────────────────────────
create table messages (
    id                  uuid primary key default uuid_generate_v4(),
    tenant_id           uuid not null references tenants(id),
    conversation_id     uuid not null references conversations(id) on delete cascade,
    direction           text not null check (direction in ('inbound', 'outbound')),
    channel             text not null default 'linkedin',
    content             text not null,
    generated_by_agent  text,
    confidence_score    numeric(3,2),
    human_reviewed      boolean not null default false,
    sent_at             timestamptz not null default now()
);
create index idx_messages_tenant on messages(tenant_id);
create index idx_messages_conversation on messages(tenant_id, conversation_id, sent_at);
alter table messages enable row level security;
create policy messages_tenant_isolation on messages
    using (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ─── agent_runs ──────────────────────────────────────────────────────────────
create table agent_runs (
    id              uuid primary key default uuid_generate_v4(),
    tenant_id       uuid not null references tenants(id),
    agent_name      text not null,
    conversation_id uuid references conversations(id),
    input_payload   jsonb,
    output_payload  jsonb,
    llm_provider    text,
    llm_model       text,
    tokens_in       integer,
    tokens_out      integer,
    cost_usd        numeric(10,6),
    latency_ms      integer,
    decision_trace  jsonb,
    created_at      timestamptz not null default now()
);
create index idx_agent_runs_tenant on agent_runs(tenant_id);
create index idx_agent_runs_conversation on agent_runs(tenant_id, conversation_id);
alter table agent_runs enable row level security;
create policy agent_runs_tenant_isolation on agent_runs
    using (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ─── events_outbox ────────────────────────────────────────────────────────────
create table events_outbox (
    id              uuid primary key default uuid_generate_v4(),
    tenant_id       uuid not null references tenants(id),
    aggregate_id    uuid not null,
    event_type      text not null,
    payload         jsonb not null default '{}',
    published_at    timestamptz,
    attempts        integer not null default 0,
    created_at      timestamptz not null default now()
);
create index idx_events_outbox_tenant on events_outbox(tenant_id);
create index idx_events_outbox_unpublished on events_outbox(tenant_id, created_at) where published_at is null;
alter table events_outbox enable row level security;
create policy events_outbox_tenant_isolation on events_outbox
    using (tenant_id = current_setting('app.tenant_id', true)::uuid);
