from __future__ import annotations

from pathlib import Path

import pytest

from pci_realtime.forecast_registry.engine import (
    RiskLimits,
    RiskState,
    build_abstentions,
    build_forecasts,
    build_trade_proposal,
    build_trade_proposals,
    build_outcomes,
    compute_forecast_metrics,
    generate_signals,
    match_signals_to_markets,
)
from pci_realtime.forecast_registry.kalshi import (
    ExecutionGateError,
    create_signed_order_request,
    parse_market_snapshot,
    read_jsonl,
    snapshots_from_fixture,
)
from pci_realtime.forecast_registry.store import (
    forecast_to_row,
    write_json,
    write_jsonl,
)


FIXED_NOW = "2026-05-21T12:00:00+00:00"


def _policy_event(provision: str = "45V", delta: float = -2.0) -> dict:
    return {
        "event_id": "2025-W23:federal_register:hydrogen:45V",
        "week": "2025-W23",
        "week_start": "2025-06-02",
        "doc_id": "federal_register:hydrogen",
        "provision": provision,
        "provision_name": "Clean Hydrogen Production Credit",
        "pci_delta": delta,
        "dimension_deltas": {
            "specificity": delta,
            "durability": 0.0,
            "enforceability": 0.0,
        },
        "rationale": "Treasury guidance sharply narrows clean hydrogen 45V eligibility.",
        "confidence": 0.9,
        "source_document": {
            "doc_id": "federal_register:hydrogen",
            "source": "federal_register",
            "agency": "Treasury Department",
            "title": "Clean Hydrogen Production Credit Guidance",
            "url": "https://example.gov/45v",
        },
    }


def _kalshi_market(
    *,
    ticker: str = "KXIRA-45VREPEAL-YES",
    title: str = "Will Congress repeal or terminate the 45V clean hydrogen tax credit?",
    yes_bid: str = "0.4500",
    yes_ask: str = "0.4900",
    liquidity: str = "250.00",
    status: str = "active",
    result: str | None = None,
) -> dict:
    return {
        "ticker": ticker,
        "event_ticker": "KXIRA-45VREPEAL",
        "title": title,
        "subtitle": "IRA clean energy policy",
        "yes_sub_title": "45V is repealed",
        "no_sub_title": "45V remains in force",
        "status": status,
        "result": result,
        "yes_bid_dollars": yes_bid,
        "yes_ask_dollars": yes_ask,
        "volume_fp": "1000.00",
        "volume_24h_fp": "100.00",
        "liquidity_dollars": liquidity,
        "open_interest_fp": "1000.00",
        "open_time": "2026-05-01T00:00:00Z",
        "close_time": "2026-12-31T23:59:59Z",
        "latest_expiration_time": "2027-01-15T00:00:00Z",
        "settlement_ts": "2027-01-02T00:00:00Z" if result else None,
        "rules_primary": (
            "This market resolves Yes if a federal law terminates or repeals "
            "the Section 45V clean hydrogen production credit before expiration."
        ),
        "rules_secondary": "Official federal statute text controls resolution.",
    }


def _forecast_rows() -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    signals = generate_signals([_policy_event(delta=-2.0)], generated_at=FIXED_NOW)
    markets = [parse_market_snapshot(_kalshi_market(), generated_at=FIXED_NOW)]
    matches = match_signals_to_markets(signals, markets)
    forecasts = build_forecasts(
        signals=signals,
        markets=markets,
        matches=matches,
        generated_at=FIXED_NOW,
    )
    return signals, markets, matches, forecasts


def test_signal_generation_from_policy_events() -> None:
    signals = generate_signals([_policy_event()], generated_at=FIXED_NOW)

    assert len(signals) == 1
    signal = signals[0]
    assert signal["provision"] == "45V"
    assert signal["dimension"] == "specificity"
    assert signal["shock_direction"] == "credibility_down"
    assert signal["shock_type"] == "negative_credibility_shock"
    assert signal["private_info_used"] is False
    assert "Hydrogen" in signal["exposure_channels"]


