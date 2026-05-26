from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from pci_realtime.forecast_registry.policy import (
    POLICY_MARKET_KEYWORDS,
    PROVISION_EXPOSURES,
)


MARKET_DISCOVERY_SCHEMA_VERSION = "market-discovery-v1.0.0"
OPEN_MARKET_STATUSES = {"active", "open", "initialized"}
POLICY_CONTEXT_TERMS = {
    "ira",
    "inflation reduction act",
    "tax credit",
    "tax credits",
    "treasury",
    "irs",
    "department of energy",
    "doe",
    "loan programs office",
    "lpo",
    "congress",
    "regulation",
    "federal",
    "agency",
    "rule",
    "guidance",
    "subsidy",
}
WEAK_PROVISION_TERMS = {
    "tax credit",
    "tax credits",
    "production credit",
    "treasury",
    "irs",
    "department of energy",
    "doe",
    "loan guarantee",
}


@lru_cache(maxsize=512)
def _keyword_pattern(keyword: str) -> re.Pattern[str]:
    normalized = keyword.strip().lower()
    if len(normalized) <= 3 or normalized.replace(" ", "").isalnum():
        return re.compile(r"(?<![a-z0-9])" + re.escape(normalized) + r"(?![a-z0-9])")
    return re.compile(re.escape(normalized))


POLICY_KEYWORD_PATTERNS = {
    keyword: _keyword_pattern(keyword) for keyword in sorted(POLICY_MARKET_KEYWORDS)
}
POLICY_CONTEXT_PATTERNS = {
    keyword: _keyword_pattern(keyword) for keyword in sorted(POLICY_CONTEXT_TERMS)
}
PROVISION_KEYWORD_PATTERNS = {
    provision: {
        term: _keyword_pattern(term)
        for term in sorted(
            {provision, *exposure.market_keywords} - WEAK_PROVISION_TERMS
        )
    }
    for provision, exposure in PROVISION_EXPOSURES.items()
}


@dataclass(frozen=True)
class MarketScanResult:
    snapshots: list[dict[str, Any]]
    candidates: list[dict[str, Any]]
    stats: dict[str, Any]


def market_text(market: dict[str, Any]) -> str:
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
            "category",
            "market_url",
        ]
    ).lower()


def matched_policy_keywords(text: str) -> list[str]:
    lowered = text.lower()
    return [
        keyword
        for keyword, pattern in POLICY_KEYWORD_PATTERNS.items()
        if pattern.search(lowered)
    ]


def matched_policy_context_keywords(text: str) -> list[str]:
    lowered = text.lower()
    return [
        keyword
        for keyword, pattern in POLICY_CONTEXT_PATTERNS.items()
        if pattern.search(lowered)
    ]


def any_keyword_match(text: str, keywords: tuple[str, ...]) -> bool:
    if not keywords:
        return True
    lowered = text.lower()
    return any(_keyword_pattern(keyword).search(lowered) for keyword in keywords)


def matched_provisions(text: str) -> list[str]:
    rows: list[str] = []
    lowered = text.lower()
    for provision, patterns in PROVISION_KEYWORD_PATTERNS.items():
        if any(pattern.search(lowered) for pattern in patterns.values()):
            rows.append(provision)
    return rows


def resolution_clear(market: dict[str, Any]) -> bool:
    text = market_text(market)
    rules = str(market.get("resolution_text") or market.get("rules_primary") or "")
    if len(rules.strip()) < 20:
        return False
    return not any(term in text for term in ("subjective", "unclear", "ambiguous"))


def market_candidate_row(
    market: dict[str, Any],
    *,
    run_id: str,
    generated_at: str,
    rank: int,
    query_name: str | None = None,
) -> dict[str, Any]:
    text = market_text(market)
    policy_terms = matched_policy_keywords(text)
    context_terms = matched_policy_context_keywords(text)
    provisions = matched_provisions(text)
    status = str(market.get("status") or "").lower()
    is_open = not status or status in OPEN_MARKET_STATUSES
    clear_resolution = resolution_clear(market)
    policy_relevant = bool(context_terms and provisions)
    tracked_overlap = bool(provisions)

    rejection_reasons: list[str] = []
    if not is_open:
        rejection_reasons.append("market_not_open")
    if not context_terms:
        rejection_reasons.append("no_policy_context")
    if not tracked_overlap:
        rejection_reasons.append("no_tracked_provision_overlap")
    if not clear_resolution:
        rejection_reasons.append("unclear_or_missing_resolution")

    venue = str(market.get("venue") or "unknown")
    ticker = str(market.get("ticker") or "")
    source_metadata = market.get("raw_public_metadata") or {}
    return {
        "candidate_id": f"{run_id}:{venue}:{ticker}",
        "run_id": run_id,
        "schema_version": MARKET_DISCOVERY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "venue": venue,
        "ticker": ticker,
        "event_ticker": market.get("event_ticker"),
        "title": str(market.get("title") or ticker),
        "market_url": market.get("market_url"),
        "status": market.get("status"),
        "close_time": market.get("close_time"),
        "query_name": query_name or str(market.get("query_name") or ""),
        "candidate_rank": rank,
        "matched_keywords": policy_terms,
        "matched_provisions": provisions,
        "policy_relevant": policy_relevant,
        "resolution_clear": clear_resolution,
        "eligible_snapshot": policy_relevant,
        "rejection_reasons": rejection_reasons if not policy_relevant else [],
        "resolution_text": market.get("resolution_text"),
        "liquidity_dollars": market.get("liquidity_dollars"),
        "volume": market.get("volume"),
        "volume_24h": market.get("volume_24h"),
        "raw_public_metadata": {
            "source": market.get("source"),
            "query_name": query_name or market.get("query_name"),
            **source_metadata,
        },
    }


def should_store_candidate(
    candidate: dict[str, Any], *, include_all_candidates: bool = False
) -> bool:
    if include_all_candidates:
        return True
    return bool(
        candidate.get("eligible_snapshot")
        or candidate.get("matched_keywords")
        or candidate.get("matched_provisions")
    )
