create extension if not exists pgcrypto;

create table if not exists provisions (
  code text primary key,
  name text not null,
  provision_type text not null,
  primary_channel text not null,
  paper_role text not null,
  baseline_specificity numeric not null,
  baseline_durability numeric not null,
  baseline_enforceability numeric not null,
  baseline_pci numeric not null,
  baseline_as_of date not null default date '2022-08-16',
  obbba_delta_pci numeric not null,
  obbba_post_pci numeric not null,
  obbba_summary text not null,
  data_origin text not null default 'paper_anchor',
  updated_at timestamptz not null default now()
);

create table if not exists pipeline_runs (
  run_id uuid primary key default gen_random_uuid(),
  run_type text not null check (run_type in ('seed', 'weekly', 'daily_refresh')),
  status text not null check (status in ('queued', 'running', 'success', 'failed')),
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  git_sha text,
  source text not null default 'python_pipeline',
  error_summary text,
  metadata jsonb not null default '{}'::jsonb
);

create table if not exists pci_weekly (
  provision text not null references provisions(code),
  week text not null,
  week_start date not null,
  pci numeric not null,
  specificity numeric not null,
  durability numeric not null,
  enforceability numeric not null,
  n_docs integer not null default 0,
  delta_this_week numeric not null default 0,
  data_origin text not null,
  source_event_ids text[] not null default '{}',
  provenance_status text not null default 'complete',
  updated_at timestamptz not null default now(),
  primary key (provision, week)
);

create table if not exists policy_events (
  event_id text primary key,
  provision text not null references provisions(code),
  week text not null,
  week_start date not null,
  doc_id text not null,
  doc_source text,
  agency text,
  title text,
  url text,
  pci_delta numeric not null,
  dimension_deltas jsonb not null default '{}'::jsonb,
  rationale text,
  confidence numeric,
  prompt_version text,
  scored_at timestamptz,
  data_origin text not null default 'live_scored',
  created_at timestamptz not null default now()
);

create table if not exists market_snapshots (
  snapshot_id uuid primary key default gen_random_uuid(),
  generated_at timestamptz not null default now(),
  venue text not null default 'kalshi',
  ticker text not null,
  event_ticker text,
  title text not null,
  subtitle text,
  yes_sub_title text,
  no_sub_title text,
  status text,
  result text,
  yes_bid numeric,
  yes_ask numeric,
  bid_ask_spread numeric,
  market_probability numeric,
  liquidity_dollars numeric,
  volume numeric,
  volume_24h numeric,
  open_interest numeric,
  open_time timestamptz,
  close_time timestamptz,
  expected_expiration_time timestamptz,
  latest_expiration_time timestamptz,
  settlement_ts timestamptz,
  rules_primary text,
  rules_secondary text,
  resolution_text text,
  policy_relevant boolean not null default false,
  raw_public_metadata jsonb not null default '{}'::jsonb,
  unique (venue, ticker, generated_at)
);

create table if not exists forecasts (
  forecast_id text primary key,
  created_at timestamptz not null default now(),
  schema_version text not null,
  venue text not null default 'kalshi',
  market_ticker text not null,
  market_title text,
  market_rules text,
  market_status text,
  market_close_time timestamptz,
  provision text not null references provisions(code),
  dimension text,
  pci_delta numeric,
  shock_type text,
  market_probability numeric not null,
  pci_rule_probability numeric not null,
  llm_probability numeric,
  model_probability numeric not null,
  edge numeric not null,
  confidence numeric not null,
  method_version text,
  model_provider text,
  model_name text,
  source_doc jsonb not null default '{}'::jsonb,
  evidence jsonb not null default '{}'::jsonb,
  reasoning jsonb not null default '{}'::jsonb,
  counterarguments text,
  resolution_risk_notes text,
  private_info_used boolean not null default false,
  run_id uuid references pipeline_runs(run_id)
);

