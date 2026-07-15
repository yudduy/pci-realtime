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
