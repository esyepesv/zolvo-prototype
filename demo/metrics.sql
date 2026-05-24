-- Zolvo AI Sales Engine — Demo Metrics
-- Run these in the Supabase SQL Editor after executing run_happy_path.py

-- ─── Cost per message sent ───────────────────────────────────────────────────
select
    agent_name,
    count(*)                                    as runs,
    sum(tokens_in)                              as total_tokens_in,
    sum(tokens_out)                             as total_tokens_out,
    round(sum(cost_usd)::numeric, 6)            as total_cost_usd,
    round(avg(cost_usd)::numeric, 6)            as avg_cost_usd,
    round(avg(latency_ms)::numeric, 0)          as avg_latency_ms
from agent_runs
where tenant_id = '00000000-0000-0000-0000-000000000001'
group by agent_name
order by total_cost_usd desc;

-- ─── Confidence score distribution ──────────────────────────────────────────
select
    round(cast(output_payload->>'score' as numeric), 3) as confidence_score,
    output_payload->>'should_send'                       as should_send,
    created_at
from agent_runs
where tenant_id = '00000000-0000-0000-0000-000000000001'
  and agent_name = 'evaluator'
order by created_at desc
limit 20;

-- ─── Intent distribution ────────────────────────────────────────────────────
select
    output_payload->>'intent'   as intent,
    count(*)                    as occurrences
from agent_runs
where tenant_id = '00000000-0000-0000-0000-000000000001'
  and agent_name = 'intent_classifier'
group by intent
order by occurrences desc;

-- ─── Pipeline totals ────────────────────────────────────────────────────────
select
    count(distinct l.id)                       as total_leads,
    count(distinct c.id)                       as total_conversations,
    count(m.id) filter (where m.role = 'user') as prospect_messages,
    count(m.id) filter (where m.role = 'assistant') as agent_replies,
    round(sum(ar.cost_usd)::numeric, 4)        as total_cost_usd
from leads l
left join conversations c on c.lead_id = l.id and c.tenant_id = l.tenant_id
left join messages m on m.conversation_id = c.id
left join agent_runs ar on ar.tenant_id = l.tenant_id
where l.tenant_id = '00000000-0000-0000-0000-000000000001';
