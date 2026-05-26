create table if not exists source_documents (
  source_doc_id text primary key,
  source text not null,
  source_name text not null,
  source_type text not null,
  external_id text,
  title text not null,
  agency text,
  url text,
  published_at timestamptz,
  fetched_at timestamptz not null default now(),
  content_hash text not null,
  text_excerpt text,
  raw_public_metadata jsonb not null default '{}'::jsonb
);

create table if not exists evidence_items (
  evidence_id text primary key,
  source_doc_id text references source_documents(source_doc_id),
  provision text references provisions(code),
  evidence_type text not null,
  snippet text,
  normalized_signal text,
  score_dimension text,
  confidence numeric,
  extractor_version text,
  created_at timestamptz not null default now()
);

create table if not exists source_links (
  link_id text primary key,
  evidence_id text references evidence_items(evidence_id),
  target_table text not null,
  target_id text not null,
  link_type text not null,
  created_at timestamptz not null default now()
);

create table if not exists source_health (
  source text primary key,
  source_name text not null,
  status text not null,
  last_attempt_at timestamptz not null default now(),
  last_success_at timestamptz,
  latency_ms integer,
  row_count integer not null default 0,
  last_error_class text,
  last_error_summary text,
  details jsonb not null default '{}'::jsonb
);

alter table source_documents enable row level security;
alter table evidence_items enable row level security;
alter table source_links enable row level security;
alter table source_health enable row level security;

create or replace view v_trade_proposals as
select
  t.proposal_id,
  t.created_at,
  t.forecast_id,
  t.venue,
  t.market_ticker,
  t.edge,
  t.confidence,
  t.risk_passed,
  t.approval_status,
  t.human_approval_required,
  case
    when t.execution_enabled then 'review_enabled_after_approval'
    else 'public_execution_unavailable'
  end as public_execution_status,
  t.rejection_reasons
from trade_proposals t
join forecasts f on f.forecast_id = t.forecast_id
where f.private_info_used = false
  and coalesce((f.reasoning -> 'match' ->> 'policy_relevant')::boolean, false) = true
  and coalesce((f.reasoning -> 'match' ->> 'resolution_clear')::boolean, false) = true;

create or replace view v_source_documents as
select
  d.source_doc_id,
  d.source,
  d.source_name,
  d.source_type,
  d.external_id,
  d.title,
  d.agency,
  d.url,
  d.published_at,
  d.fetched_at,
  d.text_excerpt,
  d.raw_public_metadata
from source_documents d;

create or replace view v_evidence_items as
select
  e.evidence_id,
  e.source_doc_id,
  e.provision,
  p.name as provision_name,
  e.evidence_type,
  e.snippet,
  e.normalized_signal,
  e.score_dimension,
  e.confidence,
  e.extractor_version,
  e.created_at,
  d.source,
  d.source_name,
  d.source_type,
  d.title as source_title,
  d.agency,
  d.url,
  d.published_at,
  d.fetched_at
from evidence_items e
left join source_documents d on d.source_doc_id = e.source_doc_id
left join provisions p on p.code = e.provision;

create or replace view v_source_links as
select
  l.link_id,
  l.evidence_id,
  l.target_table,
  l.target_id,
  l.link_type,
  l.created_at
from source_links l;

create or replace view v_source_health as
select
  h.source,
  h.source_name,
  h.status,
  h.last_attempt_at,
  h.last_success_at,
  h.latency_ms,
  h.row_count,
  h.last_error_class,
  h.last_error_summary,
  h.details
from source_health h
order by
  case h.status when 'success' then 0 when 'disabled' then 1 else 2 end,
  h.source_name asc;

grant select on v_source_documents to anon, authenticated;
grant select on v_evidence_items to anon, authenticated;
grant select on v_source_links to anon, authenticated;
grant select on v_source_health to anon, authenticated;
grant select on v_trade_proposals to anon, authenticated;

grant all on source_documents to service_role;
grant all on evidence_items to service_role;
grant all on source_links to service_role;
grant all on source_health to service_role;
