alter table pipeline_runs drop constraint if exists pipeline_runs_run_type_check;
alter table pipeline_runs
  add constraint pipeline_runs_run_type_check
  check (run_type in ('seed', 'weekly', 'daily_refresh', 'market_discovery', 'agent_intake', 'policy_discovery'));

create table if not exists policy_source_candidates (
  candidate_id text primary key,
  run_id uuid not null references pipeline_runs(run_id),
  schema_version text not null,
  discovered_at timestamptz not null default now(),
  provision text not null references provisions(code),
  source_class text not null
    check (source_class in ('official', 'news', 'analysis', 'mixed')),
  review_state text not null default 'queued'
    check (review_state in ('queued', 'needs_primary_source', 'approved', 'duplicate', 'rejected')),
  promotability text not null
    check (promotability in ('ledger_candidate', 'context_only')),
  source_name text not null,
  source_type text,
  canonical_url text not null,
  resolved_primary_url text,
  title text not null,
  published_at timestamptz,
  citation_quote text,
  citation_section text,
  claim text not null,
  decision_relevance text,
  why_it_matters text,
  confidence numeric not null default 0.5
    check (confidence >= 0 and confidence <= 1),
  search_query text,
  retrieved_at timestamptz not null default now(),
  model_name text,
  prompt_version text,
  idempotency_key text not null,
  duplicate_of text,
  related_evidence_ids text[] not null default '{}',
  reviewer_note text,
  reviewed_at timestamptz,
  promoted_submission_id text references evidence_submissions(submission_id),
  promotion_result jsonb not null default '{}'::jsonb,
  raw_public_metadata jsonb not null default '{}'::jsonb,
  raw_private_metadata jsonb not null default '{}'::jsonb,
  unique (provision, canonical_url, idempotency_key)
);

alter table policy_source_candidates enable row level security;

create index if not exists idx_policy_source_candidates_discovered_at
  on policy_source_candidates (discovered_at desc);
create index if not exists idx_policy_source_candidates_review
  on policy_source_candidates (review_state, discovered_at desc);
create index if not exists idx_policy_source_candidates_provision
  on policy_source_candidates (provision, discovered_at desc);
create index if not exists idx_policy_source_candidates_url
  on policy_source_candidates (canonical_url);

create or replace view v_policy_source_candidates as
select
  c.candidate_id,
  c.run_id,
  c.discovered_at,
  c.provision,
  p.name as provision_name,
  c.source_class,
  c.review_state,
  c.promotability,
  c.source_name,
  c.source_type,
  c.canonical_url,
  c.resolved_primary_url,
  c.title,
  c.published_at,
  c.citation_quote,
  c.citation_section,
  c.claim,
  c.decision_relevance,
  c.why_it_matters,
  c.confidence,
  c.related_evidence_ids,
  c.reviewed_at,
  c.promoted_submission_id,
  c.promotion_result,
  coalesce(c.raw_public_metadata, '{}'::jsonb)
    - 'authorization'
    - 'api_key'
    - 'apikey'
    - 'token'
    - 'raw_response'
    - 'response_body'
    - 'request_headers'
    - 'private_review_notes' as raw_public_metadata
from policy_source_candidates c
join provisions p on p.code = c.provision
where c.review_state = 'approved'
order by c.discovered_at desc, c.provision, c.source_class;

grant select on v_policy_source_candidates to anon, authenticated;
grant all on policy_source_candidates to service_role;
