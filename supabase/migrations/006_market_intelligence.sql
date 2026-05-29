create table if not exists market_inventory (
  venue text not null,
  ticker text not null,
  latest_run_id uuid references pipeline_runs(run_id),
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  title text not null,
  market_url text,
  status text,
  close_time timestamptz,
  market_probability numeric,
  yes_bid numeric,
  yes_ask numeric,
  bid_ask_spread numeric,
  liquidity_dollars numeric,
  volume numeric,
  volume_24h numeric,
  open_interest numeric,
  resolution_text text,
  source_payload_hash text not null,
  raw_public_metadata jsonb not null default '{}'::jsonb,
  primary key (venue, ticker)
);

create table if not exists market_assessments (
  assessment_id text primary key,
  schema_version text not null,
  assessed_at timestamptz not null default now(),
  latest_run_id uuid references pipeline_runs(run_id),
  venue text not null,
  ticker text not null,
  provision text not null references provisions(code),
  source_text_hash text not null,
  relevance_class text not null check (
    relevance_class in (
      'direct_policy',
      'implementation_proxy',
      'sector_proxy',
      'macro_context',
      'unrelated'
    )
  ),
  resolution_fit text not null check (
    resolution_fit in ('clear', 'partial', 'ambiguous', 'none')
  ),
  orientation text not null,
  confidence numeric not null check (confidence >= 0 and confidence <= 1),
  evidence_span text,
  rationale text,
  eligible_for_forecast boolean not null default false,
  model_provider text not null,
  model_name text not null,
  prompt_version text not null,
  cached boolean not null default false,
  raw_public_metadata jsonb not null default '{}'::jsonb,
  unique (venue, ticker, provision)
);

alter table market_inventory enable row level security;
alter table market_assessments enable row level security;

create index if not exists idx_market_inventory_last_seen_at
  on market_inventory (last_seen_at desc);
create index if not exists idx_market_inventory_venue_ticker
  on market_inventory (venue, ticker);
create index if not exists idx_market_assessments_provision_relevance
  on market_assessments (provision, relevance_class, confidence desc);
create index if not exists idx_market_assessments_eligible
  on market_assessments (eligible_for_forecast, assessed_at desc);

create or replace function preserve_market_inventory_first_seen()
returns trigger
language plpgsql
as $$
begin
  new.first_seen_at = old.first_seen_at;
  new.last_seen_at = coalesce(new.last_seen_at, now());
  return new;
end;
$$;

drop trigger if exists trg_market_inventory_preserve_first_seen on market_inventory;
create trigger trg_market_inventory_preserve_first_seen
before update on market_inventory
for each row
execute function preserve_market_inventory_first_seen();

create or replace view v_market_inventory as
select
  i.venue,
  i.ticker,
  i.first_seen_at,
  i.last_seen_at,
  i.title,
  i.market_url,
  i.status,
  i.close_time,
  i.market_probability,
  i.yes_bid,
  i.yes_ask,
  i.bid_ask_spread,
  i.liquidity_dollars,
  i.volume,
  i.volume_24h,
  i.open_interest,
  i.resolution_text,
  i.source_payload_hash,
  coalesce(i.raw_public_metadata, '{}'::jsonb)
    - 'authorization'
    - 'api_key'
    - 'apikey'
    - 'token'
    - 'raw_response'
    - 'response_body'
    - 'request_headers' as raw_public_metadata
from market_inventory i;

create or replace view v_market_intelligence as
select
  a.assessment_id,
  a.assessed_at,
  a.venue,
  a.ticker,
  a.provision,
  p.name as provision_name,
  a.relevance_class,
  a.resolution_fit,
  a.orientation,
  a.confidence,
  a.evidence_span,
  a.rationale,
  a.eligible_for_forecast,
  a.model_provider,
  a.model_name,
  a.prompt_version,
  a.cached,
  i.title,
  i.market_url,
  i.status,
  i.close_time,
  i.market_probability,
  i.yes_bid,
  i.yes_ask,
  i.bid_ask_spread,
  i.liquidity_dollars,
  i.volume,
  i.volume_24h,
  i.resolution_text,
  i.first_seen_at,
  i.last_seen_at,
  coalesce(a.raw_public_metadata, '{}'::jsonb)
    - 'authorization'
    - 'api_key'
    - 'apikey'
    - 'token'
    - 'raw_response'
    - 'response_body'
    - 'request_headers' as raw_public_metadata
from market_assessments a
join provisions p on p.code = a.provision
left join market_inventory i on i.venue = a.venue and i.ticker = a.ticker
order by
  a.eligible_for_forecast desc,
  case a.relevance_class
    when 'direct_policy' then 0
    when 'implementation_proxy' then 1
    when 'sector_proxy' then 2
    when 'macro_context' then 3
    else 4
  end,
  a.confidence desc,
  a.assessed_at desc;

grant select on v_market_inventory to anon, authenticated;
grant select on v_market_intelligence to anon, authenticated;
grant all on market_inventory to service_role;
grant all on market_assessments to service_role;
