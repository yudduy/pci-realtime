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
    PROVISION_EXPOSURES,
    is_policy_relevant_text,
)


LOGGER = logging.getLogger(__name__)
POLYMARKET_GAMMA_BASE_URL = "https://gamma-api.polymarket.com"
POLYMARKET_SEARCH_STOP_TERMS = {
    "tax credit",
    "tax credits",
    "production credit",
    "treasury",
    "irs",
    "department of energy",
    "doe",
    "ev",
    "battery",
    "solar",
}


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

    def get_market_by_slug(self, slug: str) -> dict[str, Any] | None:
        payload = self._get_json(
            "/markets",
            params={
                "slug": slug,
                "limit": 1,
            },
        )
        if isinstance(payload, list):
            rows = [item for item in payload if isinstance(item, dict)]
            return rows[0] if rows else None
        if isinstance(payload, dict):
            rows = payload.get("markets") or payload.get("data") or []
            if isinstance(rows, list):
                rows = [item for item in rows if isinstance(item, dict)]
                return rows[0] if rows else None
        return None

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

    def public_search(
        self,
        *,
        query: str,
        limit_per_type: int = 10,
        page: int = 1,
        events_status: str = "active",
        keep_closed_markets: int = 0,
    ) -> dict[str, Any]:
        payload = self._get_json(
            "/public-search",
            params={
                "q": query,
                "events_status": events_status,
                "limit_per_type": limit_per_type,
                "page": page,
                "search_profiles": "false",
                "search_tags": "true",
                "keep_closed_markets": keep_closed_markets,
            },
        )
        return payload if isinstance(payload, dict) else {}

    def get_events_keyset(
        self,
        *,
        limit: int = 500,
        after_cursor: str | None = None,
        closed: bool = False,
        order: str = "volume",
        ascending: bool = False,
        title_search: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "limit": limit,
            "closed": str(closed).lower(),
            "order": order,
            "ascending": str(ascending).lower(),
        }
        if after_cursor:
            params["after_cursor"] = after_cursor
        if title_search:
            params["title_search"] = title_search
        payload = self._get_json("/events/keyset", params=params)
        return payload if isinstance(payload, dict) else {"events": []}

    def get_markets_keyset(
        self,
        *,
        limit: int = 100,
        after_cursor: str | None = None,
        closed: bool = False,
        order: str = "volume_num",
        ascending: bool = False,
        include_tag: bool = True,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "limit": limit,
            "closed": str(closed).lower(),
            "order": order,
            "ascending": str(ascending).lower(),
            "include_tag": str(include_tag).lower(),
        }
        if after_cursor:
            params["after_cursor"] = after_cursor
        payload = self._get_json("/markets/keyset", params=params)
        return payload if isinstance(payload, dict) else {"markets": []}

    def get_tags(self) -> list[dict[str, Any]]:
        payload = self._get_json("/tags")
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        return [item for item in payload.get("tags", []) if isinstance(item, dict)]

    def get_series(self) -> list[dict[str, Any]]:
        payload = self._get_json("/series", params={"closed": "false"})
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        return [item for item in payload.get("series", []) if isinstance(item, dict)]


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
            "_discovery_sources",
            "_discovery_search_query",
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
        row.setdefault("_discovery_sources", event.get("_discovery_sources"))
        row.setdefault(
            "_discovery_search_provisions", event.get("_discovery_search_provisions")
        )
        row.setdefault("_discovery_search_query", event.get("_discovery_search_query"))
        rows.append(row)
    return rows