def test_kalshi_adapter_parses_market_fixture_orderbook_and_result() -> None:
    market = _kalshi_market(yes_bid="", yes_ask="", status="finalized", result="yes")
    orderbook = {
        "orderbook_fp": {
            "yes_dollars": [["0.4200", "50.00"], ["0.4400", "10.00"]],
            "no_dollars": [["0.5200", "20.00"]],
        }
    }

    snapshot = parse_market_snapshot(
        market,
        query_name="fixture",
        orderbook=orderbook,
        generated_at=FIXED_NOW,
    )

    assert snapshot["venue"] == "kalshi"
    assert snapshot["yes_bid"] == 0.44
    assert snapshot["yes_ask"] == pytest.approx(0.48)
    assert snapshot["bid_ask_spread"] == pytest.approx(0.04)
    assert snapshot["market_probability"] == pytest.approx(0.46)
    assert snapshot["policy_relevant"] is True
    assert snapshot["result"] == "yes"
    assert snapshot["latest_expiration_time"] == "2027-01-15T00:00:00Z"


def test_market_snapshot_publication_filters_non_policy_noise(tmp_path: Path) -> None:
    market_path = tmp_path / "markets.json"
    noisy_market = _kalshi_market(
        ticker="KXSPORTS-ENERGY-YES",
        title="Will a high-energy basketball team win tonight?",
    )
    noisy_market["event_ticker"] = "KXSPORTS"
    noisy_market["subtitle"] = "sports market"
    noisy_market["yes_sub_title"] = "team wins"
    noisy_market["no_sub_title"] = "team loses"
    noisy_market["rules_primary"] = (
        "This market resolves Yes if the listed basketball team wins tonight."
    )
    noisy_market["rules_secondary"] = "Official league score controls resolution."
    write_json(market_path, {"markets": [noisy_market, _kalshi_market()]})

    snapshots = snapshots_from_fixture(market_path, generated_at=FIXED_NOW)

    assert [snapshot["ticker"] for snapshot in snapshots] == ["KXIRA-45VREPEAL-YES"]


def test_market_matching_links_pci_signal_to_policy_market() -> None:
    signals, markets, matches, _ = _forecast_rows()

    assert len(matches) == 1
    assert matches[0]["signal_id"] == signals[0]["signal_id"]
    assert matches[0]["market_ticker"] == markets[0]["ticker"]
    assert matches[0]["policy_relevant"] is True
    assert matches[0]["resolution_clear"] is True
    assert matches[0]["market_orientation"] == "adverse_policy_change"


def test_forecast_ensemble_bounds_and_builds_immutable_ledger_payload() -> None:
    _, _, _, forecasts = _forecast_rows()

    assert len(forecasts) == 1
    forecast = forecasts[0]
    assert 0.01 <= forecast["model_probability"] <= 0.99
    assert forecast["edge"] >= 0.08
    assert forecast["private_info_used"] is False

    forecast_row = forecast_to_row(forecast)
    assert forecast_row["forecast_id"] == forecast["forecast_id"]
    assert forecast_row["provision"] == "45V"
    assert forecast_row["private_info_used"] is False


def test_abstention_logged_when_signal_has_no_eligible_market() -> None:
    signals = generate_signals([_policy_event(delta=-1.0)], generated_at=FIXED_NOW)
    abstentions = build_abstentions(signals=signals, matches=[], generated_at=FIXED_NOW)

    assert len(abstentions) == 1
    assert abstentions[0]["reason"] == "no_eligible_market_mapping"
    assert abstentions[0]["provision"] == "45V"


def test_settlement_and_metrics_from_finalized_kalshi_fixture() -> None:
    _, _, _, forecasts = _forecast_rows()
    settled_market = parse_market_snapshot(
        _kalshi_market(status="finalized", result="yes"),
        generated_at=FIXED_NOW,
    )
    outcomes = build_outcomes(
        forecasts=forecasts, markets=[settled_market], generated_at=FIXED_NOW
    )
    metrics = compute_forecast_metrics(
        forecasts=forecasts,
        outcomes=outcomes,
        abstentions=[],
        generated_at=FIXED_NOW,
    )

    assert outcomes[0]["settlement_value"] == 1.0
    assert metrics["settled_forecast_count"] == 1
    assert metrics["model"]["brier_score"] is not None
    assert metrics["baselines"]["market_prior"]["log_loss"] is not None
    assert metrics["calibration_ready"] is True


