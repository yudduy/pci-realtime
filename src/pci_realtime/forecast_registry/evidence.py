from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from typing import Any

import pandas as pd


SOURCE_DISPLAY_NAMES = {
    "federal_register": "Federal Register",
    "treasury": "Treasury",
    "irs": "IRS",
    "congress": "Congress",
    "omb": "OMB",
    "regulations_gov": "Regulations.gov",
    "reginfo": "OIRA review",
    "usaspending": "Federal spending",
    "govinfo": "GovInfo",
    "eia": "Energy data",
    "fred": "Macro data",
    "courtlistener": "Court records",
    "kalshi": "Kalshi markets",
    "polymarket": "Polymarket markets",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_value(value: Any) -> Any:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_value(item) for item in value]
    if hasattr(value, "tolist"):
        return json_value(value.tolist())
    if not isinstance(value, (list, dict, tuple, set)):
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass
    return value


def stable_hash(*parts: Any) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(str(part or "").encode("utf-8", errors="ignore"))
        digest.update(b"\x00")
    return digest.hexdigest()


def excerpt(text: Any, max_chars: int = 520) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "..."


def source_document_rows_from_raw_docs(
    raw_docs: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for doc_id, raw in sorted(raw_docs.items()):
        body = raw.get("body") or ""
        rows.append(
            {
                "source_doc_id": doc_id,
                "source": raw.get("source") or "official_source",
                "source_name": SOURCE_DISPLAY_NAMES.get(
                    str(raw.get("source") or ""), str(raw.get("source") or "Source")
                ),
                "source_type": "official_text",
                "external_id": doc_id.split(":", 1)[-1],
                "title": raw.get("title") or doc_id,
                "agency": raw.get("agency"),
                "url": raw.get("url"),
                "published_at": raw.get("date"),
                "fetched_at": raw.get("ingested_at") or utc_now_iso(),
                "content_hash": stable_hash(
                    doc_id, raw.get("title"), raw.get("url"), body
                ),
                "text_excerpt": excerpt(body),
                "raw_public_metadata": {
                    "provisions_mentioned": raw.get("provisions_mentioned") or [],
                    "body_truncated": bool(raw.get("body_truncated")),
                    "ingestor_version": raw.get("ingestor_version"),
                },
            }
        )
    return [json_value(row) for row in rows]


def source_document_rows_from_markets(
    markets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for market in markets:
        venue = str(market.get("venue") or "market")
        ticker = str(market.get("ticker") or "")
        if not ticker:
            continue
        source_doc_id = f"market:{venue}:{ticker}"
        rows.append(
            {
                "source_doc_id": source_doc_id,
                "source": venue,
                "source_name": SOURCE_DISPLAY_NAMES.get(venue, venue.title()),
                "source_type": "market_snapshot",
                "external_id": ticker,
                "title": market.get("title") or ticker,
                "agency": None,
                "url": market.get("market_url"),
                "published_at": market.get("generated_at"),
                "fetched_at": market.get("generated_at") or utc_now_iso(),
                "content_hash": stable_hash(
                    venue, ticker, market.get("generated_at"), market.get("title")
                ),
                "text_excerpt": excerpt(
                    " ".join(
                        str(market.get(key) or "")
                        for key in ["title", "subtitle", "resolution_text"]
                    )
                ),
                "raw_public_metadata": {
                    "status": market.get("status"),
                    "query_name": market.get("query_name"),
                    "probability": market.get("market_probability"),
                    "liquidity_dollars": market.get("liquidity_dollars"),
                },
            }
        )
    return [json_value(row) for row in rows]


def evidence_rows_from_policy_events(
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for event in events:
        event_id = str(event.get("event_id") or "")
        if not event_id:
            continue
        dimension_deltas = event.get("dimension_deltas") or {}
        primary_dimension = (
            max(
                dimension_deltas, key=lambda key: abs(float(dimension_deltas[key] or 0))
            )
            if dimension_deltas
            else "pci"
        )
        rows.append(
            {
                "evidence_id": f"evidence:{event_id}",
                "source_doc_id": event.get("doc_id"),
                "provision": event.get("provision"),
                "evidence_type": "pci_scoring_rationale",
                "snippet": excerpt(event.get("rationale")),
                "normalized_signal": (f"{float(event.get('pci_delta') or 0):+.2f} PCI"),
                "score_dimension": primary_dimension,
                "confidence": event.get("confidence"),
                "extractor_version": event.get("prompt_version"),
            }
        )
    return [json_value(row) for row in rows]


def evidence_rows_from_market_snapshots(
    markets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for market in markets:
        venue = str(market.get("venue") or "market")
        ticker = str(market.get("ticker") or "")
        if not ticker:
            continue
        rows.append(
            {
                "evidence_id": f"evidence:market:{venue}:{ticker}",
                "source_doc_id": f"market:{venue}:{ticker}",
                "provision": None,
                "evidence_type": "market_snapshot",
                "snippet": excerpt(
                    market.get("resolution_text") or market.get("title")
                ),
                "normalized_signal": (
                    f"{float(market.get('market_probability') or 0):.0%} market"
                    if market.get("market_probability") is not None
                    else "market snapshot"
                ),
                "score_dimension": "market_probability",
                "confidence": None,
                "extractor_version": market.get("source"),
            }
        )
    return [json_value(row) for row in rows]


def source_links_from_policy_events(
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "link_id": f"link:policy_events:{event['event_id']}",
            "evidence_id": f"evidence:{event['event_id']}",
            "target_table": "policy_events",
            "target_id": event["event_id"],
            "link_type": "primary_source",
        }
        for event in events
        if event.get("event_id")
    ]


def source_links_from_forecasts(
    forecasts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    links = []
    for forecast in forecasts:
        forecast_id = str(forecast.get("forecast_id") or "")
        signal = forecast.get("signal") or {}
        source_event_id = str(signal.get("source_event_id") or "")
        if forecast_id and source_event_id:
            links.append(
                {
                    "link_id": f"link:forecasts:{forecast_id}:{source_event_id}",
                    "evidence_id": f"evidence:{source_event_id}",
                    "target_table": "forecasts",
                    "target_id": forecast_id,
                    "link_type": "forecast_basis",
                }
            )
        market = forecast.get("market_snapshot") or {}
        venue = str(market.get("venue") or forecast.get("venue") or "")
        ticker = str(market.get("ticker") or forecast.get("market_ticker") or "")
        if forecast_id and venue and ticker:
            links.append(
                {
                    "link_id": f"link:forecasts:{forecast_id}:market:{venue}:{ticker}",
                    "evidence_id": f"evidence:market:{venue}:{ticker}",
                    "target_table": "forecasts",
                    "target_id": forecast_id,
                    "link_type": "market_match",
                }
            )
    return [json_value(row) for row in links]


def source_links_from_market_snapshots(
    markets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    links = []
    for market in markets:
        venue = str(market.get("venue") or "")
        ticker = str(market.get("ticker") or "")
        if not venue or not ticker:
            continue
        links.append(
            {
                "link_id": f"link:market_snapshots:{venue}:{ticker}",
                "evidence_id": f"evidence:market:{venue}:{ticker}",
                "target_table": "market_snapshots",
                "target_id": f"{venue}:{ticker}",
                "link_type": "public_market_data",
            }
        )
    return [json_value(row) for row in links]


def source_health_row(
    *,
    source: str,
    status: str,
    row_count: int = 0,
    last_attempt_at: str | None = None,
    last_success_at: str | None = None,
    latency_ms: int | None = None,
    error_class: str | None = None,
    error_summary: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = utc_now_iso()
    return json_value(
        {
            "source": source,
            "source_name": SOURCE_DISPLAY_NAMES.get(
                source, source.replace("_", " ").title()
            ),
            "status": status,
            "last_attempt_at": last_attempt_at or now,
            "last_success_at": last_success_at
            or (now if status == "success" else None),
            "latency_ms": latency_ms,
            "row_count": row_count,
            "last_error_class": error_class,
            "last_error_summary": excerpt(error_summary, max_chars=300),
            "details": details or {},
        }
    )
