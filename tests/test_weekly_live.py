from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from conftest import RecordingSupabaseClient, SelectingSupabaseClient
from pci_realtime.forecast_registry.store import assert_public_payload_safe
from pci_realtime.pipeline.weekly_live import (
    _load_remote_scored_deltas,
    build_weekly_live_rows,
    run_weekly_live,
    write_supabase_rows,
)


FIXED_RUN_ID = "00000000-0000-0000-0000-000000000001"
LEDGER_TABLES = {
    "provisions",
    "pipeline_runs",
    "scored_deltas",
    "pci_weekly",
    "policy_events",
    "source_documents",
    "evidence_items",
    "source_links",
    "source_health",
}


def _raw_doc_row() -> dict[str, Any]:
    return {
        "doc_id": "federal_register:45v-guidance",
        "date": "2025-06-02",
        "source": "federal_register",
        "agency": "Treasury Department; Internal Revenue Service",
        "title": "Clean Hydrogen Production Credit Guidance Under Section 45V",
        "body": "Official guidance narrows eligibility for the clean hydrogen production credit.",
        "body_truncated": False,
        "url": "https://www.federalregister.gov/documents/2025/06/02/45v-guidance",
        "provisions_mentioned": ["45V"],
        "ingested_at": pd.Timestamp("2025-06-02T12:00:00Z"),
        "ingestor_version": "test",
    }


def _scored_row() -> dict[str, Any]:
    return {
        "doc_id": "federal_register:45v-guidance",
        "provision": "45V",
        "specificity_delta": -2.0,
        "durability_delta": -2.0,
        "enforceability_delta": -2.0,
        "relevance_score": 5,
        "rationale": "Treasury guidance narrows eligibility and lowers 45V specificity.",
        "confidence": 0.9,
        "model": "fixture",
        "prompt_version": "test",
        "temperature": 0.0,
        "scored_at": "2025-06-02T12:10:00Z",
        "cached": False,
        "cost_usd": 0.0,
    }


def _source_health_row() -> dict[str, Any]:
    return {
        "source": "federal_register",
        "source_name": "Federal Register",
        "status": "success",
        "row_count": 1,
        "details": {"window_start": "2025-06-02", "window_end": "2025-06-08"},
    }


def _write_fixture_inputs(tmp_path: Path) -> tuple[Path, Path]:
    raw_root = tmp_path / "raw"
    raw_dir = raw_root / "federal_register"
    scored_dir = tmp_path / "scored"
    raw_dir.mkdir(parents=True)
    scored_dir.mkdir()
    pd.DataFrame([_raw_doc_row()]).to_parquet(
        raw_dir / "federal_register_2025-W23.parquet", index=False
    )
    pd.DataFrame([_scored_row()]).to_parquet(
        scored_dir / "scored_2025-W23.parquet", index=False
    )
    return raw_root, scored_dir


def test_weekly_live_rows_materialize_cited_ledger(tmp_path: Path) -> None:
    raw_root, scored_dir = _write_fixture_inputs(tmp_path)

    rows = build_weekly_live_rows(
        week="2025-W23",
        raw_root=raw_root,
        scored_dir=scored_dir,
        run_id=FIXED_RUN_ID,
        ingest_sources=("federal_register",),
        source_health=[_source_health_row()],
    )

    assert set(rows) == LEDGER_TABLES
    assert len(rows["provisions"]) == 6
    assert len(rows["scored_deltas"]) == 1
    assert len(rows["policy_events"]) == 1
    assert len(rows["source_documents"]) == 1
    assert len(rows["evidence_items"]) == 1
    assert len(rows["source_links"]) == 1
    assert rows["source_health"] == [_source_health_row()]
    assert rows["pipeline_runs"][0]["metadata"] == {
        "week": "2025-W23",
        "ingest_sources": ["federal_register"],
        "policy_events": 1,
    }

    event = rows["policy_events"][0]
    evidence = rows["evidence_items"][0]
    link = rows["source_links"][0]
    assert event["event_id"] == "2025-W23:federal_register:45v-guidance:45V"
    assert event["doc_id"] == "federal_register:45v-guidance"
    assert "source_document" not in event
    assert rows["source_documents"][0]["source_doc_id"] == event["doc_id"]
    assert evidence["source_doc_id"] == event["doc_id"]
    assert evidence["evidence_id"] == f"evidence:{event['event_id']}"
    assert link == {
        "link_id": f"link:policy_events:{event['event_id']}",
        "evidence_id": evidence["evidence_id"],
        "target_table": "policy_events",
        "target_id": event["event_id"],
        "link_type": "primary_source",
    }

    row_45v = next(
        row
        for row in rows["pci_weekly"]
        if row["week"] == "2025-W23" and row["provision"] == "45V"
    )
    assert row_45v["data_origin"] == "live_scored"
    assert row_45v["source_event_ids"] == [event["event_id"]]
    assert rows["pci_weekly"][0]["week"] == "2022-W33"
    assert_public_payload_safe(rows)