def test_private_risk_and_execution_remain_internal_gated() -> None:
    _, _, _, forecasts = _forecast_rows()
    proposal = build_trade_proposal(forecasts[0])

    assert proposal["approval_status"] == "pending_human_approval"
    assert proposal["estimated_exposure_usd"] <= 10.01

    approval = {"approved_proposal_ids": [proposal["proposal_id"]]}
    with pytest.raises(ExecutionGateError, match="PCI_ENABLE_LIVE_TRADING"):
        create_signed_order_request(
            proposal,
            approval_payload=approval,
            credentials=None,
            enable_live_trading=False,
        )


def test_private_risk_engine_rejects_bad_trade_inputs() -> None:
    forecast = {
        "schema_version": "forecast-registry-v1.0.0",
        "generated_at": FIXED_NOW,
        "forecast_id": "forecast:test",
        "venue": "kalshi",
        "market_ticker": "KXTEST",
        "edge": 0.09,
        "confidence": 0.4,
        "private_info_used": False,
        "market_snapshot": {
            "ticker": "KXTEST",
            "yes_bid": 0.2,
            "yes_ask": 0.4,
            "bid_ask_spread": 0.2,
            "liquidity_dollars": 20.0,
        },
        "match": {"policy_relevant": True, "resolution_clear": True},
    }

    proposal = build_trade_proposal(forecast)

    assert proposal["risk_passed"] is False
    assert {"spread", "liquidity", "confidence"} <= set(proposal["rejection_reasons"])

    passing_forecast = {
        **forecast,
        "confidence": 0.8,
        "market_snapshot": {
            **forecast["market_snapshot"],
            "yes_bid": 0.45,
            "yes_ask": 0.49,
            "bid_ask_spread": 0.04,
            "liquidity_dollars": 250.0,
        },
    }
    state = RiskState(total_exposure_usd=249.0)
    limited = build_trade_proposal(
        passing_forecast,
        limits=RiskLimits(max_total_exposure_usd=250.0),
        state=state,
    )
    assert limited["risk_passed"] is False
    assert "total_exposure" in limited["rejection_reasons"]


def test_private_risk_engine_accumulates_batch_exposure() -> None:
    _, _, _, forecasts = _forecast_rows()
    batch = [
        {**forecasts[0], "forecast_id": f"forecast:test:{index}"} for index in range(6)
    ]

    proposals = build_trade_proposals(
        batch,
        limits=RiskLimits(max_market_exposure_usd=50.0),
        include_rejected=True,
    )

    assert sum(1 for proposal in proposals if proposal["risk_passed"]) == 5
    assert proposals[-1]["risk_passed"] is False
    assert "market_exposure" in proposals[-1]["rejection_reasons"]


def test_end_to_end_debug_artifacts_contain_no_private_fields(
    tmp_path: Path,
) -> None:
    debug_dir = tmp_path / "debug"
    debug_dir.mkdir()
    signals, markets, matches, forecasts = _forecast_rows()
    abstentions = build_abstentions(signals=signals, matches=matches)
    outcomes = build_outcomes(forecasts=forecasts, markets=[])
    metrics = compute_forecast_metrics(
        forecasts=forecasts, outcomes=outcomes, abstentions=abstentions
    )

    write_jsonl(debug_dir / "signals.jsonl", signals)
    write_jsonl(debug_dir / "market_snapshots.jsonl", markets)
    write_jsonl(debug_dir / "matches.jsonl", matches)
    write_jsonl(debug_dir / "forecasts.jsonl", forecasts)
    write_jsonl(debug_dir / "abstentions.jsonl", abstentions)

    assert read_jsonl(debug_dir / "signals.jsonl")[0]["provision"] == "45V"
    assert read_jsonl(debug_dir / "forecasts.jsonl")[0]["edge"] >= 0.08
    assert metrics["forecast_count"] == 1
    for path in debug_dir.iterdir():
        text = path.read_text(encoding="utf-8")
        assert "raw_response" not in text
        assert "Company ID" not in text
        assert "OPENAI_API_KEY" not in text
        assert "trade_proposals" not in text
