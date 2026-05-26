from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from pci_realtime.config import REQUEST_TIMEOUT_SECONDS
from pci_realtime.forecast_registry.engine import clamp_probability
from pci_realtime.forecast_registry.kalshi import load_queries, parse_float
from pci_realtime.forecast_registry.policy import (
    is_policy_relevant_text,
    text_contains_keyword,
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
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=timeout_seconds)

    def close(self) -> None:
        self.client.close()

    def get_markets(
        self, *, limit: int = 100, active: bool = True
    ) -> list[dict[str, Any]]:
        response = self.client.get(
            f"{self.base_url}/markets",
            params={"limit": limit, "active": str(active).lower()},
        )
        response.raise_for_status()
        payload = response.json()
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
        ]
    )


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
        "title": str(market.get("question") or ticker),
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
        },
    }


def fetch_polymarket_snapshots(
    *,
    query_file: Path,
    base_url: str = POLYMARKET_GAMMA_BASE_URL,
    generated_at: str | None = None,
    limit: int = 150,
) -> list[dict[str, Any]]:
    queries = load_queries(query_file)
    keywords = tuple(keyword for query in queries for keyword in query.keywords)
    generated = generated_at or utc_now_iso()
    client = PolymarketClient(base_url=base_url)
    try:
        markets = client.get_markets(limit=limit, active=True)
    finally:
        client.close()

    snapshots = []
    for market in markets:
        text = _market_text(market)
        if keywords and not any(
            text_contains_keyword(text, keyword) for keyword in keywords
        ):
            continue
        snapshot = parse_polymarket_snapshot(market, generated_at=generated)
        if snapshot["policy_relevant"]:
            snapshots.append(snapshot)
    return sorted(snapshots, key=lambda row: row["ticker"])