def test_weekly_live_rows_without_documents_keep_ledger_shape(tmp_path: Path) -> None:
    rows = build_weekly_live_rows(
        week="2025-W23",
        raw_root=tmp_path / "raw",
        scored_dir=tmp_path / "scored",
        run_id=FIXED_RUN_ID,
    )

    assert set(rows) == LEDGER_TABLES
    assert len(rows["provisions"]) == 6
    assert rows["scored_deltas"] == []
    assert rows["policy_events"] == []
    assert rows["source_documents"] == []
    assert rows["evidence_items"] == []
    assert rows["source_links"] == []
    assert rows["source_health"] == []
    assert rows["pipeline_runs"][0]["metadata"]["policy_events"] == 0
    assert all(row["provenance_status"] == "complete" for row in rows["pci_weekly"])


def test_remote_scored_deltas_are_loaded_and_filtered_through_week() -> None:
    client = SelectingSupabaseClient(
        [
            {**_scored_row(), "week": "2025-W22"},
            {**_scored_row(), "doc_id": "future", "week": "2025-W24"},
        ]
    )

    scored = _load_remote_scored_deltas(  # type: ignore[arg-type]
        client, through_week="2025-W23"
    )

    assert client.calls == [
        (
            "scored_deltas",
            "doc_id,provision,specificity_delta,durability_delta,"
            "enforceability_delta,rationale,confidence,model,prompt_version,"
            "temperature,scored_at,cached,cost_usd,week",
            {"week": "lte.2025-W23"},
        )
    ]
    assert scored[["week", "doc_id"]].to_dict("records") == [
        {"week": "2025-W22", "doc_id": "federal_register:45v-guidance"}
    ]


def test_write_supabase_rows_uses_ledger_insert_and_upsert_contract(
    tmp_path: Path,
) -> None:
    raw_root, scored_dir = _write_fixture_inputs(tmp_path)
    rows = build_weekly_live_rows(
        week="2025-W23",
        raw_root=raw_root,
        scored_dir=scored_dir,
        run_id=FIXED_RUN_ID,
        source_health=[_source_health_row()],
    )
    client = RecordingSupabaseClient()

    write_supabase_rows(rows, client=client)  # type: ignore[arg-type]

    assert [
        (method, table, len(recorded_rows), conflict)
        for method, table, recorded_rows, conflict in client.calls
    ] == [
        ("upsert", "provisions", 6, "code"),
        ("upsert", "scored_deltas", 1, "week,doc_id,provision"),
        ("upsert", "pci_weekly", len(rows["pci_weekly"]), "provision,week"),
        ("upsert", "policy_events", 1, "event_id"),
        ("insert", "pipeline_runs", 1, None),
        ("upsert", "source_documents", 1, "source_doc_id"),
        ("upsert", "evidence_items", 1, "evidence_id"),
        ("upsert", "source_links", 1, "link_id"),
        ("upsert", "source_health", 1, "source"),
    ]


def test_weekly_live_dry_run_writes_complete_ledger_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_root, scored_dir = _write_fixture_inputs(tmp_path)
    output_path = tmp_path / "weekly_live_payload.json"
    calls: dict[str, dict[str, Any]] = {}

    def record_ingest(**kwargs: Any) -> list[dict[str, Any]]:
        calls["ingest"] = kwargs
        return [_source_health_row()]

    def record_score(**kwargs: Any) -> Path:
        calls["score"] = kwargs
        return scored_dir / "scored_2025-W23.parquet"

    monkeypatch.setattr(
        "pci_realtime.pipeline.weekly_live.run_official_ingest", record_ingest
    )
    monkeypatch.setattr("pci_realtime.pipeline.weekly_live.score_week", record_score)

    result = run_weekly_live(
        start_date=pd.Timestamp("2025-06-02").date(),
        end_date=pd.Timestamp("2025-06-08").date(),
        raw_root=raw_root,
        scored_dir=scored_dir,
        confirm_cost=True,
        ingest_sources=("federal_register",),
        dry_run=True,
        output_path=output_path,
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert set(result.counts) == LEDGER_TABLES
    assert result.counts["scored_deltas"] == 1
    assert result.counts["policy_events"] == 1
    assert result.counts["source_documents"] == 1
    assert result.counts["evidence_items"] == 1
    assert result.counts["source_links"] == 1
    assert result.counts["source_health"] == 1
    assert set(payload["rows"]) == LEDGER_TABLES
    assert payload["counts"] == result.counts
    assert payload["run_id"] == result.run_id
    assert calls["score"]["confirm_cost"] is True
    assert calls["ingest"]["sources"] == ("federal_register",)


def test_public_payload_guard_allows_public_slugs_but_blocks_keys() -> None:
    assert_public_payload_safe({"slug": "sk-telecom-policy"})

    with pytest.raises(ValueError, match="OpenAI project key"):
        assert_public_payload_safe({"token": "sk-proj-" + "a" * 32})