create table if not exists trade_proposals (
  proposal_id text primary key,
  created_at timestamptz not null default now(),
  forecast_id text not null references forecasts(forecast_id),
  venue text not null default 'kalshi',
  market_ticker text not null,
  proposed_side text not null,
  order_type text not null check (order_type = 'limit'),
  limit_price numeric not null,
  contracts numeric not null,
  max_order_usd numeric not null,
  estimated_exposure_usd numeric not null,
  edge numeric not null,
  confidence numeric not null,
  risk_passed boolean not null default false,
  approval_status text not null,
  human_approval_required boolean not null default true,
  execution_enabled boolean not null default false,
  rejection_reasons text[] not null default '{}',
  risk_checks jsonb not null default '[]'::jsonb,
  run_id uuid references pipeline_runs(run_id)
);

create table if not exists forecast_outcomes (
  outcome_id text primary key,
  forecast_id text not null references forecasts(forecast_id),
  generated_at timestamptz not null default now(),
  venue text not null default 'kalshi',
  market_ticker text not null,
  result text not null,
  settlement_value numeric not null,
  resolved_at timestamptz not null,
  outcome_source text not null,
  market_status text
);

alter table provisions enable row level security;
alter table pipeline_runs enable row level security;
alter table pci_weekly enable row level security;
alter table policy_events enable row level security;
alter table market_snapshots enable row level security;
alter table forecasts enable row level security;
alter table trade_proposals enable row level security;
alter table forecast_outcomes enable row level security;

create view v_current_pci as
select distinct on (p.code)
  p.code,
  p.name,
  p.provision_type,
  p.primary_channel,
  p.paper_role,
  w.week,
  w.week_start,
  w.pci,
  w.specificity,
  w.durability,
  w.enforceability,
  w.delta_this_week,
  w.data_origin,
  p.baseline_pci,
  p.obbba_delta_pci,
  p.obbba_post_pci,
  p.obbba_summary,
  w.updated_at
from provisions p
left join pci_weekly w on w.provision = p.code
order by p.code, w.week_start desc nulls last;

create view v_provision_timelines as
select
  w.provision,
  p.name,
  w.week,
  w.week_start,
  w.pci,
  w.specificity,
  w.durability,
  w.enforceability,
  w.n_docs,
  w.delta_this_week,
  w.data_origin,
  w.source_event_ids,
  w.provenance_status
from pci_weekly w
join provisions p on p.code = w.provision;

create view v_policy_events as
select
  e.event_id,
  e.provision,
  p.name as provision_name,
  e.week,
  e.week_start,
  e.doc_id,
  e.doc_source,
  e.agency,
  e.title,
  e.url,
  e.pci_delta,
  e.dimension_deltas,
  e.rationale,
  e.confidence,
  e.prompt_version,
  e.scored_at,
  e.created_at
from policy_events e
join provisions p on p.code = e.provision;

create view v_open_forecasts as
select
  f.forecast_id,
  f.created_at,
  f.venue,
  f.market_ticker,
  f.market_title,
  f.market_rules,
  f.market_close_time,
  f.provision,
  p.name as provision_name,
  f.dimension,
  f.pci_delta,
  f.shock_type,
  f.market_probability,
  f.pci_rule_probability,
  f.llm_probability,
  f.model_probability,
  f.edge,
  f.confidence,
  f.method_version,
  f.model_provider,
  f.model_name,
  f.source_doc,
  f.evidence,
  f.reasoning,
  f.counterarguments,
  f.resolution_risk_notes
from forecasts f
join provisions p on p.code = f.provision
left join forecast_outcomes o on o.forecast_id = f.forecast_id
where o.forecast_id is null
  and f.private_info_used = false
  and coalesce((f.reasoning -> 'match' ->> 'policy_relevant')::boolean, false) = true
  and coalesce((f.reasoning -> 'match' ->> 'resolution_clear')::boolean, false) = true;

