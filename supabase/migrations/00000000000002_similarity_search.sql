-- Migration: similarity_search
-- RPC functions for pgvector similarity search.
-- supabase-py does not support the <-> operator directly; .rpc() is the
-- idiomatic way to run similarity queries via the REST API.
-- Both functions use SECURITY DEFINER with an explicit tenant_id parameter
-- (RLS is bypassed in SECURITY DEFINER mode).

-- ─── match_lead_embeddings ──────────────────────────────────────────────────
create or replace function match_lead_embeddings(
    query_embedding vector(1536),
    match_count int default 5,
    filter_tenant_id uuid default null
)
returns table(
    id uuid,
    lead_id uuid,
    source_text text,
    similarity float
)
language plpgsql
security definer
set search_path = public
as $$
begin
    return query
    select
        le.id,
        le.lead_id,
        le.source_text,
        1 - (le.embedding <=> query_embedding) as similarity
    from public.lead_embeddings le
    where le.tenant_id = filter_tenant_id
    order by le.embedding <=> query_embedding
    limit match_count;
end;
$$;

-- ─── match_conversation_summaries ───────────────────────────────────────────
create or replace function match_conversation_summaries(
    query_embedding vector(1536),
    match_count int default 5,
    filter_tenant_id uuid default null
)
returns table(
    id uuid,
    conversation_id uuid,
    summary_text text,
    outcome text,
    similarity float
)
language plpgsql
security definer
set search_path = public
as $$
begin
    return query
    select
        cse.id,
        cse.conversation_id,
        cse.summary_text,
        cse.outcome,
        1 - (cse.embedding <=> query_embedding) as similarity
    from public.conversation_summaries_embeddings cse
    where cse.tenant_id = filter_tenant_id
    order by cse.embedding <=> query_embedding
    limit match_count;
end;
$$;
