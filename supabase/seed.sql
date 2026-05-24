-- Seed: tenant demo para desarrollo y demo end-to-end.
-- El UUID debe coincidir con DEFAULT_TENANT_ID en .env.
-- Seeds de leads ICP México se agregan en Hito 11.

insert into tenants (id, name)
values ('00000000-0000-0000-0000-000000000001', 'Zolvo Demo — Fintech MX')
on conflict (id) do nothing;
