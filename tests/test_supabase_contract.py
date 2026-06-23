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
    assert "create table if not exists scored_deltas" in sql
    assert "create table if not exists market_discovery_candidates" in sql
    assert "'market_discovery'" in sql
    assert "grant all on scored_deltas to service_role" in sql
    assert "grant all on market_discovery_candidates to service_role" in sql
    assert "create table if not exists agent_runs" in sql
    assert "create table if not exists evidence_submissions" in sql
    assert "create table if not exists policy_source_candidates" in sql
    assert "'policy_discovery'" in sql
    assert "alter table agent_runs enable row level security" in sql
    assert "alter table evidence_submissions enable row level security" in sql
    assert "alter table policy_source_candidates enable row level security" in sql
    assert "grant all on agent_runs to service_role" in sql
    assert "grant all on evidence_submissions to service_role" in sql
    assert "grant all on policy_source_candidates to service_role" in sql
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
    assert "view v_market_discovery_candidates" in sql
    assert "view v_policy_source_candidates" in sql
    policy_candidate_view = sql.split(
        "create or replace view v_policy_source_candidates",
        1,
    )[1].split("grant select on v_policy_source_candidates", 1)[0]
    assert "raw_private_metadata" not in policy_candidate_view
    assert "where c.review_state = 'approved'" in policy_candidate_view
    assert "grant select on v_source_health" in sql
