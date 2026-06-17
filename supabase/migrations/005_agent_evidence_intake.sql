alter table pipeline_runs drop constraint if exists pipeline_runs_run_type_check;
alter table pipeline_runs
  add constraint pipeline_runs_run_type_check
  check (run_type in ('seed', 'weekly', 'daily_refresh', 'market_discovery', 'agent_intake'));

create table if not exists agent_runs (
  agent_run_id text primary key,
  agent_name text not null default 'policy-agent',
  target_provision text references provisions(code),
  question text,
  status text not null default 'completed'
    check (status in ('running', 'completed', 'failed')),
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  raw_public_metadata jsonb not null default '{}'::jsonb
);

create table if not exists evidence_submissions (
  submission_id text primary key,
  idempotency_key_hash text not null unique,
  agent_run_id text references agent_runs(agent_run_id),
  provision text not null references provisions(code),
  source_doc_id text references source_documents(source_doc_id),
  evidence_id text references evidence_items(evidence_id),
  event_id text references policy_events(event_id),
  canonical_url text not null,
  source_title text not null,
  claim_hash text not null,
  status text not null
    check (status in ('promoted', 'rejected', 'duplicate', 'quarantined')),
  rejection_reason text,
  promotion_result jsonb not null default '{}'::jsonb,
  submitted_at timestamptz not null default now(),
  promoted_at timestamptz,
  raw_public_metadata jsonb not null default '{}'::jsonb
);

alter table source_documents
  add column if not exists canonical_url text,
  add column if not exists first_seen_at timestamptz,
  add column if not exists last_seen_at timestamptz,
  add column if not exists submitted_by_agent_run_id text references agent_runs(agent_run_id);

alter table evidence_items
  add column if not exists citation_quote text,
  add column if not exists citation_section text,
  add column if not exists citation_page text,
  add column if not exists citation_url_fragment text,
  add column if not exists claim_hash text,
  add column if not exists submitted_by_agent_run_id text references agent_runs(agent_run_id),
  add column if not exists extraction_confidence numeric
    check (extraction_confidence is null or (extraction_confidence >= 0 and extraction_confidence <= 1)),
  add column if not exists raw_public_metadata jsonb not null default '{}'::jsonb;

alter table agent_runs enable row level security;
alter table evidence_submissions enable row level security;

create index if not exists idx_agent_runs_target_provision
  on agent_runs (target_provision, completed_at desc);
create index if not exists idx_evidence_submissions_provision
  on evidence_submissions (provision, submitted_at desc);
create index if not exists idx_evidence_submissions_claim_hash
  on evidence_submissions (claim_hash);
create index if not exists idx_source_documents_canonical_url
  on source_documents (canonical_url);
create index if not exists idx_evidence_items_claim_hash
  on evidence_items (claim_hash);

create or replace view v_agent_runs as
select
  r.agent_run_id,
  r.agent_name,
  r.target_provision,
  p.name as provision_name,
  r.question,
  r.status,
  r.started_at,
  r.completed_at,
  coalesce(r.raw_public_metadata, '{}'::jsonb)
    - 'authorization'
    - 'api_key'
    - 'apikey'
    - 'token'
    - 'raw_response'
    - 'response_body'
    - 'request_headers' as raw_public_metadata
from agent_runs r
left join provisions p on p.code = r.target_provision
order by r.completed_at desc nulls last, r.started_at desc;

create or replace view v_agent_evidence_submissions as
select
  s.submission_id,
  s.agent_run_id,
  s.provision,
  p.name as provision_name,
  s.source_doc_id,
  s.evidence_id,
  s.event_id,
  s.canonical_url,
  s.source_title,
  s.claim_hash,
  s.status,
  s.rejection_reason,
  s.promotion_result,
  s.submitted_at,
  s.promoted_at,
  coalesce(s.raw_public_metadata, '{}'::jsonb)
    - 'authorization'
    - 'api_key'
    - 'apikey'
    - 'token'
    - 'raw_response'
    - 'response_body'
    - 'request_headers' as raw_public_metadata
from evidence_submissions s
join provisions p on p.code = s.provision
order by s.submitted_at desc;

drop view if exists v_evidence_items;
drop view if exists v_source_documents;

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
  d.canonical_url,
  d.published_at,
  d.fetched_at,
  d.first_seen_at,
  d.last_seen_at,
  d.submitted_by_agent_run_id,
  d.text_excerpt,
  coalesce(d.raw_public_metadata, '{}'::jsonb)
    - 'authorization'
    - 'api_key'
    - 'apikey'
    - 'token'
    - 'raw_response'
    - 'response_body'
    - 'request_headers' as raw_public_metadata
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
  e.citation_quote,
  e.citation_section,
  e.citation_page,
  e.citation_url_fragment,
  e.claim_hash,
  e.submitted_by_agent_run_id,
  e.extraction_confidence,
  coalesce(e.raw_public_metadata, '{}'::jsonb)
    - 'authorization'
    - 'api_key'
    - 'apikey'
    - 'token'
    - 'raw_response'
    - 'response_body'
    - 'request_headers' as raw_public_metadata,
  d.source,
  d.source_name,
  d.source_type,
  d.title as source_title,
  d.agency,
  d.url,
  d.canonical_url,
  d.published_at,
  d.fetched_at
from evidence_items e
left join source_documents d on d.source_doc_id = e.source_doc_id
left join provisions p on p.code = e.provision;

grant select on v_agent_runs to anon, authenticated;
grant select on v_agent_evidence_submissions to anon, authenticated;
grant select on v_source_documents to anon, authenticated;
grant select on v_evidence_items to anon, authenticated;

grant all on agent_runs to service_role;
grant all on evidence_submissions to service_role;
grant all on source_documents to service_role;
grant all on evidence_items to service_role;
