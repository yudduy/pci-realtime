from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from conftest import RecordingSupabaseClient
from pci_realtime.pipeline.daily_refresh import run_daily_refresh


def _context_rows() -> dict[str, list[dict[str, Any]]]:
    return {
        "source_documents": [
            {
                "source_doc_id": "eia:electricity-retail-price:2026-05",
                "source": "eia",
                "title": "U.S. retail electricity price",
            }
        ],
        "evidence_items": [
            {
                "evidence_id": "evidence:context:reginfo:45V",
                "source_doc_id": "reginfo:45v",
                "provision": "45V",
            }
        ],
        "source_links": [
            {
                "link_id": "link:context:reginfo:45V",
                "evidence_id": "evidence:context:reginfo:45V",
                "target_table": "policy_events",
                "target_id": "context:reginfo:45V",
            }
        ],
        "source_health": [
            {
                "source": "eia",
                "source_name": "Energy data",
                "status": "success",
                "row_count": 1,
            }
        ],
    }


def test_daily_refresh_writes_context_rows_with_expected_conflicts() -> None:
    client = RecordingSupabaseClient()

    counts = run_daily_refresh(
        client=client,  # type: ignore[arg-type]
        context_fetcher=_context_rows,
    )

    assert counts == {
        "source_documents": 1,
        "evidence_items": 1,
        "source_links": 1,
        "source_health": 1,
        "pipeline_runs": 1,
    }
    assert [
        (method, table, conflict) for method, table, _, conflict in client.calls
    ] == [
        ("upsert", "source_documents", "source_doc_id"),
        ("upsert", "evidence_items", "evidence_id"),
        ("upsert", "source_links", "link_id"),
        ("upsert", "source_health", "source"),
        ("insert", "pipeline_runs", None),
    ]
    pipeline_run = client.calls[4][2][0]
    assert pipeline_run["run_type"] == "daily_refresh"
    assert pipeline_run["status"] == "success"
    assert pipeline_run["completed_at"]
    assert pipeline_run["metadata"] == {
        "source_documents": 1,
        "evidence_items": 1,
        "source_links": 1,
        "source_health": 1,
    }
    assert client.calls[0][2] == _context_rows()["source_documents"]
    assert client.calls[1][2] == _context_rows()["evidence_items"]
    assert client.calls[2][2] == _context_rows()["source_links"]
    assert client.calls[3][2] == _context_rows()["source_health"]


def test_daily_refresh_does_not_record_success_after_upsert_failure() -> None:
    client = RecordingSupabaseClient(fail_on_table="evidence_items")

    with pytest.raises(RuntimeError, match="forced failure for evidence_items"):
        run_daily_refresh(
            client=client,  # type: ignore[arg-type]
            context_fetcher=_context_rows,
        )

    assert [(method, table) for method, table, _, _ in client.calls] == [
        ("upsert", "source_documents"),
        ("upsert", "evidence_items"),
    ]


def test_daily_refresh_dry_run_calls_context_builder_and_writes_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = tmp_path / "daily_refresh_payload.json"
    calls = 0

    def build_rows() -> dict[str, list[dict[str, Any]]]:
        nonlocal calls
        calls += 1
        return _context_rows()

    monkeypatch.setattr(
        "pci_realtime.pipeline.daily_refresh.build_context_rows", build_rows
    )

    counts = run_daily_refresh(
        dry_run=True,
        output_path=output_path,
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert calls == 1
    assert counts == {
        "source_documents": 1,
        "evidence_items": 1,
        "source_links": 1,
        "source_health": 1,
        "pipeline_runs": 1,
    }
    assert set(payload["rows"]) == {
        "source_documents",
        "evidence_items",
        "source_links",
        "source_health",
        "pipeline_runs",
    }
    assert payload["counts"] == counts
    assert payload["rows"]["source_documents"] == _context_rows()["source_documents"]
    assert payload["rows"]["pipeline_runs"][0]["metadata"]["source_health"] == 1
