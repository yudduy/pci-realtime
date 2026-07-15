-- Manual rollback for 006_retire_prediction_markets.sql. This file is kept
-- outside supabase/migrations so it is never applied automatically.

alter table if exists archive.market_snapshots set schema public;
alter table if exists archive.forecasts set schema public;
alter table if exists archive.trade_proposals set schema public;
alter table if exists archive.forecast_outcomes set schema public;
alter table if exists archive.market_discovery_candidates set schema public;

alter table public.forecasts
  add constraint forecasts_provision_fkey
  foreign key (provision) references public.provisions(code);
alter table public.forecasts
  add constraint forecasts_run_id_fkey
  foreign key (run_id) references public.pipeline_runs(run_id);
alter table public.trade_proposals
  add constraint trade_proposals_forecast_id_fkey
  foreign key (forecast_id) references public.forecasts(forecast_id);
alter table public.trade_proposals
  add constraint trade_proposals_run_id_fkey
  foreign key (run_id) references public.pipeline_runs(run_id);
alter table public.forecast_outcomes
  add constraint forecast_outcomes_forecast_id_fkey
  foreign key (forecast_id) references public.forecasts(forecast_id);
alter table public.market_discovery_candidates
  add constraint market_discovery_candidates_run_id_fkey
  foreign key (run_id) references public.pipeline_runs(run_id);

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

grant select on v_open_forecasts to anon, authenticated;
grant select on v_resolved_forecasts to anon, authenticated;
grant select on v_forecast_performance to anon, authenticated;
grant select on v_market_snapshots to anon, authenticated;
grant select on v_trade_proposals to anon, authenticated;
grant select on v_market_discovery_candidates to anon, authenticated;
