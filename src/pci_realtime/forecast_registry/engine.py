from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from pci_realtime.config import (
    LLM_AUDIT_MODEL,
    LLM_AUDIT_PROVIDER,
    TRACKED_PROVISIONS,
)
from pci_realtime.forecast_registry.policy import (
    FORECAST_REGISTRY_METHOD_VERSION,
    PROVISION_EXPOSURES,
    infer_policy_orientation,
    is_policy_relevant_text,
    text_contains_keyword,
)
from pci_realtime.scoring.screener import StructuredOutputClient


FORECAST_SCHEMA_VERSION = "forecast-registry-v1.0.0"
ENSEMBLE_WEIGHTS = {"market_prior": 0.60, "pci_rule": 0.25, "llm_forecast": 0.15}
FORECAST_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "probability": {"type": "number", "minimum": 0.01, "maximum": 0.99},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "causal_chain": {"type": "string"},
        "counterarguments": {"type": "string"},
        "resolution_risk_notes": {"type": "string"},
        "private_info_used": {"type": "boolean"},
    },
    "required": [
        "probability",
        "confidence",
        "causal_chain",
        "counterarguments",
        "resolution_risk_notes",
        "private_info_used",
    ],
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clamp_probability(value: float) -> float:
    return min(0.99, max(0.01, float(value)))


def _dimension_from_event(event: dict[str, Any]) -> str:
    deltas = event.get("dimension_deltas") or {}
    if not deltas:
        return "composite"
    return max(deltas, key=lambda key: abs(float(deltas[key] or 0.0)))


def _shock_direction(delta: float) -> str:
    if delta > 0:
        return "credibility_up"
    if delta < 0:
        return "credibility_down"
    return "credibility_neutral"


def _shock_type(event: dict[str, Any], pci_delta: float) -> str:
    source = event.get("source_document") or {}
    text = " ".join(
        str(part or "")
        for part in [event.get("rationale"), source.get("title"), source.get("agency")]
    ).lower()
    if "obbba" in text or "one big beautiful bill" in text:
        return "obbba_style_shock"
    if pci_delta <= -0.5:
        return "negative_credibility_shock"
    if pci_delta >= 0.5:
        return "positive_credibility_shock"
    return "incremental_credibility_update"


def event_to_signal(
    event: dict[str, Any], *, generated_at: str | None = None
) -> dict[str, Any] | None:
    provision = str(event.get("provision", ""))
    if provision not in TRACKED_PROVISIONS:
        return None

    pci_delta = float(event.get("pci_delta") or 0.0)
    exposure = PROVISION_EXPOSURES[provision]
    source_document = event.get("source_document") or {}
    event_id = str(event.get("event_id") or "")
    signal_id = (
        f"{event_id}:pci_signal"
        if event_id
        else f"{event.get('week')}:{provision}:pci_signal"
    )
    return {
        "schema_version": FORECAST_SCHEMA_VERSION,
        "generated_at": generated_at or utc_now_iso(),
        "signal_id": signal_id,
        "source_event_id": event_id,
        "week": str(event.get("week", "")),
        "week_start": event.get("week_start"),
        "provision": provision,
        "provision_name": event.get("provision_name"),
        "dimension": _dimension_from_event(event),
        "delta": pci_delta,
        "shock_direction": _shock_direction(pci_delta),
        "shock_type": _shock_type(event, pci_delta),
        "confidence": float(event.get("confidence") or 0.65),
        "source_doc": {
            "doc_id": source_document.get("doc_id") or event.get("doc_id"),
            "source": source_document.get("source"),
            "agency": source_document.get("agency"),
            "title": source_document.get("title"),
            "url": source_document.get("url"),
        },
        "evidence": str(event.get("rationale") or ""),
        "exposure_channels": list(exposure.sectors),
        "paper_exposure_channel": exposure.exposure_channel,
        "paper_evidence": exposure.paper_evidence,
        "private_info_used": False,
        "method_version": FORECAST_REGISTRY_METHOD_VERSION,
        "data_origin": "official_policy_pipeline",
    }


