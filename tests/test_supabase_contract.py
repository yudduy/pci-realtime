from __future__ import annotations

from pathlib import Path


MIGRATIONS = sorted(Path("supabase/migrations").glob("*.sql"))


def test_public_views_and_permissions_cover_ledger_tables() -> None:
    sql = "\n".join(path.read_text(encoding="utf-8") for path in MIGRATIONS)

    assert sql.count("f.private_info_used = false") >= 3
    assert "create table if not exists source_documents" in sql
    assert "create table if not exists evidence_items" in sql
    assert "create table if not exists scored_deltas" in sql
    assert "grant all on scored_deltas to service_role" in sql
    assert "create table if not exists agent_runs" in sql
    assert "create table if not exists evidence_submissions" in sql
    assert "alter table agent_runs enable row level security" in sql
    assert "alter table evidence_submissions enable row level security" in sql
    assert "grant all on agent_runs to service_role" in sql
    assert "grant all on evidence_submissions to service_role" in sql
    assert "view v_agent_evidence_submissions" in sql
    assert (
        "idempotency_key_hash"
        not in sql.split(
            "create or replace view v_agent_evidence_submissions",
            1,
        )[1].split("grant select on v_agent_evidence_submissions", 1)[0]
    )
    assert sql.count("- 'raw_response'") >= 4
    assert "view v_evidence_items" in sql
    assert "grant select on v_source_health" in sql


def test_prediction_market_schema_is_retired() -> None:
    migration = Path("supabase/migrations/007_retire_prediction_markets.sql")
    assert migration.is_file()

    sql = migration.read_text(encoding="utf-8")
    for view in (
        "v_open_forecasts",
        "v_resolved_forecasts",
        "v_forecast_performance",
        "v_market_snapshots",
        "v_trade_proposals",
        "v_market_discovery_candidates",
    ):
        assert f"drop view if exists {view};" in sql

    for table in (
        "market_snapshots",
        "forecasts",
        "trade_proposals",
        "forecast_outcomes",
        "market_discovery_candidates",
    ):
        assert f"to_regclass('public.{table}')" in sql
        assert f"alter table public.{table} set schema archive;" in sql


def test_vertical_schema_exposes_only_the_weighted_view_to_anon() -> None:
    migration = Path("supabase/migrations/008_verticals.sql")
    assert migration.is_file()

    sql = migration.read_text(encoding="utf-8")
    assert "create table if not exists verticals" in sql
    assert "create table if not exists vertical_provisions" in sql
    assert "references verticals(id) on delete cascade" in sql
    assert "references provisions(code)" in sql
    assert "check (weight > 0)" in sql
    assert "alter table verticals enable row level security" in sql
    assert "alter table vertical_provisions enable row level security" in sql
    assert "create or replace view v_vertical_pci" in sql
    assert "select distinct on (w.provision)" in sql
    assert "where w.delta_this_week <> 0" in sql
    assert "grant all on verticals to service_role" in sql
    assert "grant all on vertical_provisions to service_role" in sql

    anon_grants = [
        line.strip()
        for line in sql.splitlines()
        if line.strip().startswith("grant") and "anon" in line
    ]
    assert anon_grants == ["grant select on v_vertical_pci to anon;"]
