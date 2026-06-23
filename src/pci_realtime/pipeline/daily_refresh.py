from __future__ import annotations

import argparse
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pci_realtime.config import DATA_ROOT
from pci_realtime.forecast_registry.context import build_context_rows
from pci_realtime.forecast_registry.engine import utc_now_iso
from pci_realtime.forecast_registry.evidence import source_health_row
from pci_realtime.forecast_registry.kalshi import KALSHI_PRODUCTION_BASE_URL, read_jsonl
from pci_realtime.forecast_registry.store import (
    SupabaseRestClient,
    market_to_row,
    write_json,
)


LOGGER = logging.getLogger(__name__)
MarketFetcher = Callable[[], list[dict[str, Any]]]
ContextFetcher = Callable[[], dict[str, list[dict[str, Any]]]]


def _run_supabase_daily_refresh(
    *,
    client: SupabaseRestClient,
    market_fetcher: MarketFetcher | None = None,
    context_fetcher: ContextFetcher | None = None,
    base_url: str = KALSHI_PRODUCTION_BASE_URL,
    dry_run: bool = False,
    output_path: Path | None = None,
) -> dict[str, int]:
    markets = market_fetcher() if market_fetcher is not None else []
    context_rows = (
        context_fetcher() if context_fetcher is not None else build_context_rows()
    )
    refresh_health = [
        source_health_row(
            source="daily_refresh",
            status="success",
            row_count=len(markets),
            details={
                "refresh": "policy context and optional read-only market snapshots",
                "forecast_generation": "disabled_policy_desk",
                "forecast_outcomes": 0,
            },
        )
    ]
    rows_by_table = {
        "pipeline_runs": [
            {
                "run_type": "daily_refresh",
                "status": "success",
                "source": "daily_refresh.py",
                "completed_at": utc_now_iso(),
                "metadata": {
                    "markets_refreshed": len(markets),
                    "forecast_generation": "disabled_policy_desk",
                    "forecast_outcomes": 0,
                },
            }
        ],
        "market_snapshots": [market_to_row(market) for market in markets],
        "source_health": refresh_health,
    }
    rows_by_table["source_documents"] = context_rows["source_documents"]
    rows_by_table["evidence_items"] = context_rows["evidence_items"]
    rows_by_table["source_links"] = context_rows["source_links"]
    rows_by_table["source_health"] = [
        *rows_by_table["source_health"],
        *context_rows["source_health"],
    ]
    counts = {table: len(rows) for table, rows in rows_by_table.items()}
    if output_path is not None:
        write_json(output_path, {"counts": counts, "rows": rows_by_table})
    if dry_run:
        return counts

    client.insert_rows("pipeline_runs", rows_by_table["pipeline_runs"])
    client.insert_rows("market_snapshots", rows_by_table["market_snapshots"])
    client.upsert_rows(
        "source_health",
        rows_by_table["source_health"],
        on_conflict="source",
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
    return counts


def run_daily_refresh(
    *,
    forecast_path: Path = DATA_ROOT / "debug" / "forecasts.jsonl",
    market_path: Path = DATA_ROOT / "debug" / "market_snapshots.jsonl",
    outcome_path: Path = DATA_ROOT / "debug" / "forecast_outcomes.jsonl",
    performance_path: Path = DATA_ROOT / "debug" / "performance.json",
    supabase: bool = False,
    dry_run: bool = False,
    output_path: Path | None = None,
    client: SupabaseRestClient | None = None,
    market_fetcher: MarketFetcher | None = None,
    context_fetcher: ContextFetcher | None = None,
    base_url: str = KALSHI_PRODUCTION_BASE_URL,
) -> dict[str, int]:
    if supabase:
        client = client or SupabaseRestClient.from_env()
        if client is None:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required"
            )
        return _run_supabase_daily_refresh(
            client=client,
            market_fetcher=market_fetcher,
            context_fetcher=context_fetcher,
            base_url=base_url,
            dry_run=dry_run,
            output_path=output_path,
        )

    markets = read_jsonl(market_path) if market_path.exists() else []
    summary = {
        "market_snapshots": len(markets),
        "forecast_generation": "disabled_policy_desk",
        "forecast_outcomes": 0,
    }
    write_json(performance_path, summary)
    return {"market_snapshots": len(markets)}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Refresh policy context and optional read-only market snapshots."
    )
    parser.add_argument(
        "--supabase",
        action="store_true",
        help="Write policy context, source health, and optional market snapshots.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-path")
    parser.add_argument("--base-url", default=KALSHI_PRODUCTION_BASE_URL)
    parser.add_argument(
        "--forecast-path",
        default=str(DATA_ROOT / "debug" / "forecasts.jsonl"),
        help="Deprecated compatibility option; forecasts are not read.",
    )
    parser.add_argument(
        "--market-path", default=str(DATA_ROOT / "debug" / "market_snapshots.jsonl")
    )
    parser.add_argument(
        "--outcome-path",
        default=str(DATA_ROOT / "debug" / "forecast_outcomes.jsonl"),
        help="Deprecated compatibility option; forecast outcomes are not written.",
    )
    parser.add_argument(
        "--performance-path", default=str(DATA_ROOT / "debug" / "performance.json")
    )
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = build_arg_parser().parse_args()
    counts = run_daily_refresh(
        forecast_path=Path(args.forecast_path),
        market_path=Path(args.market_path),
        outcome_path=Path(args.outcome_path),
        performance_path=Path(args.performance_path),
        supabase=args.supabase,
        dry_run=args.dry_run,
        output_path=Path(args.output_path) if args.output_path else None,
        base_url=args.base_url,
    )
    LOGGER.info("Daily refresh counts: %s", counts)


if __name__ == "__main__":
    main()
