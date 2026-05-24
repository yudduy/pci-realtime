from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import yaml
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from pci_realtime.config import DATA_ROOT, REQUEST_TIMEOUT_SECONDS
from pci_realtime.forecast_registry.engine import (
    FORECAST_SCHEMA_VERSION,
    clamp_probability,
)
from pci_realtime.forecast_registry.policy import (
    is_policy_relevant_text,
    text_contains_keyword,
)


LOGGER = logging.getLogger(__name__)
KALSHI_PRODUCTION_BASE_URL = "https://external-api.kalshi.com/trade-api/v2"
ORDER_ENDPOINT = "/portfolio/events/orders"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_float(value: Any, default: float | None = None) -> float | None:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    return [json.loads(line) for line in text.splitlines()]


@dataclass(frozen=True)
class KalshiQuery:
    name: str
    keywords: tuple[str, ...]
    status: str = "open"
    limit: int = 100
    series_ticker: str | None = None
    event_ticker: str | None = None
    tickers: tuple[str, ...] = ()


class KalshiClient:
    def __init__(
        self,
        *,
        base_url: str = KALSHI_PRODUCTION_BASE_URL,
        timeout_seconds: int = REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=timeout_seconds)

    def close(self) -> None:
        self.client.close()

    def get_markets(
        self,
        *,
        status: str = "open",
        limit: int = 100,
        series_ticker: str | None = None,
        event_ticker: str | None = None,
        tickers: tuple[str, ...] = (),
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"status": status, "limit": limit}
        if series_ticker:
            params["series_ticker"] = series_ticker
        if event_ticker:
            params["event_ticker"] = event_ticker
        if tickers:
            params["tickers"] = ",".join(tickers)

        rows: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            if cursor:
                params["cursor"] = cursor
            response = self.client.get(f"{self.base_url}/markets", params=params)
            response.raise_for_status()
            payload = response.json()
            rows.extend(payload.get("markets", []))
            cursor = payload.get("cursor")
            if not cursor or len(rows) >= limit:
                return rows[:limit]

    def get_orderbook(self, ticker: str, *, depth: int = 1) -> dict[str, Any]:
        response = self.client.get(
            f"{self.base_url}/markets/{ticker}/orderbook",
            params={"depth": depth},
        )
        response.raise_for_status()
        return response.json()


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
            "category",
        ]
    )


def _best_bid_from_orderbook(orderbook: dict[str, Any], side: str) -> float | None:
    levels = (orderbook.get("orderbook_fp") or {}).get(f"{side}_dollars") or []
    prices = [parse_float(level[0]) for level in levels if level]
    prices = [price for price in prices if price is not None]
    return max(prices) if prices else None


def _passes_query_keywords(market: dict[str, Any], keywords: tuple[str, ...]) -> bool:
    if not keywords:
        return True
    text = _market_text(market)
    return any(text_contains_keyword(text, keyword) for keyword in keywords)


