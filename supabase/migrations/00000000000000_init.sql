-- Migration: init
-- Habilita extensiones y crea estructura base multi-tenant.
-- Las tablas de dominio (leads, conversations, messages, etc.) se agregan en
-- supabase/migrations/00000000000001_domain_tables.sql (Hito 2).

-- Extensions
create extension if not exists "uuid-ossp";
create extension if not exists "vector";

-- Base tenant registry
create table if not exists tenants (
    id          uuid primary key default uuid_generate_v4(),
    name        text not null,
    created_at  timestamptz not null default now()
);

-- RLS on tenants
alter table tenants enable row level security;

-- Service role bypasses RLS by default in Supabase (no explicit policy needed).
-- Authenticated users should only see their own tenant; enforce at app level for now.
-- Full RLS policies per table are added in Hito 2 alongside domain tables.