def generate_signals(
    policy_events: list[dict[str, Any]], *, generated_at: str | None = None
) -> list[dict[str, Any]]:
    signals = [
        signal
        for event in policy_events
        if (signal := event_to_signal(event, generated_at=generated_at)) is not None
    ]
    return sorted(
        signals, key=lambda row: (row["week"], row["provision"], row["signal_id"])
    )


def _market_text(market: dict[str, Any]) -> str:
    return " ".join(
        str(market.get(key) or "")
        for key in [
            "ticker",
            "event_ticker",
            "title",
            "subtitle",
            "yes_sub_title",
            "no_sub_title",
            "rules_primary",
            "rules_secondary",
            "resolution_text",
        ]
    ).lower()


def _resolution_clear(market: dict[str, Any]) -> bool:
    text = _market_text(market)
    rules = str(market.get("resolution_text") or market.get("rules_primary") or "")
    if len(rules.strip()) < 20:
        return False
    return not any(term in text for term in ("subjective", "unclear", "ambiguous"))


def score_signal_market_match(
    signal: dict[str, Any], market: dict[str, Any]
) -> tuple[float, list[str]]:
    provision = str(signal.get("provision") or "")
    exposure = PROVISION_EXPOSURES.get(provision)
    keywords = tuple(exposure.market_keywords if exposure else ())
    text = _market_text(market)
    matched_terms = sorted(
        {keyword for keyword in keywords if text_contains_keyword(text, keyword)}
    )

    policy_bonus = 0.12 if is_policy_relevant_text(text) else 0.0
    provision_bonus = 0.18 if provision.lower() in text else 0.0
    overlap_score = min(0.45, 0.09 * len(matched_terms))
    channel_bonus = sum(
        0.05
        for channel in signal.get("exposure_channels", [])
        if text_contains_keyword(text, str(channel))
    )
    confidence = min(
        0.95, 0.25 + overlap_score + policy_bonus + provision_bonus + channel_bonus
    )
    return round(confidence, 4), matched_terms


def match_signals_to_markets(
    signals: list[dict[str, Any]],
    markets: list[dict[str, Any]],
    *,
    min_confidence: float = 0.35,
    generated_at: str | None = None,
) -> list[dict[str, Any]]:
    generated = generated_at or utc_now_iso()
    matches: list[dict[str, Any]] = []
    for signal in signals:
        for market in markets:
            confidence, matched_terms = score_signal_market_match(signal, market)
            if confidence < min_confidence:
                continue
            ticker = str(market.get("ticker") or "")
            signal_id = str(signal.get("signal_id") or "")
            match_id = f"{signal_id}:{ticker}"
            orientation = infer_policy_orientation(_market_text(market))
            matches.append(
                {
                    "schema_version": FORECAST_SCHEMA_VERSION,
                    "generated_at": generated,
                    "match_id": match_id,
                    "signal_id": signal_id,
                    "market_ticker": ticker,
                    "venue": str(market.get("venue") or "kalshi"),
                    "confidence": confidence,
                    "matched_terms": matched_terms,
                    "policy_relevant": bool(market.get("policy_relevant"))
                    or is_policy_relevant_text(_market_text(market)),
                    "resolution_clear": _resolution_clear(market),
                    "market_orientation": orientation,
                    "semantic_score": round(math.sqrt(confidence), 4),
                    "match_rationale": (
                        f"Matched {signal.get('provision')} signal to {ticker} "
                        f"through terms: {', '.join(matched_terms) or 'policy text'}."
                    ),
                    "method_version": FORECAST_REGISTRY_METHOD_VERSION,
                }
            )
    return sorted(
        matches,
        key=lambda row: (
            -float(row["confidence"]),
            row["signal_id"],
            row["market_ticker"],
        ),
    )