def parse_market_snapshot(
    market: dict[str, Any],
    *,
    query_name: str = "fixture",
    orderbook: dict[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    yes_bid = parse_float(market.get("yes_bid_dollars"))
    yes_ask = parse_float(market.get("yes_ask_dollars"))
    if orderbook:
        yes_bid = (
            yes_bid
            if yes_bid is not None
            else _best_bid_from_orderbook(orderbook, "yes")
        )
        no_bid = _best_bid_from_orderbook(orderbook, "no")
        if yes_ask is None and no_bid is not None:
            yes_ask = 1.0 - no_bid

    last_price = parse_float(market.get("last_price_dollars"))
    if yes_bid is not None and yes_ask is not None:
        market_probability = clamp_probability((yes_bid + yes_ask) / 2.0)
        spread = max(0.0, yes_ask - yes_bid)
    else:
        market_probability = clamp_probability(last_price or 0.5)
        spread = None

    text = _market_text(market)
    return {
        "schema_version": FORECAST_SCHEMA_VERSION,
        "generated_at": generated_at or utc_now_iso(),
        "venue": "kalshi",
        "query_name": query_name,
        "ticker": str(market.get("ticker") or ""),
        "event_ticker": str(market.get("event_ticker") or ""),
        "title": str(market.get("title") or ""),
        "subtitle": str(market.get("subtitle") or ""),
        "yes_sub_title": str(market.get("yes_sub_title") or ""),
        "no_sub_title": str(market.get("no_sub_title") or ""),
        "status": str(market.get("status") or ""),
        "result": market.get("result"),
        "yes_bid": yes_bid,
        "yes_ask": yes_ask,
        "bid_ask_spread": spread,
        "market_probability": market_probability,
        "liquidity_dollars": parse_float(market.get("liquidity_dollars"), 0.0),
        "volume": parse_float(market.get("volume_fp"), 0.0),
        "volume_24h": parse_float(market.get("volume_24h_fp"), 0.0),
        "open_interest": parse_float(market.get("open_interest_fp"), 0.0),
        "open_time": market.get("open_time"),
        "close_time": market.get("close_time"),
        "expected_expiration_time": market.get("expected_expiration_time"),
        "latest_expiration_time": market.get("latest_expiration_time"),
        "expiration_time": market.get("expiration_time"),
        "settlement_timer_seconds": market.get("settlement_timer_seconds"),
        "settlement_ts": market.get("settlement_ts"),
        "rules_primary": str(market.get("rules_primary") or ""),
        "rules_secondary": str(market.get("rules_secondary") or ""),
        "policy_relevant": is_policy_relevant_text(text),
        "resolution_text": " ".join(
            part
            for part in [
                str(market.get("rules_primary") or ""),
                str(market.get("rules_secondary") or ""),
            ]
            if part
        ),
        "source": "kalshi_public_market_data",
    }


def load_queries(path: Path) -> list[KalshiQuery]:
    if not path.exists():
        return [
            KalshiQuery(
                name="policy_open_markets",
                keywords=(
                    "ira",
                    "inflation reduction act",
                    "tax credit",
                    "clean energy",
                    "climate",
                    "hydrogen tax credit",
                    "carbon capture",
                    "electric vehicle",
                    "treasury",
                    "irs",
                    "department of energy",
                    "loan programs office",
                    "section 45v",
                    "section 45x",
                    "section 45q",
                    "section 30d",
                    "lpo",
                ),
                limit=100,
            )
        ]
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [
        KalshiQuery(
            name=str(item.get("name") or "policy_query"),
            keywords=tuple(str(value) for value in item.get("keywords", [])),
            status=str(item.get("status") or "open"),
            limit=int(item.get("limit") or 100),
            series_ticker=item.get("series_ticker"),
            event_ticker=item.get("event_ticker"),
            tickers=tuple(str(value) for value in item.get("tickers", [])),
        )
        for item in payload.get("queries", [])
    ]


def snapshots_from_fixture(
    path: Path,
    *,
    generated_at: str | None = None,
    audit: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    payload = read_json(path)
    if "markets" in payload:
        markets = payload.get("markets", [])
    elif isinstance(payload, list):
        markets = payload
    else:
        markets = payload.get("data", [])
    orderbooks = payload.get("orderbooks", {}) if isinstance(payload, dict) else {}
    stats = {
        "scanned": 0,
        "published": 0,
        "rejected_not_policy_relevant": 0,
    }
    snapshots: list[dict[str, Any]] = []
    for market in markets:
        stats["scanned"] += 1
        snapshot = parse_market_snapshot(
            market,
            query_name=str(market.get("query_name") or "fixture"),
            orderbook=orderbooks.get(str(market.get("ticker") or "")),
            generated_at=generated_at,
        )
        if snapshot["policy_relevant"]:
            snapshots.append(snapshot)
            stats["published"] += 1
        else:
            stats["rejected_not_policy_relevant"] += 1
    if audit is not None:
        audit.update(stats)
    return snapshots


def fetch_market_snapshots(
    *,
    query_file: Path,
    base_url: str = KALSHI_PRODUCTION_BASE_URL,
    generated_at: str | None = None,
    audit: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    client = KalshiClient(base_url=base_url)
    generated = generated_at or utc_now_iso()
    seen: set[str] = set()
    snapshots: list[dict[str, Any]] = []
    stats = {
        "scanned": 0,
        "published": 0,
        "rejected_duplicate": 0,
        "rejected_query_keywords": 0,
        "rejected_not_policy_relevant": 0,
    }
    try:
        for query in load_queries(query_file):
            markets = client.get_markets(
                status=query.status,
                limit=query.limit,
                series_ticker=query.series_ticker,
                event_ticker=query.event_ticker,
                tickers=query.tickers,
            )
            for market in markets:
                stats["scanned"] += 1
                ticker = str(market.get("ticker") or "")
                if not ticker or ticker in seen:
                    stats["rejected_duplicate"] += 1
                    continue
                if not _passes_query_keywords(market, query.keywords):
                    stats["rejected_query_keywords"] += 1
                    continue
                snapshot = parse_market_snapshot(
                    market,
                    query_name=query.name,
                    generated_at=generated,
                )
                if not snapshot["policy_relevant"]:
                    stats["rejected_not_policy_relevant"] += 1
                    continue
                seen.add(ticker)
                snapshots.append(snapshot)
                stats["published"] += 1
    finally:
        client.close()
    if audit is not None:
        audit.update(stats)
    return sorted(snapshots, key=lambda row: row["ticker"])


class ExecutionGateError(RuntimeError):
    """Raised when a trade proposal fails the live-execution gate."""


@dataclass(frozen=True)
class KalshiCredentials:
    api_key_id: str
    private_key_pem: bytes

    @classmethod
    def from_env(cls) -> KalshiCredentials | None:
        api_key_id = os.getenv("KALSHI_API_KEY_ID") or os.getenv("KALSHI_ACCESS_KEY")
        private_key = os.getenv("KALSHI_PRIVATE_KEY")
        private_key_path = os.getenv("KALSHI_PRIVATE_KEY_PATH")
        if not api_key_id:
            return None
        if private_key:
            return cls(api_key_id=api_key_id, private_key_pem=private_key.encode())
        if private_key_path:
            return cls(
                api_key_id=api_key_id,
                private_key_pem=Path(private_key_path).read_bytes(),
            )
        return None


def sign_request(
    *,
    private_key_pem: bytes,
    timestamp_ms: str,
    method: str,
    path: str,
) -> str:
    private_key = serialization.load_pem_private_key(private_key_pem, password=None)
    path_without_query = path.split("?")[0]
    message = f"{timestamp_ms}{method.upper()}{path_without_query}".encode()
    signature = private_key.sign(
        message,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode()


def load_approval_file(path: Path) -> dict[str, Any]:
    return read_json(path)


def proposal_is_approved(proposal_id: str, approval_payload: dict[str, Any]) -> bool:
    approved_ids = approval_payload.get("approved_proposal_ids", [])
    if proposal_id in approved_ids:
        return True
    proposals = approval_payload.get("proposals", {})
    if isinstance(proposals, dict):
        return bool((proposals.get(proposal_id) or {}).get("approved"))
    if isinstance(proposals, list):
        return any(
            item.get("proposal_id") == proposal_id and item.get("approved")
            for item in proposals
            if isinstance(item, dict)
        )
    return False


def build_order_payload(proposal: dict[str, Any]) -> dict[str, Any]:
    proposed_side = str(proposal.get("proposed_side") or "")
    side = "bid" if proposed_side == "buy_yes" else "ask"
    return {
        "ticker": str(proposal["market_ticker"]),
        "client_order_id": str(proposal["proposal_id"]).replace(":", "-")[:64],
        "side": side,
        "count": f"{float(proposal['contracts']):.2f}",
        "price": f"{float(proposal['limit_price']):.4f}",
        "time_in_force": "good_till_canceled",
        "self_trade_prevention_type": "taker_at_cross",
        "post_only": True,
        "cancel_order_on_pause": True,
        "reduce_only": False,
    }


def create_signed_order_request(
    proposal: dict[str, Any],
    *,
    approval_payload: dict[str, Any],
    credentials: KalshiCredentials | None,
    enable_live_trading: bool,
    base_url: str = KALSHI_PRODUCTION_BASE_URL,
) -> dict[str, Any]:
    proposal_id = str(proposal.get("proposal_id") or "")
    if not enable_live_trading:
        raise ExecutionGateError(
            "PCI_ENABLE_LIVE_TRADING must be true for live execution."
        )
    if not proposal.get("risk_passed"):
        raise ExecutionGateError("Proposal failed risk checks.")
    if not proposal_is_approved(proposal_id, approval_payload):
        raise ExecutionGateError("Proposal is missing explicit human approval.")
    if credentials is None:
        raise ExecutionGateError("Kalshi credentials are missing.")

    payload = build_order_payload(proposal)
    timestamp_ms = str(int(time.time() * 1000))
    sign_path = urlparse(base_url + ORDER_ENDPOINT).path
    signature = sign_request(
        private_key_pem=credentials.private_key_pem,
        timestamp_ms=timestamp_ms,
        method="POST",
        path=sign_path,
    )
    return {
        "method": "POST",
        "url": base_url.rstrip("/") + ORDER_ENDPOINT,
        "headers": {
            "Content-Type": "application/json",
            "KALSHI-ACCESS-KEY": credentials.api_key_id,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": timestamp_ms,
        },
        "json": payload,
    }


def find_proposal(proposals: list[dict[str, Any]], proposal_id: str) -> dict[str, Any]:
    for proposal in proposals:
        if proposal.get("proposal_id") == proposal_id:
            return proposal
    msg = f"Proposal not found: {proposal_id}"
    raise KeyError(msg)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare or send a human-approved Kalshi order request."
    )
    parser.add_argument("--proposal-id", required=True)
    parser.add_argument("--approve-file", required=True)
    parser.add_argument(
        "--proposal-path",
        default=str(DATA_ROOT / "private" / "trade_proposals.jsonl"),
    )
    parser.add_argument("--base-url", default=KALSHI_PRODUCTION_BASE_URL)
    parser.add_argument(
        "--send",
        action="store_true",
        help="Actually POST the signed request after all gates pass.",
    )
    parser.add_argument("--output-path")
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = build_arg_parser().parse_args()
    proposal = find_proposal(read_jsonl(Path(args.proposal_path)), args.proposal_id)
    request = create_signed_order_request(
        proposal,
        approval_payload=load_approval_file(Path(args.approve_file)),
        credentials=KalshiCredentials.from_env(),
        enable_live_trading=os.getenv("PCI_ENABLE_LIVE_TRADING", "").lower() == "true",
        base_url=args.base_url,
    )
    if args.output_path:
        Path(args.output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output_path).write_text(
            json.dumps(request, indent=2) + "\n", encoding="utf-8"
        )
    if args.send:
        response = httpx.post(
            request["url"],
            headers=request["headers"],
            json=request["json"],
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        LOGGER.info("Kalshi order accepted: %s", response.text)
    else:
        LOGGER.info("Prepared signed order request for %s; not sent.", args.proposal_id)


if __name__ == "__main__":
    main()
