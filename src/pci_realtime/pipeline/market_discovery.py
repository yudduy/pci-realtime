from __future__ import annotations

import argparse
import logging
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pci_realtime.forecast_registry.evidence import (
    evidence_rows_from_market_snapshots,
    source_document_rows_from_markets,
    source_health_row,
    source_links_from_market_snapshots,
)
from pci_realtime.forecast_registry.kalshi import fetch_market_snapshot_scan
from pci_realtime.forecast_registry.polymarket import fetch_polymarket_snapshot_scan
from pci_realtime.forecast_registry.store import (
    SupabaseRestClient,
    market_to_row,
    write_json,
)


LOGGER = logging.getLogger(__name__)
DEFAULT_QUERY_FILE = Path("config/policy_market_queries.yml")
PROVIDER_LIMIT_REFERENCES = {
    "kalshi": {
        "basic_read_budget_tokens_per_second": 200,
        "default_request_cost_tokens": 10,
        "effective_basic_read_requests_per_second": 20,
        "source_url": "https://docs.kalshi.com/getting_started/rate_limits",
    },
    "polymarket": {
        "gamma_events_requests_per_10_seconds": 500,
        "gamma_markets_requests_per_10_seconds": 300,
        "source_url": "https://docs.polymarket.com/api-reference/rate-limits",
    },
}


@dataclass(frozen=True)
class MarketDiscoveryResult:
    run_id: str
    counts: dict[str, int]
    rows_by_table: dict[str, list[dict[str, Any]]]


def _combine_stats(scans: dict[str, dict[str, Any]]) -> dict[str, Any]:
    totals: dict[str, Any] = {"by_venue": scans}
    for stats in scans.values():
        for key, value in stats.items():
            if isinstance(value, int):
                totals[key] = int(totals.get(key, 0)) + value
    return totals


def build_market_discovery_rows(
    *,
    run_id: str | None = None,
    query_file: Path = DEFAULT_QUERY_FILE,
    fetch_kalshi: bool = True,
    fetch_polymarket: bool = True,
    polymarket_limit: int = 1000,
    include_all_candidates: bool = False,
    request_interval_seconds: float = 0.0,
) -> dict[str, list[dict[str, Any]]]:
    run_id = run_id or str(uuid.uuid4())
    snapshots: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    source_health: list[dict[str, Any]] = []
    scans: dict[str, dict[str, Any]] = {}
    errors: dict[str, str] = {}
    started = time.monotonic()

    if fetch_kalshi:
        provider_started = time.monotonic()
        try:
            scan = fetch_market_snapshot_scan(
                query_file=query_file,
                run_id=run_id,
                include_all_candidates=include_all_candidates,
                request_interval_seconds=request_interval_seconds,
            )
            snapshots.extend(scan.snapshots)
            candidates.extend(scan.candidates)
            scans["kalshi"] = scan.stats
            source_health.append(
                source_health_row(
                    source="kalshi",
                    status="success",
                    row_count=int(scan.stats.get("scanned") or 0),
                    latency_ms=round((time.monotonic() - provider_started) * 1000),
                    details=scan.stats,
                )
            )
        except Exception as exc:  # noqa: BLE001 - keep one provider from hiding the other.
            errors["kalshi"] = f"{type(exc).__name__}: {exc}"
            source_health.append(
                source_health_row(
                    source="kalshi",
                    status="failed",
                    latency_ms=round((time.monotonic() - provider_started) * 1000),
                    error_class=type(exc).__name__,
                    error_summary=str(exc),
                )
            )

    if fetch_polymarket:
        provider_started = time.monotonic()
        try:
            scan = fetch_polymarket_snapshot_scan(
                query_file=query_file,
                run_id=run_id,
                limit=polymarket_limit,
                include_all_candidates=include_all_candidates,
                request_interval_seconds=request_interval_seconds,
            )
            snapshots.extend(scan.snapshots)
            candidates.extend(scan.candidates)
            scans["polymarket"] = scan.stats
            source_health.append(
                source_health_row(
                    source="polymarket",
                    status="success",
                    row_count=int(scan.stats.get("scanned") or 0),
                    latency_ms=round((time.monotonic() - provider_started) * 1000),
                    details=scan.stats,
                )
            )
        except Exception as exc:  # noqa: BLE001 - keep one provider from hiding the other.
            errors["polymarket"] = f"{type(exc).__name__}: {exc}"
            source_health.append(
                source_health_row(
                    source="polymarket",
                    status="failed",
                    latency_ms=round((time.monotonic() - provider_started) * 1000),
                    error_class=type(exc).__name__,
                    error_summary=str(exc),
                )
            )

    requested = [
        name
        for name, enabled in [
            ("kalshi", fetch_kalshi),
            ("polymarket", fetch_polymarket),
        ]
        if enabled
    ]
    success_count = len(scans)
    status = "success" if success_count == len(requested) else "failed"
    metadata = {
        "requested_venues": requested,
        "successful_venues": sorted(scans),
        "provider_errors": errors,
        "scan": _combine_stats(scans),
        "provider_limit_references": PROVIDER_LIMIT_REFERENCES,
        "markets": len(snapshots),
        "market_discovery_candidates": len(candidates),
        "eligible_candidates": sum(
            1 for row in candidates if row.get("eligible_snapshot")
        ),
        "include_all_candidates": include_all_candidates,
        "elapsed_ms": round((time.monotonic() - started) * 1000),
        "absence_claim": (
            "No eligible public policy market was found"
            if not snapshots and success_count == len(requested)
            else None
        ),
    }

    return {
        "pipeline_runs": [
            {
                "run_id": run_id,
                "run_type": "market_discovery",
                "status": status,
                "source": "market_discovery.py",
                "metadata": metadata,
            }
        ],
        "market_snapshots": [market_to_row(market) for market in snapshots],
        "market_discovery_candidates": candidates,
        "source_documents": source_document_rows_from_markets(snapshots),
        "evidence_items": evidence_rows_from_market_snapshots(snapshots),
        "source_links": source_links_from_market_snapshots(snapshots),
        "source_health": source_health,
    }


