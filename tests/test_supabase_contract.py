from __future__ import annotations

from pathlib import Path


MIGRATION = Path("supabase/migrations/001_core_registry.sql")


def test_public_views_filter_policy_relevant_clear_public_forecasts() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "where m.policy_relevant = true" in sql
    assert sql.count("f.private_info_used = false") >= 3
    assert sql.count("'match' ->> 'policy_relevant'") >= 3
    assert sql.count("'match' ->> 'resolution_clear'") >= 3
