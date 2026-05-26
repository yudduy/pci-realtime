from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from pci_realtime.config import REQUEST_TIMEOUT_SECONDS
from pci_realtime.forecast_registry.discovery import (
    MarketScanResult,
    any_keyword_match,
    market_candidate_row,
    matched_provisions,
    should_store_candidate,
)
from pci_realtime.forecast_registry.engine import clamp_probability
from pci_realtime.forecast_registry.kalshi import load_queries, parse_float
from pci_realtime.forecast_registry.policy import (
    is_policy_relevant_text,
)


LOGGER = logging.getLogger(__name__)
POLYMARKET_GAMMA_BASE_URL = "https://gamma-api.polymarket.com"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PolymarketClient:
    def __init__(
        self,
        *,
        base_url: str = POLYMARKET_GAMMA_BASE_URL,
        timeout_seconds: int = REQUEST_TIMEOUT_SECONDS,
        request_interval_seconds: float = 0.0,
        max_retries: int = 4,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=timeout_seconds)
        self.request_interval_seconds = request_interval_seconds
        self.max_retries = max_retries
        self.request_count = 0
        self.rate_limited_count = 0
        self.retry_count = 0

    def close(self) -> None:
        self.client.close()

    def _get_json(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        attempt = 0
        while True:
            self.request_count += 1
            response = self.client.get(f"{self.base_url}{path}", params=params)
            if response.status_code not in {429, 503}:
                response.raise_for_status()
                if self.request_interval_seconds > 0:
                    time.sleep(self.request_interval_seconds)
                return response.json()
            self.rate_limited_count += 1
            if attempt >= self.max_retries:
                response.raise_for_status()
            delay = min(8.0, 0.5 * (2**attempt))
            self.retry_count += 1
            LOGGER.warning("Polymarket API throttled; backing off for %.1fs", delay)
            time.sleep(delay)
            attempt += 1

    def get_markets(
        self, *, limit: int = 100, offset: int = 0, active: bool = True
    ) -> list[dict[str, Any]]:
        payload = self._get_json(
            "/markets",
            params={
                "limit": limit,
                "offset": offset,
                "active": str(active).lower(),
                "closed": "false",
            },
        )
        return [item for item in payload if isinstance(item, dict)]

    def get_events(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        active: bool = True,
        closed: bool = False,
        order: str = "volume_24hr",
        ascending: bool = False,
    ) -> list[dict[str, Any]]:
        payload = self._get_json(
            "/events",
            params={
                "limit": limit,
                "offset": offset,
                "active": str(active).lower(),
                "closed": str(closed).lower(),
                "order": order,
                "ascending": str(ascending).lower(),
            },
        )
        return [item for item in payload if isinstance(item, dict)]


def _market_text(market: dict[str, Any]) -> str:
    return " ".join(
        str(market.get(key) or "")
        for key in [
            "question",
            "description",
            "resolutionSource",
            "category",
            "slug",
            "eventSlug",
            "eventTitle",
        ]
    )


def _markets_from_event(event: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    markets = event.get("markets") or []
    if not isinstance(markets, list):
        return rows
    for market in markets:
        if not isinstance(market, dict):
            continue
        row = dict(market)
        row.setdefault("eventSlug", event.get("slug"))
        row.setdefault("eventTitle", event.get("title") or event.get("question"))
        row.setdefault("category", event.get("category"))
        row.setdefault("active", event.get("active"))
        row.setdefault("closed", event.get("closed"))
        row.setdefault("startDate", event.get("startDate"))
        row.setdefault("endDate", event.get("endDate"))
        rows.append(row)
    return rows


def _outcome_price(market: dict[str, Any], index: int) -> float | None:
    prices = market.get("outcomePrices")
    if isinstance(prices, str):
        try:
            import json

            prices = json.loads(prices)
        except Exception:  # noqa: BLE001 - malformed public payload.
            return None
    if isinstance(prices, list) and len(prices) > index:
        return parse_float(prices[index])
    return None


def parse_polymarket_snapshot(
    market: dict[str, Any], *, generated_at: str | None = None
) -> dict[str, Any]:
    yes_price = (
        parse_float(market.get("bestAsk"))
        or parse_float(market.get("lastTradePrice"))
        or _outcome_price(market, 0)
    )
    market_probability = clamp_probability(yes_price or 0.5)
    ticker = str(market.get("slug") or market.get("id") or "")
    text = _market_text(market)
    return {
        "schema_version": "forecast-registry-v1.0.0",
        "generated_at": generated_at or utc_now_iso(),
        "venue": "polymarket",
        "query_name": "polymarket_gamma",
        "ticker": ticker,
        "event_ticker": str(market.get("conditionId") or ""),
        "title": str(market.get("question") or market.get("eventTitle") or ticker),
        "subtitle": str(market.get("category") or ""),
        "yes_sub_title": "Yes",
        "no_sub_title": "No",
        "status": "open" if market.get("active") else "closed",
        "result": None,
        "yes_bid": parse_float(market.get("bestBid")),
        "yes_ask": yes_price,
        "bid_ask_spread": parse_float(market.get("spread")),
        "market_probability": market_probability,
        "liquidity_dollars": parse_float(
            market.get("liquidityNum") or market.get("liquidity"), 0.0
        ),
        "volume": parse_float(market.get("volumeNum") or market.get("volume"), 0.0),
        "volume_24h": parse_float(market.get("volume24hr"), 0.0),
        "open_interest": parse_float(market.get("openInterest"), 0.0),
        "open_time": market.get("startDate"),
        "close_time": market.get("endDateIso") or market.get("endDate"),
        "expected_expiration_time": market.get("endDateIso") or market.get("endDate"),
        "latest_expiration_time": market.get("endDateIso") or market.get("endDate"),
        "settlement_ts": market.get("closedTime"),
        "rules_primary": str(market.get("description") or ""),
        "rules_secondary": str(market.get("resolutionSource") or ""),
        "policy_relevant": is_policy_relevant_text(text),
        "resolution_text": " ".join(
            part
            for part in [
                str(market.get("description") or ""),
                str(market.get("resolutionSource") or ""),
            ]
            if part
        ),
        "market_url": f"https://polymarket.com/market/{ticker}" if ticker else None,
        "source": "polymarket_gamma_public_data",
        "raw_public_metadata": {
            "id": market.get("id"),
            "condition_id": market.get("conditionId"),
            "slug": market.get("slug"),
            "event_slug": market.get("eventSlug"),
        },
    }


def fetch_polymarket_snapshots(
    *,
    query_file: Path,
    base_url: str = POLYMARKET_GAMMA_BASE_URL,
    generated_at: str | None = None,
    limit: int = 1000,
    run_id: str | None = None,
    include_all_candidates: bool = False,
    request_interval_seconds: float = 0.0,
) -> list[dict[str, Any]]:
    result = fetch_polymarket_snapshot_scan(
        query_file=query_file,
        base_url=base_url,
        generated_at=generated_at,
        limit=limit,
        run_id=run_id,
        include_all_candidates=include_all_candidates,
        request_interval_seconds=request_interval_seconds,
    )
    return result.snapshots


def fetch_polymarket_snapshot_scan(
    *,
    query_file: Path,
    base_url: str = POLYMARKET_GAMMA_BASE_URL,
    generated_at: str | None = None,
    limit: int = 1000,
    page_limit: int = 100,
    run_id: str | None = None,
    include_all_candidates: bool = False,
    request_interval_seconds: float = 0.0,
) -> MarketScanResult:
    queries = load_queries(query_file)
    keywords = tuple(keyword for query in queries for keyword in query.keywords)
    generated = generated_at or utc_now_iso()
    scan_run_id = run_id or f"local-{generated}"
    client = PolymarketClient(
        base_url=base_url, request_interval_seconds=request_interval_seconds
    )
    raw_markets: list[dict[str, Any]] = []
    stats: dict[str, Any] = {
        "scanned": 0,
        "published": 0,
        "stored_candidates": 0,
        "rejected_duplicate": 0,
        "rejected_query_keywords": 0,
        "rejected_not_policy_relevant": 0,
        "event_pages": 0,
        "market_fallback_pages": 0,
        "requests": 0,
        "rate_limited": 0,
        "retries": 0,
    }
    try:
        max_events = max(0, limit)
        offset = 0
        while offset < max_events:
            batch_limit = min(page_limit, max_events - offset)
            events = client.get_events(limit=batch_limit, offset=offset)
            stats["event_pages"] += 1
            if not events:
                break
            for event in events:
                raw_markets.extend(_markets_from_event(event))
            if len(events) < batch_limit:
                break
            offset += batch_limit
        if not raw_markets:
            offset = 0
            while offset < max_events:
                batch_limit = min(page_limit, max_events - offset)
                markets = client.get_markets(limit=batch_limit, offset=offset)
                stats["market_fallback_pages"] += 1
                if not markets:
                    break
                raw_markets.extend(markets)
                if len(markets) < batch_limit:
                    break
                offset += batch_limit
    finally:
        stats["requests"] = client.request_count
        stats["rate_limited"] = client.rate_limited_count
        stats["retries"] = client.retry_count
        client.close()

    snapshots: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for market in raw_markets:
        stats["scanned"] += 1
        text = _market_text(market)
        ticker = str(market.get("slug") or market.get("id") or "")
        if not ticker or ticker in seen:
            stats["rejected_duplicate"] += 1
            continue
        seen.add(ticker)
        passes_query = any_keyword_match(text, keywords)
        if not passes_query:
            stats["rejected_query_keywords"] += 1
        likely_candidate = bool(
            passes_query or include_all_candidates or matched_provisions(text)
        )
        if not likely_candidate:
            continue
        snapshot = parse_polymarket_snapshot(market, generated_at=generated)
        candidate = market_candidate_row(
            snapshot,
            run_id=scan_run_id,
            generated_at=generated,
            rank=stats["scanned"],
            query_name="polymarket_gamma_events",
        )
        if should_store_candidate(
            candidate, include_all_candidates=include_all_candidates
        ):
            candidates.append(candidate)
            stats["stored_candidates"] += 1
        if not passes_query:
            continue
        snapshot["policy_relevant"] = bool(candidate["eligible_snapshot"])
        if snapshot["policy_relevant"]:
            snapshots.append(snapshot)
            stats["published"] += 1
        else:
            stats["rejected_not_policy_relevant"] += 1
    return MarketScanResult(
        snapshots=sorted(snapshots, key=lambda row: row["ticker"]),
        candidates=sorted(candidates, key=lambda row: (row["venue"], row["ticker"])),
        stats=stats,
    )
