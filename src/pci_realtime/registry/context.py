from __future__ import annotations

import os
import time
from datetime import date, timedelta
from typing import Any

from pci_realtime.registry.evidence import (
    evidence_rows_from_policy_events,
    source_document_rows_from_raw_docs,
    source_health_row,
    stable_hash,
)
from pci_realtime.ingest.public_sources import (
    COURTLISTENER_TOKEN_ENV,
    EIAClient,
    FRED_KEY_ENV,
    FREDClient,
    RegInfoIngestor,
    USASpendingIngestor,
    CourtListenerClient,
)


def build_context_rows(*, today: date | None = None) -> dict[str, list[dict[str, Any]]]:
    today = today or date.today()
    start_date = today - timedelta(days=30)
    docs: dict[str, dict[str, Any]] = {}
    events: list[dict[str, Any]] = []
    health: list[dict[str, Any]] = []

    _collect_eia(today=today, docs=docs, events=events, health=health)
    _collect_fred(start_date=start_date, docs=docs, events=events, health=health)
    _collect_courtlistener(docs=docs, events=events, health=health)
    _collect_ingestor_context(
        source="reginfo",
        ingestor=RegInfoIngestor(),
        start_date=start_date,
        end_date=today,
        docs=docs,
        events=events,
        health=health,
    )
    _collect_ingestor_context(
        source="usaspending",
        ingestor=USASpendingIngestor(),
        start_date=start_date,
        end_date=today,
        docs=docs,
        events=events,
        health=health,
    )

    return {
        "source_documents": source_document_rows_from_raw_docs(docs),
        "evidence_items": evidence_rows_from_policy_events(events),
        "source_links": [],
        "source_health": health,
    }


def _collect_eia(
    *,
    today: date,
    docs: dict[str, dict[str, Any]],
    events: list[dict[str, Any]],
    health: list[dict[str, Any]],
) -> None:
    started = time.monotonic()
    try:
        row = EIAClient().latest_electricity_price()
        period = row.get("period") or today.isoformat()
        period_date = (
            f"{period}-01" if isinstance(period, str) and len(period) == 7 else period
        )
        doc_id = f"eia:electricity-retail-price:{period}"
        body = (
            f"Average U.S. electricity price was {row.get('price')} "
            f"{row.get('price-units')} for {period}."
        )
        docs[doc_id] = _raw_context_doc(
            doc_id=doc_id,
            source="eia",
            agency="U.S. Energy Information Administration",
            title="U.S. retail electricity price",
            body=body,
            url="https://www.eia.gov/opendata/",
            date_value=period_date,
        )
        health.append(
            source_health_row(
                source="eia",
                status="success",
                row_count=1,
                latency_ms=int((time.monotonic() - started) * 1000),
            )
        )
    except Exception as exc:  # noqa: BLE001 - context failures degrade.
        health.append(_failed_health("eia", started, exc))


def _collect_fred(
    *,
    start_date: date,
    docs: dict[str, dict[str, Any]],
    events: list[dict[str, Any]],
    health: list[dict[str, Any]],
) -> None:
    del events
    if not os.getenv(FRED_KEY_ENV):
        health.append(
            source_health_row(
                source="fred",
                status="disabled",
                error_class="MissingApiKey",
                error_summary=f"{FRED_KEY_ENV} is not configured",
            )
        )
        return
    started = time.monotonic()
    try:
        client = FREDClient()
        count = 0
        for series_id in ["DGS10", "FEDFUNDS", "CPIAUCSL"]:
            observations = client.observations(
                series_id=series_id, start_date=start_date, limit=1
            )
            for observation in observations:
                doc_id = f"fred:{series_id}:{observation.get('date')}"
                docs[doc_id] = _raw_context_doc(
                    doc_id=doc_id,
                    source="fred",
                    agency="Federal Reserve Bank of St. Louis",
                    title=f"FRED {series_id}",
                    body=f"{series_id} was {observation.get('value')} on {observation.get('date')}.",
                    url=f"https://fred.stlouisfed.org/series/{series_id}",
                    date_value=observation.get("date"),
                )
                count += 1
        health.append(
            source_health_row(
                source="fred",
                status="success",
                row_count=count,
                latency_ms=int((time.monotonic() - started) * 1000),
            )
        )
    except Exception as exc:  # noqa: BLE001
        health.append(_failed_health("fred", started, exc))


