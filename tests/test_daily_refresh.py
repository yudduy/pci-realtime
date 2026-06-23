from __future__ import annotations

from typing import Any

from pci_realtime.pipeline.daily_refresh import run_daily_refresh


class RecordingSupabaseClient:
    def __init__(self) -> None:
        self.inserts: list[tuple[str, list[dict[str, Any]]]] = []
        self.upserts: list[tuple[str, list[dict[str, Any]], str | None]] = []

    def select_rows(
        self,
        table: str,
        *,
        columns: str = "*",
        params: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        raise AssertionError(f"daily_refresh should not read {table}")

    def insert_rows(self, table: str, rows: list[dict[str, Any]]) -> None:
        self.inserts.append((table, rows))

    def upsert_rows(
        self,
        table: str,
        rows: list[dict[str, Any]],
        *,
        on_conflict: str | None = None,
    ) -> None:
        self.upserts.append((table, rows, on_conflict))


def test_daily_refresh_writes_context_without_forecast_outcomes() -> None:
    client = RecordingSupabaseClient()

    def fetch_markets() -> list[dict[str, Any]]:
        return [
            {
                "generated_at": "2026-05-25T14:00:00Z",
                "venue": "kalshi",
                "ticker": "KX45V-SETTLE",
                "event_ticker": "KX45V",
                "title": "Will section 45V be changed?",
                "status": "settled",
                "result": "yes",
                "market_probability": 0.99,
                "liquidity_dollars": 500.0,
                "volume": 1000.0,
                "volume_24h": 100.0,
                "open_interest": 200.0,
                "settlement_ts": "2026-05-25T13:00:00Z",
                "resolution_text": "Official market result.",
                "policy_relevant": True,
            }
        ]

    counts = run_daily_refresh(
        supabase=True,
        client=client,  # type: ignore[arg-type]
        market_fetcher=fetch_markets,
        context_fetcher=lambda: {
            "source_documents": [],
            "evidence_items": [],
            "source_links": [],
            "source_health": [],
        },
    )

    assert counts == {
        "pipeline_runs": 1,
        "market_snapshots": 1,
        "source_health": 1,
        "source_documents": 0,
        "evidence_items": 0,
        "source_links": 0,
    }
    assert client.inserts[0][0] == "pipeline_runs"
    assert client.inserts[1][0] == "market_snapshots"
    assert [table for table, *_ in client.upserts] == [
        "source_health",
        "source_documents",
        "evidence_items",
        "source_links",
    ]