def write_market_discovery_rows(
    rows_by_table: dict[str, list[dict[str, Any]]],
    *,
    client: SupabaseRestClient,
) -> None:
    client.insert_rows("pipeline_runs", rows_by_table["pipeline_runs"])
    client.insert_rows("market_snapshots", rows_by_table["market_snapshots"])
    client.upsert_rows(
        "market_discovery_candidates",
        rows_by_table["market_discovery_candidates"],
        on_conflict="candidate_id",
    )
    client.upsert_rows(
        "source_documents",
        rows_by_table["source_documents"],
        on_conflict="source_doc_id",
    )
    client.upsert_rows(
        "evidence_items",
        rows_by_table["evidence_items"],
        on_conflict="evidence_id",
    )
    client.upsert_rows(
        "source_links",
        rows_by_table["source_links"],
        on_conflict="link_id",
    )
    client.upsert_rows(
        "source_health",
        rows_by_table["source_health"],
        on_conflict="source",
    )


def run_market_discovery(
    *,
    query_file: Path = DEFAULT_QUERY_FILE,
    fetch_kalshi: bool = True,
    fetch_polymarket: bool = True,
    polymarket_limit: int = 1000,
    include_all_candidates: bool = False,
    request_interval_seconds: float = 0.0,
    dry_run: bool = False,
    output_path: Path | None = None,
    client: SupabaseRestClient | None = None,
) -> MarketDiscoveryResult:
    run_id = str(uuid.uuid4())
    rows_by_table = build_market_discovery_rows(
        run_id=run_id,
        query_file=query_file,
        fetch_kalshi=fetch_kalshi,
        fetch_polymarket=fetch_polymarket,
        polymarket_limit=polymarket_limit,
        include_all_candidates=include_all_candidates,
        request_interval_seconds=request_interval_seconds,
    )
    counts = {table: len(rows) for table, rows in rows_by_table.items()}
    if output_path is not None:
        write_json(
            output_path, {"run_id": run_id, "counts": counts, "rows": rows_by_table}
        )
    if not dry_run:
        supabase = client or SupabaseRestClient.from_env()
        if supabase is None:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required"
            )
        write_market_discovery_rows(rows_by_table, client=supabase)
    return MarketDiscoveryResult(
        run_id=run_id, counts=counts, rows_by_table=rows_by_table
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run broad public market discovery and write audit evidence."
    )
    parser.add_argument("--query-file", default=str(DEFAULT_QUERY_FILE))
    parser.add_argument("--no-kalshi", action="store_true")
    parser.add_argument("--no-polymarket", action="store_true")
    parser.add_argument("--polymarket-limit", type=int, default=1000)
    parser.add_argument("--include-all-candidates", action="store_true")
    parser.add_argument("--request-interval-seconds", type=float, default=0.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-path")
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = build_arg_parser().parse_args()
    result = run_market_discovery(
        query_file=Path(args.query_file),
        fetch_kalshi=not args.no_kalshi,
        fetch_polymarket=not args.no_polymarket,
        polymarket_limit=args.polymarket_limit,
        include_all_candidates=args.include_all_candidates,
        request_interval_seconds=args.request_interval_seconds,
        dry_run=args.dry_run,
        output_path=Path(args.output_path) if args.output_path else None,
    )
    LOGGER.info("Market discovery run %s counts: %s", result.run_id, result.counts)


if __name__ == "__main__":
    main()
