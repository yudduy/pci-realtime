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
        if table == "forecast_outcomes":
            assert "settlement_value" in columns
            return []
        assert table == "forecasts"
        assert "pci_rule_probability" in columns
        assert params == {"private_info_used": "eq.false"}
        return [
            {
                "forecast_id": "forecast:45v:KX45V-SETTLE",
                "venue": "kalshi",
                "market_ticker": "KX45V-SETTLE",
                "market_probability": 0.55,
                "pci_rule_probability": 0.62,
                "model_probability": 0.68,
            }
        ]

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


def test_daily_refresh_reads_supabase_and_writes_outcomes() -> None:
    client = RecordingSupabaseClient()

    def fetch_markets(forecasts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        assert forecasts[0]["market_ticker"] == "KX45V-SETTLE"
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
    )

    assert counts == {
        "pipeline_runs": 1,
        "market_snapshots": 1,
        "forecast_outcomes": 1,
    }
    assert client.inserts[0][0] == "pipeline_runs"
    assert client.inserts[1][0] == "market_snapshots"
    assert client.upserts[0][0] == "forecast_outcomes"
    assert client.upserts[0][2] == "outcome_id"
    assert client.upserts[0][1][0]["settlement_value"] == 1.0
