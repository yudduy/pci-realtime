from __future__ import annotations

from pathlib import Path
from typing import Any

from pci_realtime.forecast_registry.discovery import market_candidate_row
from pci_realtime.forecast_registry.kalshi import fetch_market_snapshot_scan
from pci_realtime.forecast_registry.market_intelligence import (
    HeuristicMarketAssessmentClient,
    StructuredLLMMarketAssessmentClient,
    build_market_assessment_rows,
    eligible_snapshots_from_assessments,
    market_inventory_rows,
)
from pci_realtime.scoring.cache import JsonCache, StructuredLLMResponse


FIXED_RUN_ID = "00000000-0000-0000-0000-000000000001"
FIXED_NOW = "2026-05-26T12:00:00+00:00"


def _direct_market() -> dict[str, Any]:
    return {
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
        "resolution_text": (
            "This market resolves Yes if federal law repeals the Section 45V clean hydrogen tax credit."
        ),
        "raw_public_metadata": {},
    }


def _proxy_market() -> dict[str, Any]:
    return {
        "venue": "polymarket",
        "query_name": "test",
        "ticker": "tesla-robovan-orders",
        "title": "Will Tesla open orders for the Robovan before 2027?",
        "subtitle": "Electric vehicle demand",
        "status": "active",
        "market_probability": 0.55,
        "liquidity_dollars": 500.0,
        "volume": 1000.0,
        "resolution_text": "Resolves Yes if Tesla opens Robovan orders before 2027.",
        "raw_public_metadata": {"search_provisions": ["30D"]},
    }


def test_heuristic_assessment_keeps_proxy_out_of_forecasts() -> None:
    market = _proxy_market()
    rows, stats = build_market_assessment_rows(
        markets=[market],
        candidates=[],
        run_id=FIXED_RUN_ID,
        generated_at=FIXED_NOW,
        client=HeuristicMarketAssessmentClient(),
    )

    assert stats["targets"] == 1
    assert rows[0]["provision"] == "30D"
    assert rows[0]["relevance_class"] == "sector_proxy"
    assert rows[0]["eligible_for_forecast"] is False
    assert eligible_snapshots_from_assessments([market], rows) == []


def test_direct_assessment_projects_to_strict_snapshot() -> None:
    market = _direct_market()
    candidate = market_candidate_row(
        market,
        run_id=FIXED_RUN_ID,
        generated_at=FIXED_NOW,
        rank=1,
        query_name="test",
    )
    rows, stats = build_market_assessment_rows(
        markets=[market],
        candidates=[candidate],
        run_id=FIXED_RUN_ID,
        generated_at=FIXED_NOW,
        client=HeuristicMarketAssessmentClient(),
    )
    snapshots = eligible_snapshots_from_assessments([market], rows)

    assert stats["eligible_for_forecast"] == 1
    assert snapshots[0]["policy_relevant"] is True
    assert snapshots[0]["query_name"] == "assessment:45V"
    assert snapshots[0]["raw_public_metadata"]["assessment"]["provision"] == "45V"


class FakeStructuredClient:
    provider = "openai"

    def __init__(self) -> None:
        self.calls = 0

    def create_json(self, **_: Any) -> StructuredLLMResponse:
        self.calls += 1
        return StructuredLLMResponse(
            payload={
                "assessments": [
                    {
                        "provision": "45V",
                        "relevance_class": "direct_policy",
                        "resolution_fit": "clear",
                        "orientation": "repeal_risk",
                        "confidence": 0.82,
                        "evidence_span": "45V repeal market",
                        "rationale": "Directly resolves a 45V repeal question.",
                        "eligible_for_forecast": True,
                    }
                ]
            },
            raw_response="{}",
            usage={},
            cost_usd=0.0,
        )


def test_structured_assessor_uses_cache(tmp_path: Path) -> None:
    fake = FakeStructuredClient()
    assessor = StructuredLLMMarketAssessmentClient(
        client=fake,
        model="test-model",
        provider="openai",
        cache=JsonCache(tmp_path),
    )
    market = _direct_market()

    first = assessor.assess(market=market, provision="45V", recall_reasons=["test"])
    second = assessor.assess(market=market, provision="45V", recall_reasons=["test"])

    assert first["eligible_for_forecast"] is True
    assert second["cached"] is True
    assert fake.calls == 1


class FakeKalshiClient:
    def __init__(self, **_: Any) -> None:
        self.request_count = 0
        self.rate_limited_count = 0
        self.retry_count = 0
        self.orderbook_calls: list[str] = []

    def get_markets(self, **_: Any) -> list[dict[str, Any]]:
        return [
            {
                "ticker": "KXSPORTS",
                "title": "Will a basketball team win?",
                "status": "active",
                "rules_primary": "Resolves on official league score.",
            },
            {
                "ticker": "KXIRA-45V",
                "event_ticker": "KXIRA",
                "title": "Will Congress repeal the 45V clean hydrogen tax credit?",
                "subtitle": "IRA tax credit",
                "status": "active",
                "rules_primary": (
                    "This market resolves Yes if federal law repeals Section 45V."
                ),
            },
        ]

    def get_orderbook(self, ticker: str, *, depth: int = 1) -> dict[str, Any]:
        del depth
        self.orderbook_calls.append(ticker)
        return {"orderbook_fp": {"yes_dollars": [["0.45", "10"]]}}

    def close(self) -> None:
        return None


def test_kalshi_scan_fetches_orderbooks_only_for_query_hits(
    monkeypatch, tmp_path: Path
) -> None:
    query_file = tmp_path / "queries.yml"
    query_file.write_text(
        "queries:\n"
        "  - name: test\n"
        "    status: open\n"
        "    limit: 10\n"
        "    keywords:\n"
        "      - 45V\n"
        "      - clean hydrogen\n",
        encoding="utf-8",
    )
    instances: list[FakeKalshiClient] = []

    def fake_client(**kwargs: Any) -> FakeKalshiClient:
        client = FakeKalshiClient(**kwargs)
        instances.append(client)
        return client

    monkeypatch.setattr(
        "pci_realtime.forecast_registry.kalshi.KalshiClient", fake_client
    )

    result = fetch_market_snapshot_scan(query_file=query_file)

    assert len(result.inventory) == 2
    assert len(result.candidates) == 1
    assert instances[0].orderbook_calls == ["KXIRA-45V"]


def test_market_inventory_rows_are_current_state_rows() -> None:
    rows = market_inventory_rows(
        [_direct_market()], run_id=FIXED_RUN_ID, generated_at=FIXED_NOW
    )

    assert rows[0]["venue"] == "kalshi"
    assert rows[0]["ticker"] == "KXIRA-45VREPEAL"
    assert rows[0]["latest_run_id"] == FIXED_RUN_ID
    assert rows[0]["source_payload_hash"]
