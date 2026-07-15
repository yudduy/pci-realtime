-- The prediction-market layer has been removed from the product. Preserve its
-- historical data in the archive schema, outside the public API, instead of
-- deleting it.

drop view if exists v_open_forecasts;
drop view if exists v_resolved_forecasts;
drop view if exists v_forecast_performance;
drop view if exists v_market_snapshots;
drop view if exists v_trade_proposals;
drop view if exists v_market_discovery_candidates;

create schema if not exists archive;
revoke all on schema archive from anon, authenticated;

alter table if exists public.forecasts
  drop constraint if exists forecasts_provision_fkey;
alter table if exists public.forecasts
  drop constraint if exists forecasts_run_id_fkey;
alter table if exists public.trade_proposals
  drop constraint if exists trade_proposals_forecast_id_fkey;
alter table if exists public.trade_proposals
  drop constraint if exists trade_proposals_run_id_fkey;
alter table if exists public.forecast_outcomes
  drop constraint if exists forecast_outcomes_forecast_id_fkey;
alter table if exists public.market_discovery_candidates
  drop constraint if exists market_discovery_candidates_run_id_fkey;

do $$
begin
  if to_regclass('public.market_snapshots') is not null then
    alter table public.market_snapshots set schema archive;
  end if;
end
$$;

do $$
begin
  if to_regclass('public.forecasts') is not null then
    alter table public.forecasts set schema archive;
  end if;
end
$$;

do $$
begin
  if to_regclass('public.trade_proposals') is not null then
    alter table public.trade_proposals set schema archive;
  end if;
end
$$;

do $$
begin
  if to_regclass('public.forecast_outcomes') is not null then
    alter table public.forecast_outcomes set schema archive;
  end if;
end
$$;

do $$
begin
  if to_regclass('public.market_discovery_candidates') is not null then
    alter table public.market_discovery_candidates set schema archive;
  end if;
end
$$;