class ForecastClient(Protocol):
    provider: str
    model: str

    def forecast(
        self,
        *,
        signal: dict[str, Any],
        market: dict[str, Any],
        match: dict[str, Any],
        market_probability: float,
        rule_probability: float,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class HeuristicForecastClient:
    provider: str = "offline"
    model: str = "paper_grounded_heuristic_v1"

    def forecast(
        self,
        *,
        signal: dict[str, Any],
        market: dict[str, Any],
        match: dict[str, Any],
        market_probability: float,
        rule_probability: float,
    ) -> dict[str, Any]:
        probability = clamp_probability((market_probability + rule_probability) / 2.0)
        return {
            "probability": probability,
            "confidence": min(0.85, 0.5 + 0.25 * float(match.get("confidence") or 0.0)),
            "causal_chain": (
                f"{signal.get('provision')} {signal.get('shock_direction')} signal "
                "changes credibility; paper evidence links IRA credibility exposure "
                "to financing and policy-sensitive outcomes."
            ),
            "counterarguments": (
                "The market may already price the policy document, and resolution wording may not map cleanly to PCI."
            ),
            "resolution_risk_notes": (
                "Use only if the market resolution criteria directly cover the official policy channel."
            ),
            "private_info_used": False,
        }


@dataclass(frozen=True)
class StructuredLLMForecastClient:
    client: StructuredOutputClient
    model: str = LLM_AUDIT_MODEL
    provider: str = LLM_AUDIT_PROVIDER

    def forecast(
        self,
        *,
        signal: dict[str, Any],
        market: dict[str, Any],
        match: dict[str, Any],
        market_probability: float,
        rule_probability: float,
    ) -> dict[str, Any]:
        payload = {
            "signal": signal,
            "market": {
                "ticker": market.get("ticker"),
                "title": market.get("title"),
                "rules_primary": market.get("rules_primary"),
                "rules_secondary": market.get("rules_secondary"),
                "market_probability": market_probability,
            },
            "match": match,
            "rule_probability": rule_probability,
            "instruction": (
                "Return a calibrated probability that the YES side resolves true. "
                "Use only public evidence and be conservative about ambiguous wording."
            ),
        }
        response = self.client.create_json(
            model=self.model,
            system_prompt=(
                "You are a cautious prediction-market analyst. You may use only public policy evidence. "
                "Never infer from private financing data."
            ),
            user_prompt=json.dumps(payload, sort_keys=True),
            json_schema=FORECAST_JSON_SCHEMA,
            schema_name="policy_market_forecast",
            temperature=0.2,
        )
        return dict(response.payload)


def _market_by_ticker(markets: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(market.get("ticker") or ""): market for market in markets}


def _signal_by_id(signals: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(signal.get("signal_id") or ""): signal for signal in signals}


def pci_rule_probability(
    *, signal: dict[str, Any], market: dict[str, Any], match: dict[str, Any]
) -> float:
    market_probability = float(market.get("market_probability") or 0.5)
    delta = float(signal.get("delta") or 0.0)
    orientation = str(
        match.get("market_orientation") or ""
    ) or infer_policy_orientation(str(market.get("title") or ""))
    magnitude = min(0.25, abs(delta) * 0.14)
    if orientation == "adverse_policy_change":
        signed_adjustment = magnitude if delta < 0 else -magnitude
    elif orientation == "supportive_policy_continuity":
        signed_adjustment = -magnitude if delta < 0 else magnitude
    else:
        signed_adjustment = 0.0
    return clamp_probability(market_probability + signed_adjustment)


def _forecast_confidence(
    signal: dict[str, Any],
    match: dict[str, Any],
    llm_payload: dict[str, Any],
    market: dict[str, Any],
) -> float:
    spread = market.get("bid_ask_spread")
    spread_penalty = (
        0.15 if spread is None else min(0.25, max(0.0, float(spread) - 0.03))
    )
    confidence = (
        0.35 * float(signal.get("confidence") or 0.65)
        + 0.35 * float(match.get("confidence") or 0.0)
        + 0.30 * float(llm_payload.get("confidence") or 0.5)
        - spread_penalty
    )
    return round(max(0.0, min(0.99, confidence)), 4)


def build_forecasts(
    *,
    signals: list[dict[str, Any]],
    markets: list[dict[str, Any]],
    matches: list[dict[str, Any]],
    client: ForecastClient | None = None,
    generated_at: str | None = None,
) -> list[dict[str, Any]]:
    generated = generated_at or utc_now_iso()
    client = client or HeuristicForecastClient()
    signals_by_id = _signal_by_id(signals)
    markets_by_ticker = _market_by_ticker(markets)
    forecasts: list[dict[str, Any]] = []
    for match in matches:
        signal = signals_by_id.get(str(match.get("signal_id") or ""))
        market = markets_by_ticker.get(str(match.get("market_ticker") or ""))
        if signal is None or market is None:
            continue
        market_probability = clamp_probability(
            float(market.get("market_probability") or 0.5)
        )
        rule_probability = pci_rule_probability(
            signal=signal, market=market, match=match
        )
        llm_payload = client.forecast(
            signal=signal,
            market=market,
            match=match,
            market_probability=market_probability,
            rule_probability=rule_probability,
        )
        llm_probability = clamp_probability(
            float(llm_payload.get("probability") or rule_probability)
        )
        model_probability = clamp_probability(
            ENSEMBLE_WEIGHTS["market_prior"] * market_probability
            + ENSEMBLE_WEIGHTS["pci_rule"] * rule_probability
            + ENSEMBLE_WEIGHTS["llm_forecast"] * llm_probability
        )
        edge = round(model_probability - market_probability, 4)
        forecast_id = f"forecast:{match.get('match_id')}"
        forecasts.append(
            {
                "schema_version": FORECAST_SCHEMA_VERSION,
                "generated_at": generated,
                "forecast_id": forecast_id,
                "signal_id": signal.get("signal_id"),
                "match_id": match.get("match_id"),
                "venue": market.get("venue", "kalshi"),
                "market_ticker": market.get("ticker"),
                "market_probability": round(market_probability, 4),
                "rule_probability": round(rule_probability, 4),
                "llm_probability": round(llm_probability, 4),
                "model_probability": round(model_probability, 4),
                "edge": edge,
                "confidence": _forecast_confidence(signal, match, llm_payload, market),
                "ensemble_weights": ENSEMBLE_WEIGHTS,
                "signal": signal,
                "match": match,
                "market_snapshot": market,
                "evidence": {
                    "paper_exposure_channel": signal.get("paper_exposure_channel"),
                    "paper_evidence": signal.get("paper_evidence"),
                    "source_evidence": signal.get("evidence"),
                },
                "forecast_rationale": {
                    "provider": client.provider,
                    "model": client.model,
                    "causal_chain": llm_payload.get("causal_chain"),
                    "counterarguments": llm_payload.get("counterarguments"),
                    "resolution_risk_notes": llm_payload.get("resolution_risk_notes"),
                },
                "private_info_used": bool(llm_payload.get("private_info_used")),
                "calibration_metadata": {
                    "version": "hybrid_market_pci_llm_v1",
                    "market_weight": ENSEMBLE_WEIGHTS["market_prior"],
                    "pci_rule_weight": ENSEMBLE_WEIGHTS["pci_rule"],
                    "llm_weight": ENSEMBLE_WEIGHTS["llm_forecast"],
                    "paper_grounded": True,
                },
            }
        )
    return sorted(
        forecasts, key=lambda row: (-abs(float(row["edge"])), row["forecast_id"])
    )


def build_abstentions(
    *,
    signals: list[dict[str, Any]],
    matches: list[dict[str, Any]],
    generated_at: str | None = None,
) -> list[dict[str, Any]]:
    matched_signal_ids = {str(match.get("signal_id") or "") for match in matches}
    rows = []
    for signal in signals:
        signal_id = str(signal.get("signal_id") or "")
        if signal_id in matched_signal_ids:
            continue
        rows.append(
            {
                "schema_version": FORECAST_SCHEMA_VERSION,
                "generated_at": generated_at or utc_now_iso(),
                "abstention_id": f"abstention:{signal_id}",
                "signal_id": signal_id,
                "week": signal.get("week"),
                "provision": signal.get("provision"),
                "dimension": signal.get("dimension"),
                "delta": signal.get("delta"),
                "reason": "no_eligible_market_mapping",
                "public_info_only": not bool(signal.get("private_info_used")),
                "source_doc": signal.get("source_doc") or {},
            }
        )
    return rows


def build_outcomes(
    *,
    forecasts: list[dict[str, Any]],
    markets: list[dict[str, Any]],
    generated_at: str | None = None,
) -> list[dict[str, Any]]:
    market_by_ticker = _market_by_ticker(markets)
    rows: list[dict[str, Any]] = []
    for forecast in forecasts:
        ticker = str(forecast.get("market_ticker") or "")
        market = market_by_ticker.get(ticker) or forecast.get("market_snapshot") or {}
        result = str(market.get("result") or "").lower()
        status = str(market.get("status") or "").lower()
        if result not in {"yes", "no"} or status not in {"finalized", "settled"}:
            continue
        rows.append(
            {
                "schema_version": FORECAST_SCHEMA_VERSION,
                "generated_at": generated_at or utc_now_iso(),
                "outcome_id": f"outcome:{forecast.get('forecast_id')}",
                "forecast_id": forecast.get("forecast_id"),
                "venue": forecast.get("venue", "kalshi"),
                "market_ticker": ticker,
                "result": result,
                "settlement_value": 1.0 if result == "yes" else 0.0,
                "resolved_at": market.get("settlement_ts")
                or market.get("latest_expiration_time")
                or generated_at
                or utc_now_iso(),
                "outcome_source": "kalshi_market_result",
                "market_status": market.get("status"),
            }
        )
    return rows


def _forecast_by_id(forecasts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("forecast_id") or ""): row for row in forecasts}


