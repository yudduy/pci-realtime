alter table pipeline_runs drop constraint if exists pipeline_runs_run_type_check;
alter table pipeline_runs
  add constraint pipeline_runs_run_type_check
  check (run_type in (
    'seed',
    'weekly',
    'daily_refresh',
    'market_discovery',
    'agent_intake',
    'policy_discovery',
    'policy_beliefs',
    'policy_briefs'
  ));

alter table source_documents
  add column if not exists source_retrieved_at timestamptz,
  add column if not exists source_retrieval_method text,
  add column if not exists source_content_hash text;

alter table evidence_items
  add column if not exists quote_hash text,
  add column if not exists quote_verified_against_source boolean not null default false,
  add column if not exists quote_locator_type text,
  add column if not exists quote_locator_value text;

alter table evidence_submissions
  add column if not exists verification_status text not null default 'not_checked'
    check (verification_status in ('not_checked', 'verified', 'unverified', 'override')),
  add column if not exists verification_result jsonb not null default '{}'::jsonb,
  add column if not exists reviewed_by text,
  add column if not exists review_decision_code text,
  add column if not exists approval_basis text,
  add column if not exists promotion_policy_version text;

alter table policy_source_candidates
  add column if not exists verification_status text not null default 'not_checked'
    check (verification_status in ('not_checked', 'verified', 'unverified', 'override')),
  add column if not exists quote_verified_against_source boolean not null default false,
  add column if not exists source_retrieved_at timestamptz,
  add column if not exists source_retrieval_method text,
  add column if not exists source_content_hash text,
  add column if not exists quote_hash text,
  add column if not exists quote_locator_type text,
  add column if not exists quote_locator_value text,
  add column if not exists reviewed_by text,
  add column if not exists review_decision_code text,
  add column if not exists approval_basis text,
  add column if not exists promotion_policy_version text;

