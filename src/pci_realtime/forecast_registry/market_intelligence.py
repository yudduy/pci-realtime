from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from pci_realtime.config import (
    CACHE_ROOT,
    LLM_AUDIT_MODEL,
    LLM_AUDIT_PROVIDER,
    TRACKED_PROVISIONS,
)
from pci_realtime.forecast_registry.discovery import (
    OPEN_MARKET_STATUSES,
    market_text,
    matched_policy_context_keywords,
    matched_policy_keywords,
    matched_provisions,
    resolution_clear,
)
from pci_realtime.forecast_registry.policy import (
    PROVISION_DETAILS,
    PROVISION_EXPOSURES,
    infer_policy_orientation,
)
from pci_realtime.scoring.cache import JsonCache, build_cache_key
from pci_realtime.scoring.screener import (
    StructuredOutputClient,
    create_structured_output_client,
)


MARKET_ASSESSMENT_SCHEMA_VERSION = "market-assessment-v1.0.0"
MARKET_ASSESSMENT_PROMPT_VERSION = "market-assessment-v1"
MARKET_RELEVANCE_CLASSES = {
    "direct_policy",
    "implementation_proxy",
    "sector_proxy",
    "macro_context",
    "unrelated",
}
RESOLUTION_FITS = {"clear", "partial", "ambiguous", "none"}
FORECAST_CONFIDENCE_THRESHOLD = 0.70
MAX_LEXICAL_TARGETS_PER_PROVISION = 5
MARKET_ASSESSMENT_ITEM_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "provision": {"type": "string", "enum": list(TRACKED_PROVISIONS)},
        "relevance_class": {
            "type": "string",
            "enum": sorted(MARKET_RELEVANCE_CLASSES),
        },
        "resolution_fit": {"type": "string", "enum": sorted(RESOLUTION_FITS)},
        "orientation": {
            "type": "string",
            "enum": [
                "repeal_risk",
                "continuity",
                "funding_availability",
                "implementation",
                "demand_proxy",
                "macro_context",
                "unknown",
            ],
        },
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "evidence_span": {"type": "string"},
        "rationale": {"type": "string"},
        "eligible_for_forecast": {"type": "boolean"},
    },
    "required": [
        "provision",
        "relevance_class",
        "resolution_fit",
        "orientation",
        "confidence",
        "evidence_span",
        "rationale",
        "eligible_for_forecast",
    ],
}
MARKET_ASSESSMENT_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "assessments": {"type": "array", "items": MARKET_ASSESSMENT_ITEM_SCHEMA},
    },
    "required": ["assessments"],
}
WEAK_LEXICAL_TERMS = {
    "tax credit",
    "tax credits",
    "production credit",
    "treasury",
    "irs",
    "department of energy",
    "doe",
    "loan guarantee",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_hash(payload: Any) -> str:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def market_payload_hash(market: dict[str, Any]) -> str:
    return _json_hash(
        {
            key: market.get(key)
            for key in [
                "venue",
                "ticker",
                "event_ticker",
                "title",
                "subtitle",
                "status",
                "market_probability",
                "liquidity_dollars",
                "volume",
                "volume_24h",
                "close_time",
                "resolution_text",
                "rules_primary",
                "rules_secondary",
            ]
        }
    )


def market_inventory_row(
    market: dict[str, Any], *, run_id: str, generated_at: str
) -> dict[str, Any]:
    return {
        "venue": str(market.get("venue") or "unknown"),
        "ticker": str(market.get("ticker") or ""),
        "latest_run_id": run_id,
        "last_seen_at": generated_at,
        "title": str(market.get("title") or market.get("ticker") or ""),
        "market_url": market.get("market_url"),
        "status": market.get("status"),
        "close_time": market.get("close_time"),
        "market_probability": market.get("market_probability"),
        "yes_bid": market.get("yes_bid"),
        "yes_ask": market.get("yes_ask"),
        "bid_ask_spread": market.get("bid_ask_spread"),
        "liquidity_dollars": market.get("liquidity_dollars"),
        "volume": market.get("volume"),
        "volume_24h": market.get("volume_24h"),
        "open_interest": market.get("open_interest"),
        "resolution_text": market.get("resolution_text"),
        "source_payload_hash": market_payload_hash(market),
        "raw_public_metadata": {
            "query_name": market.get("query_name"),
            "source": market.get("source"),
            "event_ticker": market.get("event_ticker"),
            "subtitle": market.get("subtitle"),
            **(market.get("raw_public_metadata") or {}),
        },
    }


def market_inventory_rows(
    markets: list[dict[str, Any]], *, run_id: str, generated_at: str
) -> list[dict[str, Any]]:
    rows = [
        market_inventory_row(market, run_id=run_id, generated_at=generated_at)
        for market in markets
        if market.get("ticker") and market.get("venue")
    ]
    return sorted(rows, key=lambda row: (row["venue"], row["ticker"]))


class MarketAssessmentClient(Protocol):
    provider: str
    model: str

    def assess_many(
        self, *, market: dict[str, Any], provisions: dict[str, list[str]]
    ) -> dict[str, dict[str, Any]]: ...


@dataclass(frozen=True)
class HeuristicMarketAssessmentClient:
    provider: str = "offline"
    model: str = "market_assessment_heuristic_v1"

    def assess_many(
        self, *, market: dict[str, Any], provisions: dict[str, list[str]]
    ) -> dict[str, dict[str, Any]]:
        return {
            provision: self.assess(
                market=market,
                provision=provision,
                recall_reasons=recall_reasons,
            )
            for provision, recall_reasons in provisions.items()
        }

    def assess(
        self, *, market: dict[str, Any], provision: str, recall_reasons: list[str]
    ) -> dict[str, Any]:
        text = market_text(market)
        provision_hits = matched_provisions(text)
        context_hits = matched_policy_context_keywords(text)
        policy_hits = matched_policy_keywords(text)
        clear = resolution_clear(market)
        status = str(market.get("status") or "").lower()
        is_open = not status or status in OPEN_MARKET_STATUSES
        has_provision = provision in provision_hits
        orientation = _normalized_orientation(text)

        if has_provision and context_hits and clear and is_open:
            relevance_class = "direct_policy"
            resolution_fit = "clear"
            confidence = 0.76
        elif has_provision and context_hits:
            relevance_class = "implementation_proxy"
            resolution_fit = "partial" if clear else "ambiguous"
            confidence = 0.58
        elif has_provision:
            relevance_class = "sector_proxy"
            resolution_fit = "partial" if clear else "ambiguous"
            confidence = 0.45
        elif policy_hits or context_hits:
            relevance_class = "macro_context"
            resolution_fit = "partial" if clear else "none"
            confidence = 0.34
        else:
            relevance_class = "unrelated"
            resolution_fit = "none"
            confidence = 0.10

        eligible = (
            relevance_class == "direct_policy"
            and resolution_fit == "clear"
            and confidence >= FORECAST_CONFIDENCE_THRESHOLD
            and is_open
        )
        return {
            "relevance_class": relevance_class,
            "resolution_fit": resolution_fit,
            "orientation": orientation,
            "confidence": confidence,
            "evidence_span": _evidence_span(market),
            "rationale": (
                f"Heuristic assessment for {provision}; recall="
                f"{', '.join(recall_reasons) or 'lexical'}."
            ),
            "eligible_for_forecast": eligible,
        }


@dataclass(frozen=True)
class StructuredLLMMarketAssessmentClient:
    client: StructuredOutputClient
    model: str = LLM_AUDIT_MODEL
    provider: str = LLM_AUDIT_PROVIDER
    cache: JsonCache = field(
        default_factory=lambda: JsonCache(CACHE_ROOT / "market_assessments")
    )
    prompt_version: str = MARKET_ASSESSMENT_PROMPT_VERSION
    temperature: float = 0.1

    def assess_many(
        self, *, market: dict[str, Any], provisions: dict[str, list[str]]
    ) -> dict[str, dict[str, Any]]:
        del provisions
        input_payload = {
            "venue": market.get("venue"),
            "ticker": market.get("ticker"),
            "text_hash": market_payload_hash(market),
        }
        cache_key = build_cache_key(
            provider=self.provider,
            model=self.model,
            prompt_version=self.prompt_version,
            temperature=self.temperature,
            schema_version=MARKET_ASSESSMENT_SCHEMA_VERSION,
            stage="market_assessment",
            input_payload=input_payload,
        )
        cached = self.cache.get(cache_key)
        if cached is not None:
            return _assessment_payloads_by_provision(cached.payload, cached=True)

        payload = {
            "task": (
                "Classify whether this public prediction market is useful for "
                "PCIndex market intelligence. Be conservative. Return one "
                "assessment for every tracked provision. A market is "
                "eligible_for_forecast only if its resolution criteria directly "
                "resolve an official policy outcome for that provision."
            ),
            "provisions": [
                {
                    "code": provision,
                    "name": PROVISION_DETAILS[provision]["name"],
                    "type": PROVISION_DETAILS[provision]["type"],
                    "primary_channel": PROVISION_DETAILS[provision]["primary_channel"],
                    "keywords": list(PROVISION_EXPOSURES[provision].market_keywords),
                }
                for provision in TRACKED_PROVISIONS
            ],
            "market": {
                "venue": market.get("venue"),
                "ticker": market.get("ticker"),
                "title": market.get("title"),
                "subtitle": market.get("subtitle"),
                "status": market.get("status"),
                "resolution_text": market.get("resolution_text"),
                "rules_primary": market.get("rules_primary"),
                "rules_secondary": market.get("rules_secondary"),
                "market_probability": market.get("market_probability"),
                "liquidity_dollars": market.get("liquidity_dollars"),
                "volume": market.get("volume"),
                "market_url": market.get("market_url"),
            },
        }
        response = self.client.create_json(
            model=self.model,
            system_prompt=(
                "You are a cautious public prediction-market analyst for climate "
                "policy credibility. Use only the supplied public market text. "
                "Do not mark sector/company/proxy markets as forecast-eligible."
            ),
            user_prompt=json.dumps(payload, sort_keys=True),
            json_schema=MARKET_ASSESSMENT_JSON_SCHEMA,
            schema_name="market_assessment",
            temperature=self.temperature,
        )
        self.cache.set(cache_key, response)
        return _assessment_payloads_by_provision(response.payload, cached=False)

    def assess(
        self, *, market: dict[str, Any], provision: str, recall_reasons: list[str]
    ) -> dict[str, Any]:
        del recall_reasons
        return self.assess_many(market=market, provisions={provision: []}).get(
            provision,
            _default_unrelated_assessment(provision),
        )


def create_market_assessment_client() -> MarketAssessmentClient:
    if not os.getenv("OPENAI_API_KEY"):
        return HeuristicMarketAssessmentClient()
    try:
        structured = create_structured_output_client(LLM_AUDIT_PROVIDER)
    except RuntimeError:
        return HeuristicMarketAssessmentClient()
    return StructuredLLMMarketAssessmentClient(client=structured)


def _assessment_payloads_by_provision(
    payload: dict[str, Any], *, cached: bool
) -> dict[str, dict[str, Any]]:
    assessments = payload.get("assessments") if isinstance(payload, dict) else []
    if not isinstance(assessments, list):
        assessments = []
    rows: dict[str, dict[str, Any]] = {}
    for item in assessments:
        if not isinstance(item, dict):
            continue
        provision = str(item.get("provision") or "")
        if provision not in TRACKED_PROVISIONS:
            continue
        row = dict(item)
        row["cached"] = cached
        rows[provision] = row
    return rows


def _default_unrelated_assessment(provision: str) -> dict[str, Any]:
    return {
        "provision": provision,
        "relevance_class": "unrelated",
        "resolution_fit": "none",
        "orientation": "unknown",
        "confidence": 0.0,
        "evidence_span": "",
        "rationale": "No assessment payload was returned for this provision.",
        "eligible_for_forecast": False,
        "cached": False,
    }


def build_market_assessment_rows(
    *,
    markets: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    run_id: str,
    generated_at: str,
    client: MarketAssessmentClient | None = None,
    max_lexical_per_provision: int = MAX_LEXICAL_TARGETS_PER_PROVISION,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    client = client or create_market_assessment_client()
    targets = select_assessment_targets(
        markets,
        candidates,
        max_lexical_per_provision=max_lexical_per_provision,
    )
    rows: list[dict[str, Any]] = []
    stats = {
        "provider": client.provider,
        "model": client.model,
        "targets": len(targets),
        "market_calls": 0,
        "eligible_for_forecast": 0,
        "cached": 0,
    }
    grouped: dict[tuple[str, str], tuple[dict[str, Any], dict[str, list[str]]]] = {}
    for market, provision, recall_reasons in targets:
        key = (str(market.get("venue") or ""), str(market.get("ticker") or ""))
        if key not in grouped:
            grouped[key] = (market, {})
        grouped[key][1][provision] = recall_reasons

    for market, provisions in grouped.values():
        stats["market_calls"] += 1
        payloads = client.assess_many(market=market, provisions=provisions)
        for provision, recall_reasons in provisions.items():
            payload = payloads.get(provision, _default_unrelated_assessment(provision))
            normalized = normalize_assessment_payload(
                payload,
                market=market,
                provision=provision,
            )
            if normalized.get("cached"):
                stats["cached"] += 1
            if normalized["eligible_for_forecast"]:
                stats["eligible_for_forecast"] += 1
            rows.append(
                {
                    "assessment_id": assessment_id(market, provision),
                    "schema_version": MARKET_ASSESSMENT_SCHEMA_VERSION,
                    "assessed_at": generated_at,
                    "latest_run_id": run_id,
                    "venue": market.get("venue"),
                    "ticker": market.get("ticker"),
                    "provision": provision,
                    "source_text_hash": market_payload_hash(market),
                    "relevance_class": normalized["relevance_class"],
                    "resolution_fit": normalized["resolution_fit"],
                    "orientation": normalized["orientation"],
                    "confidence": normalized["confidence"],
                    "evidence_span": normalized["evidence_span"],
                    "rationale": normalized["rationale"],
                    "eligible_for_forecast": normalized["eligible_for_forecast"],
                    "model_provider": client.provider,
                    "model_name": client.model,
                    "prompt_version": MARKET_ASSESSMENT_PROMPT_VERSION,
                    "cached": bool(normalized.get("cached")),
                    "raw_public_metadata": {
                        "recall_reasons": recall_reasons,
                        "market_url": market.get("market_url"),
                    },
                }
            )
    return (
        sorted(rows, key=lambda row: (row["venue"], row["ticker"], row["provision"])),
        stats,
    )


def select_assessment_targets(
    markets: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    *,
    max_lexical_per_provision: int = MAX_LEXICAL_TARGETS_PER_PROVISION,
) -> list[tuple[dict[str, Any], str, list[str]]]:
    markets_by_key = {
        (str(market.get("venue") or ""), str(market.get("ticker") or "")): market
        for market in markets
        if market.get("venue") and market.get("ticker")
    }
    reasons: dict[tuple[str, str, str], set[str]] = {}

    def add_target(market: dict[str, Any], provision: str, reason: str) -> None:
        if provision not in TRACKED_PROVISIONS:
            return
        venue = str(market.get("venue") or "")
        ticker = str(market.get("ticker") or "")
        if not venue or not ticker:
            return
        reasons.setdefault((venue, ticker, provision), set()).add(reason)

    for market in markets:
        text = market_text(market)
        for provision in matched_provisions(text):
            add_target(market, provision, "matched_provision_terms")
        metadata = market.get("raw_public_metadata") or {}
        for provision in metadata.get("search_provisions") or []:
            add_target(market, str(provision), "polymarket_public_search")

    for candidate in candidates:
        key = (str(candidate.get("venue") or ""), str(candidate.get("ticker") or ""))
        market = markets_by_key.get(key)
        if not market:
            continue
        for provision in candidate.get("matched_provisions") or []:
            add_target(market, str(provision), "candidate_audit_match")

    for provision in TRACKED_PROVISIONS:
        scored = sorted(
            (
                (lexical_score_for_provision(market, provision), market)
                for market in markets
            ),
            key=lambda item: item[0],
            reverse=True,
        )
        taken = 0
        for score, market in scored:
            if score <= 0 or taken >= max_lexical_per_provision:
                break
            add_target(market, provision, f"top_lexical_score:{score:.3f}")
            taken += 1

    rows = []
    for venue, ticker, provision in sorted(reasons):
        market = markets_by_key.get((venue, ticker))
        if market is None:
            continue
        rows.append((market, provision, sorted(reasons[(venue, ticker, provision)])))
    return rows


def lexical_score_for_provision(market: dict[str, Any], provision: str) -> float:
    exposure = PROVISION_EXPOSURES.get(provision)
    if exposure is None:
        return 0.0
    text = market_text(market)
    terms = [
        term
        for term in [
            provision.lower(),
            *[term.lower() for term in exposure.market_keywords],
        ]
        if term not in WEAK_LEXICAL_TERMS
    ]
    strong_hits = sum(1 for term in terms if term and term in text)
    policy_hits = len(matched_policy_context_keywords(text))
    if strong_hits == 0:
        return 0.0
    liquidity = float(market.get("liquidity_dollars") or 0.0)
    volume = float(market.get("volume") or 0.0)
    activity_bonus = min(0.25, (liquidity + volume) / 100_000_000)
    return strong_hits + min(0.5, 0.05 * policy_hits) + activity_bonus


def normalize_assessment_payload(
    payload: dict[str, Any], *, market: dict[str, Any], provision: str
) -> dict[str, Any]:
    relevance_class = str(payload.get("relevance_class") or "unrelated")
    if relevance_class not in MARKET_RELEVANCE_CLASSES:
        relevance_class = "unrelated"
    resolution_fit = str(payload.get("resolution_fit") or "none")
    if resolution_fit not in RESOLUTION_FITS:
        resolution_fit = "none"
    confidence = max(0.0, min(1.0, float(payload.get("confidence") or 0.0)))
    status = str(market.get("status") or "").lower()
    is_open = not status or status in OPEN_MARKET_STATUSES
    eligible = bool(payload.get("eligible_for_forecast")) and (
        relevance_class == "direct_policy"
        and resolution_fit == "clear"
        and confidence >= FORECAST_CONFIDENCE_THRESHOLD
        and is_open
        and provision in TRACKED_PROVISIONS
    )
    return {
        "relevance_class": relevance_class,
        "resolution_fit": resolution_fit,
        "orientation": str(
            payload.get("orientation") or _normalized_orientation(market_text(market))
        ),
        "confidence": round(confidence, 4),
        "evidence_span": str(payload.get("evidence_span") or _evidence_span(market))[
            :600
        ],
        "rationale": str(payload.get("rationale") or "")[:1000],
        "eligible_for_forecast": eligible,
        "cached": bool(payload.get("cached")),
    }


def eligible_snapshots_from_assessments(
    markets: list[dict[str, Any]], assessments: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    markets_by_key = {
        (str(market.get("venue") or ""), str(market.get("ticker") or "")): market
        for market in markets
    }
    selected: dict[tuple[str, str], dict[str, Any]] = {}
    for row in assessments:
        if not row.get("eligible_for_forecast"):
            continue
        key = (str(row.get("venue") or ""), str(row.get("ticker") or ""))
        previous = selected.get(key)
        if previous is None or float(row.get("confidence") or 0.0) > float(
            previous.get("confidence") or 0.0
        ):
            selected[key] = row

    snapshots: list[dict[str, Any]] = []
    for key, assessment in selected.items():
        market = markets_by_key.get(key)
        if market is None:
            continue
        snapshot = dict(market)
        metadata = dict(snapshot.get("raw_public_metadata") or {})
        metadata["assessment"] = {
            "assessment_id": assessment.get("assessment_id"),
            "provision": assessment.get("provision"),
            "relevance_class": assessment.get("relevance_class"),
            "resolution_fit": assessment.get("resolution_fit"),
            "orientation": assessment.get("orientation"),
            "confidence": assessment.get("confidence"),
            "eligible_for_forecast": assessment.get("eligible_for_forecast"),
        }
        snapshot["raw_public_metadata"] = metadata
        snapshot["policy_relevant"] = True
        snapshot["query_name"] = f"assessment:{assessment['provision']}"
        snapshots.append(snapshot)
    return sorted(snapshots, key=lambda row: (row["venue"], row["ticker"]))


def assessment_id(market: dict[str, Any], provision: str) -> str:
    return f"{market.get('venue')}:{market.get('ticker')}:{provision}"


def _normalized_orientation(text: str) -> str:
    orientation = infer_policy_orientation(text)
    if orientation == "adverse_policy_change":
        return "repeal_risk"
    if orientation == "supportive_policy_continuity":
        return "continuity"
    if "fund" in text or "loan" in text or "appropriation" in text:
        return "funding_availability"
    if "vehicle" in text or "ev" in text or "tesla" in text:
        return "demand_proxy"
    if matched_policy_context_keywords(text):
        return "macro_context"
    return "unknown"


def _evidence_span(market: dict[str, Any]) -> str:
    text = " ".join(
        str(market.get(key) or "")
        for key in ["title", "subtitle", "resolution_text", "rules_primary"]
    )
    return " ".join(text.split())[:600]