def _score_probability(probability: float, outcome: float) -> dict[str, float]:
    p = clamp_probability(probability)
    y = float(outcome)
    return {
        "brier": (p - y) ** 2,
        "log_loss": -(y * math.log(p) + (1.0 - y) * math.log(1.0 - p)),
    }


def compute_forecast_metrics(
    *,
    forecasts: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
    abstentions: list[dict[str, Any]] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    abstentions = abstentions or []
    by_id = _forecast_by_id(forecasts)
    model_scores: list[dict[str, float]] = []
    market_scores: list[dict[str, float]] = []
    pci_scores: list[dict[str, float]] = []
    settled = 0
    for outcome in outcomes:
        forecast = by_id.get(str(outcome.get("forecast_id") or ""))
        if forecast is None:
            continue
        value = float(outcome["settlement_value"])
        model_scores.append(_score_probability(forecast["model_probability"], value))
        market_scores.append(_score_probability(forecast["market_probability"], value))
        pci_scores.append(_score_probability(forecast["rule_probability"], value))
        settled += 1

    def mean(values: list[dict[str, float]], key: str) -> float | None:
        if not values:
            return None
        return round(sum(item[key] for item in values) / len(values), 6)

    open_count = len(forecasts) - settled
    signal_count = len(forecasts) + len(abstentions)
    return {
        "schema_version": FORECAST_SCHEMA_VERSION,
        "generated_at": generated_at or utc_now_iso(),
        "forecast_count": len(forecasts),
        "settled_forecast_count": settled,
        "open_forecast_count": open_count,
        "abstention_count": len(abstentions),
        "coverage_rate": (
            round(len(forecasts) / signal_count, 6) if signal_count else None
        ),
        "model": {
            "brier_score": mean(model_scores, "brier"),
            "log_loss": mean(model_scores, "log_loss"),
        },
        "baselines": {
            "market_prior": {
                "brier_score": mean(market_scores, "brier"),
                "log_loss": mean(market_scores, "log_loss"),
            },
            "pci_rule_only": {
                "brier_score": mean(pci_scores, "brier"),
                "log_loss": mean(pci_scores, "log_loss"),
            },
        },
        "calibration_ready": settled > 0,
    }


@dataclass(frozen=True)
class RiskLimits:
    max_order_usd: float = 10.0
    max_market_exposure_usd: float = 50.0
    max_total_exposure_usd: float = 250.0
    max_spread: float = 0.10
    min_liquidity_dollars: float = 100.0
    min_confidence: float = 0.65
    min_abs_edge: float = 0.08


@dataclass
class RiskState:
    total_exposure_usd: float = 0.0
    market_exposure_usd: dict[str, float] = field(default_factory=dict)


def _check(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def _proposal_side(edge: float) -> str:
    return "buy_yes" if edge > 0 else "buy_no_equivalent"


def _limit_price(forecast: dict[str, Any]) -> float:
    market = forecast.get("market_snapshot") or {}
    if float(forecast.get("edge") or 0.0) > 0:
        price = market.get("yes_bid") or forecast.get("market_probability") or 0.5
    else:
        price = market.get("yes_ask") or forecast.get("market_probability") or 0.5
    return round(clamp_probability(float(price)), 4)


def build_trade_proposal(
    forecast: dict[str, Any],
    *,
    limits: RiskLimits = RiskLimits(),
    state: RiskState | None = None,
) -> dict[str, Any]:
    state = state or RiskState()
    market = forecast.get("market_snapshot") or {}
    match = forecast.get("match") or {}
    ticker = str(forecast.get("market_ticker") or market.get("ticker") or "")
    edge = float(forecast.get("edge") or 0.0)
    confidence = float(forecast.get("confidence") or 0.0)
    spread = market.get("bid_ask_spread")
    spread_value = float(spread) if spread is not None else 1.0
    liquidity = float(market.get("liquidity_dollars") or 0.0)
    limit_price = _limit_price(forecast)
    contracts = round(limits.max_order_usd / max(limit_price, 0.01), 2)
    exposure_usd = round(contracts * limit_price, 2)
    market_after = state.market_exposure_usd.get(ticker, 0.0) + exposure_usd
    total_after = state.total_exposure_usd + exposure_usd

    checks = [
        _check("edge", abs(edge) >= limits.min_abs_edge, f"abs(edge)={abs(edge):.4f}"),
        _check(
            "spread", spread_value <= limits.max_spread, f"spread={spread_value:.4f}"
        ),
        _check(
            "liquidity",
            liquidity >= limits.min_liquidity_dollars,
            f"liquidity={liquidity:.2f}",
        ),
        _check(
            "confidence",
            confidence >= limits.min_confidence,
            f"confidence={confidence:.4f}",
        ),
        _check(
            "policy_relevant",
            bool(match.get("policy_relevant")),
            "market must be policy relevant",
        ),
        _check(
            "resolution_clear",
            bool(match.get("resolution_clear")),
            "resolution wording must be clear",
        ),
        _check(
            "public_info_only",
            not bool(forecast.get("private_info_used")),
            "forecast must use public evidence only",
        ),
        _check(
            "order_size",
            exposure_usd <= limits.max_order_usd + 0.01,
            f"order={exposure_usd:.2f}",
        ),
        _check(
            "market_exposure",
            market_after <= limits.max_market_exposure_usd + 0.01,
            f"market_after={market_after:.2f}",
        ),
        _check(
            "total_exposure",
            total_after <= limits.max_total_exposure_usd + 0.01,
            f"total_after={total_after:.2f}",
        ),
    ]
    passed = all(check["passed"] for check in checks)
    return {
        "schema_version": forecast.get("schema_version"),
        "generated_at": forecast.get("generated_at"),
        "proposal_id": f"proposal:{forecast.get('forecast_id')}",
        "forecast_id": forecast.get("forecast_id"),
        "venue": forecast.get("venue", "kalshi"),
        "market_ticker": ticker,
        "proposed_side": _proposal_side(edge),
        "order_type": "limit",
        "limit_price": limit_price,
        "contracts": contracts,
        "max_order_usd": limits.max_order_usd,
        "estimated_exposure_usd": exposure_usd,
        "edge": edge,
        "confidence": confidence,
        "risk_checks": checks,
        "risk_passed": passed,
        "approval_status": "pending_human_approval" if passed else "rejected",
        "execution_enabled": False,
        "rejection_reasons": [check["name"] for check in checks if not check["passed"]],
        "human_approval_required": True,
    }


def build_trade_proposals(
    forecasts: list[dict[str, Any]],
    *,
    limits: RiskLimits = RiskLimits(),
    include_rejected: bool = False,
) -> list[dict[str, Any]]:
    state = RiskState()
    proposals: list[dict[str, Any]] = []
    for forecast in forecasts:
        proposal = build_trade_proposal(forecast, limits=limits, state=state)
        proposals.append(proposal)
        if proposal["risk_passed"]:
            ticker = str(proposal.get("market_ticker") or "")
            exposure = float(proposal.get("estimated_exposure_usd") or 0.0)
            state.total_exposure_usd += exposure
            state.market_exposure_usd[ticker] = (
                state.market_exposure_usd.get(ticker, 0.0) + exposure
            )
    if include_rejected:
        return proposals
    return [proposal for proposal in proposals if proposal["risk_passed"]]