create view v_resolved_forecasts as
select
  f.forecast_id,
  f.created_at,
  f.venue,
  f.market_ticker,
  f.market_title,
  f.provision,
  p.name as provision_name,
  f.market_probability,
  f.pci_rule_probability,
  f.model_probability,
  f.edge,
  f.confidence,
  o.result,
  o.settlement_value,
  o.resolved_at,
  power(f.model_probability - o.settlement_value, 2) as brier_score
from forecasts f
join provisions p on p.code = f.provision
join forecast_outcomes o on o.forecast_id = f.forecast_id
where f.private_info_used = false
  and coalesce((f.reasoning -> 'match' ->> 'policy_relevant')::boolean, false) = true
  and coalesce((f.reasoning -> 'match' ->> 'resolution_clear')::boolean, false) = true;

create view v_market_snapshots as
select distinct on (m.venue, m.ticker)
  m.snapshot_id,
  m.generated_at,
  m.venue,
  m.ticker,
  m.event_ticker,
  m.title,
  m.subtitle,
  m.status,
  m.result,
  m.yes_bid,
  m.yes_ask,
  m.bid_ask_spread,
  m.market_probability,
  m.liquidity_dollars,
  m.volume,
  m.volume_24h,
  m.open_interest,
  m.close_time,
  m.expected_expiration_time,
  m.latest_expiration_time,
  m.policy_relevant,
  m.resolution_text,
  m.raw_public_metadata ->> 'query_name' as query_name
from market_snapshots m
where m.policy_relevant = true
order by m.venue, m.ticker, m.generated_at desc;

create view v_trade_proposals as
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
    when t.execution_enabled then 'backend_enabled_after_approval'
    else 'public_execution_unavailable'
  end as public_execution_status,
  t.rejection_reasons
from trade_proposals t
join forecasts f on f.forecast_id = t.forecast_id
where f.private_info_used = false
  and coalesce((f.reasoning -> 'match' ->> 'policy_relevant')::boolean, false) = true
  and coalesce((f.reasoning -> 'match' ->> 'resolution_clear')::boolean, false) = true;

create view v_forecast_performance as
select
  count(f.forecast_id) as forecast_count,
  count(o.forecast_id) as resolved_count,
  avg(power(f.model_probability - o.settlement_value, 2)) as model_brier_score,
  avg(power(f.market_probability - o.settlement_value, 2)) as market_brier_score,
  avg(power(f.pci_rule_probability - o.settlement_value, 2)) as pci_brier_score
from forecasts f
left join forecast_outcomes o on o.forecast_id = f.forecast_id
where f.private_info_used = false
  and coalesce((f.reasoning -> 'match' ->> 'policy_relevant')::boolean, false) = true
  and coalesce((f.reasoning -> 'match' ->> 'resolution_clear')::boolean, false) = true;

create view v_pipeline_status as
select
  r.run_id,
  r.run_type,
  r.status,
  r.started_at,
  r.completed_at,
  r.git_sha,
  r.source,
  r.error_summary,
  r.metadata
from pipeline_runs r
order by r.started_at desc
limit 20;

revoke all on all tables in schema public from anon, authenticated;
grant select on v_current_pci to anon, authenticated;
grant select on v_provision_timelines to anon, authenticated;
grant select on v_policy_events to anon, authenticated;
grant select on v_open_forecasts to anon, authenticated;
grant select on v_resolved_forecasts to anon, authenticated;
grant select on v_market_snapshots to anon, authenticated;
grant select on v_trade_proposals to anon, authenticated;
grant select on v_forecast_performance to anon, authenticated;
grant select on v_pipeline_status to anon, authenticated;

grant all on provisions to service_role;
grant all on pipeline_runs to service_role;
grant all on pci_weekly to service_role;
grant all on policy_events to service_role;
grant all on market_snapshots to service_role;
grant all on forecasts to service_role;
grant all on trade_proposals to service_role;
grant all on forecast_outcomes to service_role;