def _collect_courtlistener(
    *,
    docs: dict[str, dict[str, Any]],
    events: list[dict[str, Any]],
    health: list[dict[str, Any]],
) -> None:
    del events
    started = time.monotonic()
    try:
        client = CourtListenerClient(token=os.getenv(COURTLISTENER_TOKEN_ENV))
        results = client.search(
            query='"Inflation Reduction Act" tax credit', page_size=5
        )
        for result in results:
            absolute_url = result.get("absolute_url") or ""
            doc_id = (
                f"courtlistener:{result.get('cluster_id') or stable_hash(absolute_url)}"
            )
            docs[doc_id] = _raw_context_doc(
                doc_id=doc_id,
                source="courtlistener",
                agency=result.get("court") or "CourtListener",
                title=result.get("caseName") or result.get("caseNameFull") or doc_id,
                body=result.get("snippet") or result.get("caseName") or "",
                url=f"https://www.courtlistener.com{absolute_url}"
                if absolute_url
                else "",
                date_value=result.get("dateFiled") or result.get("dateArgued"),
            )
        health.append(
            source_health_row(
                source="courtlistener",
                status="success",
                row_count=len(results),
                latency_ms=int((time.monotonic() - started) * 1000),
            )
        )
    except Exception as exc:  # noqa: BLE001
        health.append(_failed_health("courtlistener", started, exc))


def _collect_ingestor_context(
    *,
    source: str,
    ingestor: Any,
    start_date: date,
    end_date: date,
    docs: dict[str, dict[str, Any]],
    events: list[dict[str, Any]],
    health: list[dict[str, Any]],
) -> None:
    started = time.monotonic()
    try:
        frame = ingestor.collect_documents(start_date=start_date, end_date=end_date)
        for row in frame.to_dict("records"):
            doc_id = str(row.get("doc_id") or "")
            if not doc_id:
                continue
            docs[doc_id] = row
            for provision in row.get("provisions_mentioned") or []:
                events.append(
                    {
                        "event_id": f"context:{doc_id}:{provision}",
                        "doc_id": doc_id,
                        "provision": provision,
                        "pci_delta": 0,
                        "dimension_deltas": {},
                        "rationale": row.get("body"),
                        "confidence": None,
                        "prompt_version": "context-v1",
                    }
                )
        health.append(
            source_health_row(
                source=source,
                status="success",
                row_count=len(frame),
                latency_ms=int((time.monotonic() - started) * 1000),
            )
        )
    except Exception as exc:  # noqa: BLE001
        health.append(_failed_health(source, started, exc))


def _raw_context_doc(
    *,
    doc_id: str,
    source: str,
    agency: str,
    title: str,
    body: str,
    url: str,
    date_value: Any,
) -> dict[str, Any]:
    return {
        "doc_id": doc_id,
        "date": date_value or date.today().isoformat(),
        "source": source,
        "agency": agency,
        "title": title,
        "body": body,
        "body_truncated": False,
        "url": url,
        "provisions_mentioned": [],
        "ingested_at": date.today().isoformat(),
        "ingestor_version": "context-v1",
    }


def _failed_health(source: str, started: float, exc: Exception) -> dict[str, Any]:
    return source_health_row(
        source=source,
        status="failed",
        latency_ms=int((time.monotonic() - started) * 1000),
        error_class=type(exc).__name__,
        error_summary=str(exc),
    )