create table if not exists policy_theses (
  thesis_id text primary key,
  provision text not null references provisions(code),
  thesis_type text not null
    check (thesis_type in (
      'legal_durability',
      'implementation_timing',
      'rule_strictness',
      'budget_exposure',
      'administrative_capacity',
      'coalition_pressure',
      'market_consensus',
      'decision_relevance'
    )),
  question text not null,
  prior_probability numeric not null
    check (prior_probability > 0 and prior_probability < 1),
  current_probability numeric not null
    check (current_probability > 0 and current_probability < 1),
  confidence numeric not null default 0.5
    check (confidence >= 0 and confidence <= 1),
  status text not null default 'active'
    check (status in ('active', 'paused', 'resolved')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  raw_public_metadata jsonb not null default '{}'::jsonb,
  raw_private_metadata jsonb not null default '{}'::jsonb
);

create table if not exists belief_updates (
  update_id text primary key,
  thesis_id text not null references policy_theses(thesis_id),
  provision text not null references provisions(code),
  run_id uuid references pipeline_runs(run_id),
  prior_probability numeric not null
    check (prior_probability > 0 and prior_probability < 1),
  likelihood_ratio numeric not null
    check (likelihood_ratio > 0),
  posterior_probability numeric not null
    check (posterior_probability > 0 and posterior_probability < 1),
  direction text not null
    check (direction in ('strengthens', 'weakens', 'neutral', 'ambiguous')),
  magnitude text not null
    check (magnitude in ('low', 'medium', 'high')),
  reliability text not null
    check (reliability in ('low', 'medium', 'high')),
  novelty text not null
    check (novelty in ('duplicate', 'incremental', 'new')),
  affected_evidence_ids text[] not null default '{}',
  affected_candidate_ids text[] not null default '{}',
  market_snapshot_ids uuid[] not null default '{}',
  rationale text not null,
  counterargument text,
  decision_implication text,
  model_name text,
  prompt_version text,
  updater_version text not null,
  replay_hash text not null,
  adjudication_state text not null default 'approved'
    check (adjudication_state in ('proposed', 'approved', 'rejected', 'superseded')),
  created_at timestamptz not null default now(),
  raw_public_metadata jsonb not null default '{}'::jsonb,
  raw_private_metadata jsonb not null default '{}'::jsonb
);

create table if not exists policy_briefs (
  brief_id text primary key,
  provision text not null references provisions(code),
  brief_type text not null
    check (brief_type in ('daily', 'weekly')),
  period_start date not null,
  period_end date not null,
  generated_at timestamptz not null default now(),
  title text not null,
  summary text not null,
  what_changed text not null,
  why_it_matters text not null,
  decision_relevance text not null,
  watch_items text[] not null default '{}',
  evidence_ids text[] not null default '{}',
  candidate_ids text[] not null default '{}',
  thesis_update_ids text[] not null default '{}',
  source_health_summary jsonb not null default '{}'::jsonb,
  raw_public_metadata jsonb not null default '{}'::jsonb,
  raw_private_metadata jsonb not null default '{}'::jsonb,
  unique (provision, brief_type, period_start, period_end)
);

alter table policy_theses enable row level security;
alter table belief_updates enable row level security;
alter table policy_briefs enable row level security;

create index if not exists idx_policy_source_candidates_verification
  on policy_source_candidates (verification_status, quote_verified_against_source);
create index if not exists idx_evidence_items_policy_verified
  on evidence_items (provision, quote_verified_against_source, created_at desc);
create index if not exists idx_policy_theses_provision_status
  on policy_theses (provision, status);
create index if not exists idx_belief_updates_thesis_created
  on belief_updates (thesis_id, created_at desc);
create index if not exists idx_belief_updates_provision_state
  on belief_updates (provision, adjudication_state, created_at desc);
create index if not exists idx_policy_briefs_provision_period
  on policy_briefs (provision, brief_type, period_end desc);

drop view if exists v_policy_source_candidates;
drop view if exists v_agent_evidence_submissions;
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
  d.source_retrieved_at,
  d.source_retrieval_method,
  d.source_content_hash,
  coalesce(d.raw_public_metadata, '{}'::jsonb)
    - 'authorization'
    - 'api_key'
    - 'apikey'
    - 'token'
    - 'raw_response'
    - 'response_body'
    - 'request_headers'
    - 'private_review_notes' as raw_public_metadata
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
  e.quote_hash,
  e.quote_verified_against_source,
  e.quote_locator_type,
  e.quote_locator_value,
  e.submitted_by_agent_run_id,
  e.extraction_confidence,
  coalesce(e.raw_public_metadata, '{}'::jsonb)
    - 'authorization'
    - 'api_key'
    - 'apikey'
    - 'token'
    - 'raw_response'
    - 'response_body'
    - 'request_headers'
    - 'private_review_notes' as raw_public_metadata,
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

create or replace view v_policy_evidence_items as
select *
from v_evidence_items
where provision is not null
  and evidence_type not in ('market_snapshot')
  and quote_verified_against_source = true;

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
  s.verification_status,
  s.review_decision_code,
  s.promotion_policy_version,
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
    - 'request_headers'
    - 'private_review_notes' as raw_public_metadata
from evidence_submissions s
join provisions p on p.code = s.provision
order by s.submitted_at desc;

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
  c.verification_status,
  c.quote_verified_against_source,
  c.source_retrieved_at,
  c.source_retrieval_method,
  c.quote_locator_type,
  c.review_decision_code,
  c.promotion_policy_version,
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
    - 'private_review_notes'
    - 'reviewer_note'
    - 'reviewed_by' as raw_public_metadata
from policy_source_candidates c
join provisions p on p.code = c.provision
where c.review_state = 'approved'
order by c.discovered_at desc, c.provision, c.source_class;

create or replace view v_policy_theses as
select
  t.thesis_id,
  t.provision,
  p.name as provision_name,
  t.thesis_type,
  t.question,
  t.prior_probability,
  t.current_probability,
  t.confidence,
  t.status,
  t.created_at,
  t.updated_at,
  coalesce(t.raw_public_metadata, '{}'::jsonb)
    - 'authorization'
    - 'api_key'
    - 'apikey'
    - 'token'
    - 'raw_response'
    - 'response_body'
    - 'request_headers'
    - 'private_review_notes' as raw_public_metadata
from policy_theses t
join provisions p on p.code = t.provision
where t.status = 'active'
order by t.provision, t.thesis_type, t.created_at;

create or replace view v_belief_updates as
select
  u.update_id,
  u.thesis_id,
  t.question as thesis_question,
  u.provision,
  p.name as provision_name,
  u.run_id,
  u.prior_probability,
  u.likelihood_ratio,
  u.posterior_probability,
  u.direction,
  u.magnitude,
  u.reliability,
  u.novelty,
  u.affected_evidence_ids,
  u.affected_candidate_ids,
  u.market_snapshot_ids,
  u.rationale,
  u.counterargument,
  u.decision_implication,
  u.updater_version,
  u.replay_hash,
  u.adjudication_state,
  u.created_at,
  coalesce(u.raw_public_metadata, '{}'::jsonb)
    - 'authorization'
    - 'api_key'
    - 'apikey'
    - 'token'
    - 'raw_response'
    - 'response_body'
    - 'request_headers'
    - 'private_review_notes' as raw_public_metadata
from belief_updates u
join policy_theses t on t.thesis_id = u.thesis_id
join provisions p on p.code = u.provision
where u.adjudication_state = 'approved'
order by u.created_at desc;

create or replace view v_policy_briefs as
select
  b.brief_id,
  b.provision,
  p.name as provision_name,
  b.brief_type,
  b.period_start,
  b.period_end,
  b.generated_at,
  b.title,
  b.summary,
  b.what_changed,
  b.why_it_matters,
  b.decision_relevance,
  b.watch_items,
  b.evidence_ids,
  b.candidate_ids,
  b.thesis_update_ids,
  b.source_health_summary,
  coalesce(b.raw_public_metadata, '{}'::jsonb)
    - 'authorization'
    - 'api_key'
    - 'apikey'
    - 'token'
    - 'raw_response'
    - 'response_body'
    - 'request_headers'
    - 'private_review_notes' as raw_public_metadata
from policy_briefs b
join provisions p on p.code = b.provision
order by b.period_end desc, b.provision;

grant select on v_source_documents to anon, authenticated;
grant select on v_evidence_items to anon, authenticated;
grant select on v_policy_evidence_items to anon, authenticated;
grant select on v_agent_evidence_submissions to anon, authenticated;
grant select on v_policy_source_candidates to anon, authenticated;
grant select on v_policy_theses to anon, authenticated;
grant select on v_belief_updates to anon, authenticated;
grant select on v_policy_briefs to anon, authenticated;

grant all on policy_theses to service_role;
grant all on belief_updates to service_role;
grant all on policy_briefs to service_role;
grant all on source_documents to service_role;
grant all on evidence_items to service_role;
grant all on evidence_submissions to service_role;
grant all on policy_source_candidates to service_role;
