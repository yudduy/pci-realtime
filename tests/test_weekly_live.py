from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from pci_realtime.pipeline.weekly_live import (
    build_weekly_live_rows,
    run_weekly_live,
    write_supabase_rows,
)


FIXED_RUN_ID = "00000000-0000-0000-0000-000000000001"


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


def _market_fixture() -> dict[str, Any]:
    return {
        "markets": [
            {
                "ticker": "KXIRA-45VREPEAL-YES",
                "event_ticker": "KXIRA-45VREPEAL",
                "title": "Will Congress repeal or terminate the 45V clean hydrogen tax credit?",
                "subtitle": "IRA clean energy policy",
                "yes_sub_title": "45V is repealed",
                "no_sub_title": "45V remains in force",
                "status": "active",
                "result": None,
                "yes_bid_dollars": "0.4500",
                "yes_ask_dollars": "0.4900",
                "volume_fp": "1000.00",
                "volume_24h_fp": "100.00",
                "liquidity_dollars": "250.00",
                "open_interest_fp": "1000.00",
                "open_time": "2026-05-01T00:00:00Z",
                "close_time": "2026-12-31T23:59:59Z",
                "latest_expiration_time": "2027-01-15T00:00:00Z",
                "rules_primary": (
                    "This market resolves Yes if a federal law terminates or repeals "
                    "the Section 45V clean hydrogen production credit before expiration."
                ),
                "rules_secondary": "Official federal statute text controls resolution.",
            }
        ]
    }


def _write_fixture_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
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

    market_path = tmp_path / "kalshi_markets.json"
    from pci_realtime.forecast_registry.store import write_json

    write_json(market_path, _market_fixture())
    return raw_root, scored_dir, market_path


def test_weekly_live_rows_materialize_supabase_contract(tmp_path: Path) -> None:
    raw_root, scored_dir, market_path = _write_fixture_inputs(tmp_path)

    rows = build_weekly_live_rows(
        week="2025-W23",
        raw_root=raw_root,
        scored_dir=scored_dir,
        market_fixture_path=market_path,
        run_id=FIXED_RUN_ID,
    )

    assert len(rows["provisions"]) == 6
    assert len(rows["policy_events"]) == 1
    assert len(rows["market_snapshots"]) == 1
    assert len(rows["forecasts"]) == 1
    assert len(rows["trade_proposals"]) == 1
    assert rows["pipeline_runs"][0]["metadata"]["forecasts"] == 1
    assert rows["pipeline_runs"][0]["metadata"]["trade_proposals"] == 1
    assert rows["forecasts"][0]["run_id"] == FIXED_RUN_ID
    assert rows["forecasts"][0]["provision"] == "45V"
    assert rows["trade_proposals"][0]["approval_status"] == "pending_human_approval"
    assert rows["pci_weekly"][0]["week"] == "2022-W33"

    row_45v = [
        row
        for row in rows["pci_weekly"]
        if row["week"] == "2025-W23" and row["provision"] == "45V"
    ][0]
    assert row_45v["data_origin"] == "live_scored"
    assert row_45v["source_event_ids"] == ["2025-W23:federal_register:45v-guidance:45V"]

    payload_text = repr(rows)
    assert "raw_response" not in payload_text
    assert "OPENAI_API_KEY" not in payload_text
    assert "KALSHI_PRIVATE_KEY" not in payload_text


def test_weekly_live_rows_baseline_only_has_no_fake_forecasts(tmp_path: Path) -> None:
    rows = build_weekly_live_rows(
        week="2025-W23",
        raw_root=tmp_path / "raw",
        scored_dir=tmp_path / "scored",
        run_id=FIXED_RUN_ID,
    )

    assert len(rows["provisions"]) == 6
    assert rows["policy_events"] == []
    assert rows["market_snapshots"] == []
    assert rows["forecasts"] == []
    assert rows["trade_proposals"] == []
    assert rows["pipeline_runs"][0]["metadata"]["policy_events"] == 0


def test_weekly_live_can_publish_market_scan_without_fake_forecasts(
    tmp_path: Path,
) -> None:
    market_path = tmp_path / "kalshi_markets.json"
    from pci_realtime.forecast_registry.store import write_json

    write_json(market_path, _market_fixture())

    rows = build_weekly_live_rows(
        week="2025-W23",
        raw_root=tmp_path / "raw",
        scored_dir=tmp_path / "scored",
        market_fixture_path=market_path,
        run_id=FIXED_RUN_ID,
    )

    assert len(rows["market_snapshots"]) == 1
    assert rows["forecasts"] == []
    assert rows["trade_proposals"] == []
    assert rows["pipeline_runs"][0]["metadata"]["signals"] == 0


class RecordingSupabaseClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int, str | None]] = []

    def upsert_rows(
        self,
        table: str,
        rows: list[dict[str, Any]],
        *,
        on_conflict: str | None = None,
    ) -> None:
        self.calls.append(("upsert", table, len(rows), on_conflict))

    def insert_rows(self, table: str, rows: list[dict[str, Any]]) -> None:
        self.calls.append(("insert", table, len(rows), None))


def test_write_supabase_rows_uses_upserts_for_current_state_tables(
    tmp_path: Path,
) -> None:
    raw_root, scored_dir, market_path = _write_fixture_inputs(tmp_path)
    rows = build_weekly_live_rows(
        week="2025-W23",
        raw_root=raw_root,
        scored_dir=scored_dir,
        market_fixture_path=market_path,
        run_id=FIXED_RUN_ID,
    )
    client = RecordingSupabaseClient()

    write_supabase_rows(rows, client=client)  # type: ignore[arg-type]

    assert ("upsert", "provisions", 6, "code") in client.calls
    assert any(
        call == ("upsert", "pci_weekly", len(rows["pci_weekly"]), "provision,week")
        for call in client.calls
    )
    assert ("upsert", "policy_events", 1, "event_id") in client.calls
    assert ("insert", "forecasts", 1, None) in client.calls
    assert ("insert", "trade_proposals", 1, None) in client.calls


def test_weekly_live_dry_run_writes_payload_without_supabase(
    tmp_path: Path,
    monkeypatch,
) -> None:
    raw_root, scored_dir, market_path = _write_fixture_inputs(tmp_path)
    output_path = tmp_path / "weekly_live_payload.json"

    def record_ingest(**_: Any) -> None:
        return None

    def record_score(**_: Any) -> Path:
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
        market_fixture_path=market_path,
        dry_run=True,
        output_path=output_path,
    )

    assert result.counts["forecasts"] == 1
    assert result.counts["trade_proposals"] == 1
    assert output_path.exists()
