from __future__ import annotations

from typing import Any

from pci_realtime.forecast_registry.discovery import (
    MarketScanResult,
    market_candidate_row,
)
from pci_realtime.pipeline.market_discovery import (
    build_market_discovery_rows,
    write_market_discovery_rows,
)


FIXED_RUN_ID = "00000000-0000-0000-0000-000000000001"
FIXED_NOW = "2026-05-26T12:00:00+00:00"


def _policy_market() -> dict[str, Any]:
    return {
        "schema_version": "forecast-registry-v1.0.0",
        "generated_at": FIXED_NOW,
        "venue": "kalshi",
        "query_name": "test",
        "ticker": "KXIRA-45VREPEAL",
        "event_ticker": "KXIRA",
        "title": "Will Congress repeal the 45V clean hydrogen tax credit?",
        "subtitle": "IRA clean energy policy",
        "status": "active",
        "market_probability": 0.45,
        "liquidity_dollars": 250.0,
        "volume": 1000.0,
        "volume_24h": 10.0,
        "resolution_text": (
            "This market resolves Yes if federal law repeals the Section 45V clean hydrogen tax credit."
        ),
        "policy_relevant": True,
        "source": "kalshi_public_market_data",
        "raw_public_metadata": {},
    }


def test_market_discovery_rows_record_candidate_audit(monkeypatch) -> None:
    def fake_kalshi_scan(**kwargs: Any) -> MarketScanResult:
        market = _policy_market()
        candidate = market_candidate_row(
            market,
            run_id=kwargs["run_id"],
            generated_at=FIXED_NOW,
            rank=1,
            query_name="test",
        )
        return MarketScanResult(
            snapshots=[market],
            candidates=[candidate],
            stats={"scanned": 1, "published": 1, "stored_candidates": 1, "requests": 1},
        )

    monkeypatch.setattr(
        "pci_realtime.pipeline.market_discovery.fetch_market_snapshot_scan",
        fake_kalshi_scan,
    )

    rows = build_market_discovery_rows(
        run_id=FIXED_RUN_ID, fetch_kalshi=True, fetch_polymarket=False
    )

    assert rows["pipeline_runs"][0]["run_type"] == "market_discovery"
    assert rows["pipeline_runs"][0]["metadata"]["scan"]["scanned"] == 1
    assert len(rows["market_snapshots"]) == 1
    assert rows["market_discovery_candidates"][0]["eligible_snapshot"] is True
    assert rows["source_health"][0]["source"] == "kalshi"


class RecordingSupabaseClient:
    def __init__(self) -> None:
        self.inserts: list[tuple[str, int]] = []
        self.upserts: list[tuple[str, int, str | None]] = []

    def insert_rows(self, table: str, rows: list[dict[str, Any]]) -> None:
        self.inserts.append((table, len(rows)))

    def upsert_rows(
        self,
        table: str,
        rows: list[dict[str, Any]],
        *,
        on_conflict: str | None = None,
    ) -> None:
        self.upserts.append((table, len(rows), on_conflict))


def test_market_discovery_write_order_keeps_run_before_candidates() -> None:
    market = _policy_market()
    rows = {
        "pipeline_runs": [{"run_id": FIXED_RUN_ID}],
        "market_snapshots": [market],
        "market_discovery_candidates": [
            market_candidate_row(
                market,
                run_id=FIXED_RUN_ID,
                generated_at=FIXED_NOW,
                rank=1,
                query_name="test",
            )
        ],
        "source_documents": [],
        "evidence_items": [],
        "source_links": [],
        "source_health": [],
    }
    client = RecordingSupabaseClient()

    write_market_discovery_rows(rows, client=client)  # type: ignore[arg-type]

    assert client.inserts[0] == ("pipeline_runs", 1)
    assert ("market_discovery_candidates", 1, "candidate_id") in client.upserts
