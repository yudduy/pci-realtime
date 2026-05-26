alter table pipeline_runs drop constraint if exists pipeline_runs_run_type_check;
alter table pipeline_runs
  add constraint pipeline_runs_run_type_check
  check (run_type in ('seed', 'weekly', 'daily_refresh', 'market_discovery'));

create table if not exists market_discovery_candidates (
  candidate_id text primary key,
  run_id uuid not null references pipeline_runs(run_id),
  schema_version text not null,
  generated_at timestamptz not null default now(),
  venue text not null,
  ticker text not null,
  event_ticker text,
  title text not null,
  market_url text,
  status text,
  close_time timestamptz,
  query_name text,
  candidate_rank integer,
  matched_keywords text[] not null default '{}',
  matched_provisions text[] not null default '{}',
  policy_relevant boolean not null default false,
  resolution_clear boolean not null default false,
  eligible_snapshot boolean not null default false,
  rejection_reasons text[] not null default '{}',
  resolution_text text,
  liquidity_dollars numeric,
  volume numeric,
  volume_24h numeric,
  raw_public_metadata jsonb not null default '{}'::jsonb,
  unique (run_id, venue, ticker)
);

alter table market_discovery_candidates enable row level security;

create index if not exists idx_market_discovery_candidates_generated_at
  on market_discovery_candidates (generated_at desc);
create index if not exists idx_market_discovery_candidates_venue_ticker
  on market_discovery_candidates (venue, ticker);
create index if not exists idx_market_discovery_candidates_eligible
  on market_discovery_candidates (eligible_snapshot, generated_at desc);

create or replace view v_market_discovery_candidates as
select
  c.candidate_id,
  c.run_id,
  c.generated_at,
  c.venue,
  c.ticker,
  c.event_ticker,
  c.title,
  c.market_url,
  c.status,
  c.close_time,
  c.query_name,
  c.candidate_rank,
  c.matched_keywords,
  c.matched_provisions,
  c.policy_relevant,
  c.resolution_clear,
  c.eligible_snapshot,
  c.rejection_reasons,
  c.resolution_text,
  c.liquidity_dollars,
  c.volume,
  c.volume_24h,
  c.raw_public_metadata
from market_discovery_candidates c
order by c.generated_at desc, c.eligible_snapshot desc, c.venue, c.candidate_rank;

grant select on v_market_discovery_candidates to anon, authenticated;
grant all on market_discovery_candidates to service_role;
