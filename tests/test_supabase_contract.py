from __future__ import annotations

from pathlib import Path


MIGRATIONS = sorted(Path("supabase/migrations").glob("*.sql"))


def test_public_views_filter_policy_relevant_clear_public_forecasts() -> None:
    sql = "\n".join(path.read_text(encoding="utf-8") for path in MIGRATIONS)

    assert "where m.policy_relevant = true" in sql
    assert sql.count("f.private_info_used = false") >= 3
    assert sql.count("'match' ->> 'policy_relevant'") >= 3
    assert sql.count("'match' ->> 'resolution_clear'") >= 3
    assert "create table if not exists source_documents" in sql
    assert "create table if not exists evidence_items" in sql
    assert "create table if not exists source_request_cache" in sql
    assert "create table if not exists document_chunks" in sql
    assert "add column if not exists raw_public_metadata" in sql
    assert "create table if not exists scored_deltas" in sql
    assert "create table if not exists market_discovery_candidates" in sql
    assert "'market_discovery'" in sql
    assert "grant all on scored_deltas to service_role" in sql
    assert "grant all on market_discovery_candidates to service_role" in sql
    assert "grant all on source_request_cache to service_role" in sql
    assert "grant all on document_chunks to service_role" in sql
    assert "grant select on source_request_cache" not in sql
    assert "grant select on document_chunks" not in sql
    assert "view v_evidence_items" in sql
    assert "view v_market_discovery_candidates" in sql
    assert "grant select on v_source_health" in sql