def _items_from_payload(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    values = payload.get(key)
    if values is None:
        values = payload.get("data")
    if not isinstance(values, list):
        return []
    return [item for item in values if isinstance(item, dict)]


def _next_cursor(payload: dict[str, Any]) -> str | None:
    cursor = payload.get("next_cursor") or payload.get("nextCursor")
    return str(cursor) if cursor else None


def _search_terms_by_provision() -> dict[str, set[str]]:
    terms: dict[str, set[str]] = {}
    for provision, exposure in PROVISION_EXPOSURES.items():
        values = {provision, *exposure.market_keywords}
        for value in values:
            normalized = value.strip().lower()
            if not normalized or normalized in POLYMARKET_SEARCH_STOP_TERMS:
                continue
            if len(normalized) <= 2:
                continue
            terms.setdefault(normalized, set()).add(provision)
    return terms


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
            "discovery_sources": market.get("_discovery_sources") or [],
            "search_query": market.get("_discovery_search_query"),
            "search_provisions": market.get("_discovery_search_provisions") or [],
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
    market_limit: int | None = None,
    page_limit: int = 100,
    run_id: str | None = None,
    include_all_candidates: bool = False,
    request_interval_seconds: float = 0.0,
    include_public_search: bool = True,
) -> MarketScanResult:
    queries = load_queries(query_file)
    keywords = tuple(keyword for query in queries for keyword in query.keywords)
    generated = generated_at or utc_now_iso()
    scan_run_id = run_id or f"local-{generated}"
    client = PolymarketClient(
        base_url=base_url, request_interval_seconds=request_interval_seconds
    )
    raw_market_map: dict[str, dict[str, Any]] = {}
    stats: dict[str, Any] = {
        "scanned": 0,
        "published": 0,
        "stored_candidates": 0,
        "rejected_duplicate": 0,
        "rejected_query_keywords": 0,
        "rejected_not_policy_relevant": 0,
        "event_pages": 0,
        "market_fallback_pages": 0,
        "market_keyset_pages": 0,
        "public_search_requests": 0,
        "title_search_pages": 0,
        "requests": 0,
        "rate_limited": 0,
        "retries": 0,
    }

    def add_raw_market(
        market: dict[str, Any],
        *,
        source: str,
        search_query: str | None = None,
        search_provisions: set[str] | None = None,
    ) -> None:
        ticker = str(market.get("slug") or market.get("id") or "")
        if not ticker:
            return
        row = dict(market)
        sources = set(row.get("_discovery_sources") or [])
        sources.add(source)
        if ticker in raw_market_map:
            existing = raw_market_map[ticker]
            sources.update(existing.get("_discovery_sources") or [])
            for key, value in row.items():
                if existing.get(key) in (None, "", []) and value not in (None, "", []):
                    existing[key] = value
            row = existing
        row["_discovery_sources"] = sorted(sources)
        if search_query:
            row["_discovery_search_query"] = search_query
        provisions = set(row.get("_discovery_search_provisions") or [])
        provisions.update(search_provisions or set())
        row["_discovery_search_provisions"] = sorted(provisions)
        raw_market_map[ticker] = row

    try:
        max_events = max(0, limit)
        cursor: str | None = None
        seen_events = 0
        while seen_events < max_events:
            batch_limit = min(500, max(1, max_events - seen_events))
            payload = client.get_events_keyset(limit=batch_limit, after_cursor=cursor)
            stats["event_pages"] += 1
            events = _items_from_payload(payload, "events")
            if not events:
                break
            for event in events:
                event = {
                    **event,
                    "_discovery_sources": ["polymarket_events_keyset"],
                }
                for market in _markets_from_event(event):
                    add_raw_market(market, source="polymarket_events_keyset")
            seen_events += len(events)
            cursor = _next_cursor(payload)
            if not cursor or len(events) < batch_limit:
                break

        max_markets = max(0, market_limit if market_limit is not None else limit)
        cursor = None
        seen_markets = 0
        while seen_markets < max_markets:
            batch_limit = min(100, max(1, max_markets - seen_markets))
            payload = client.get_markets_keyset(limit=batch_limit, after_cursor=cursor)
            stats["market_keyset_pages"] += 1
            markets = _items_from_payload(payload, "markets")
            if not markets:
                break
            for market in markets:
                add_raw_market(market, source="polymarket_markets_keyset")
            seen_markets += len(markets)
            cursor = _next_cursor(payload)
            if not cursor or len(markets) < batch_limit:
                break

        if include_public_search:
            for search_query, provisions in sorted(
                _search_terms_by_provision().items()
            ):
                payload = client.public_search(query=search_query, limit_per_type=10)
                stats["public_search_requests"] += 1
                for event in _items_from_payload(payload, "events"):
                    event = {
                        **event,
                        "_discovery_sources": ["polymarket_public_search"],
                        "_discovery_search_query": search_query,
                        "_discovery_search_provisions": sorted(provisions),
                    }
                    for market in _markets_from_event(event):
                        add_raw_market(
                            market,
                            source="polymarket_public_search",
                            search_query=search_query,
                            search_provisions=provisions,
                        )
                for market in _items_from_payload(payload, "markets"):
                    add_raw_market(
                        market,
                        source="polymarket_public_search",
                        search_query=search_query,
                        search_provisions=provisions,
                    )

                title_payload = client.get_events_keyset(
                    limit=10, title_search=search_query
                )
                stats["title_search_pages"] += 1
                for event in _items_from_payload(title_payload, "events"):
                    event = {
                        **event,
                        "_discovery_sources": ["polymarket_title_search"],
                        "_discovery_search_query": search_query,
                        "_discovery_search_provisions": sorted(provisions),
                    }
                    for market in _markets_from_event(event):
                        add_raw_market(
                            market,
                            source="polymarket_title_search",
                            search_query=search_query,
                            search_provisions=provisions,
                        )
    finally:
        stats["requests"] = client.request_count
        stats["rate_limited"] = client.rate_limited_count
        stats["retries"] = client.retry_count
        client.close()

    raw_markets = list(raw_market_map.values())
    snapshots: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    inventory: list[dict[str, Any]] = []
    seen: set[str] = set()
    for market in raw_markets:
        stats["scanned"] += 1
        text = _market_text(market)
        ticker = str(market.get("slug") or market.get("id") or "")
        if not ticker or ticker in seen:
            stats["rejected_duplicate"] += 1
            continue
        seen.add(ticker)
        inventory_snapshot = parse_polymarket_snapshot(market, generated_at=generated)
        inventory.append(inventory_snapshot)
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
        inventory=sorted(inventory, key=lambda row: row["ticker"]),
    )
