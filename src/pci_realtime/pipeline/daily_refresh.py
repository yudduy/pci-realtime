from __future__ import annotations

import argparse
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pci_realtime.config import DATA_ROOT
from pci_realtime.forecast_registry.context import build_context_rows
from pci_realtime.forecast_registry.engine import (
    build_outcomes,
    compute_forecast_metrics,
    utc_now_iso,
)
from pci_realtime.forecast_registry.evidence import source_health_row
from pci_realtime.forecast_registry.kalshi import (
    KALSHI_PRODUCTION_BASE_URL,
    KalshiClient,
    parse_market_snapshot,
    read_jsonl,
)
from pci_realtime.forecast_registry.polymarket import (
    PolymarketClient,
    parse_polymarket_snapshot,
)
from pci_realtime.forecast_registry.store import (
    SupabaseRestClient,
    market_to_row,
    outcome_to_row,
    write_json,
    write_jsonl,
)


LOGGER = logging.getLogger(__name__)
MarketFetcher = Callable[[list[dict[str, Any]]], list[dict[str, Any]]]
ContextFetcher = Callable[[], dict[str, list[dict[str, Any]]]]


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _forecast_from_supabase_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "forecast_id": row["forecast_id"],
        "venue": row.get("venue") or "kalshi",
        "market_ticker": row["market_ticker"],
        "market_probability": _as_float(row.get("market_probability")),
        "rule_probability": _as_float(row.get("pci_rule_probability")),
        "model_probability": _as_float(row.get("model_probability")),
    }


def _fetch_current_market_snapshots(
    forecasts: list[dict[str, Any]],
    *,
    base_url: str,
) -> list[dict[str, Any]]:
    tickers = sorted(
        {
            str(forecast.get("market_ticker") or "")
            for forecast in forecasts
            if str(forecast.get("venue") or "kalshi") == "kalshi"
        }
    )
    tickers = [ticker for ticker in tickers if ticker]
    generated_at = utc_now_iso()
    snapshots: list[dict[str, Any]] = []
    client = KalshiClient(base_url=base_url)
    try:
        for ticker in tickers:
            market = client.get_market(ticker)
            try:
                orderbook = client.get_orderbook(ticker, depth=20)
            except Exception as exc:  # noqa: BLE001 - snapshot can still refresh.
                LOGGER.debug("Could not refresh orderbook for %s: %s", ticker, exc)
                orderbook = None
            snapshots.append(
                parse_market_snapshot(
                    market,
                    orderbook=orderbook,
                    query_name="daily_refresh",
                    generated_at=generated_at,
                )
            )
    finally:
        client.close()
    polymarket_slugs = sorted(
        {
            str(forecast.get("market_ticker") or "")
            for forecast in forecasts
            if str(forecast.get("venue") or "") == "polymarket"
        }
    )
    poly_client = PolymarketClient()
    try:
        for slug in polymarket_slugs:
            market = poly_client.get_market_by_slug(slug)
            if market is None:
                continue
            snapshots.append(
                parse_polymarket_snapshot(market, generated_at=generated_at)
            )
    finally:
        poly_client.close()
    return snapshots


def _run_supabase_daily_refresh(
    *,
    client: SupabaseRestClient,
    market_fetcher: MarketFetcher | None = None,
    context_fetcher: ContextFetcher | None = None,
    base_url: str = KALSHI_PRODUCTION_BASE_URL,
    dry_run: bool = False,
    output_path: Path | None = None,
) -> dict[str, int]:
    forecasts = [
        _forecast_from_supabase_row(row)
        for row in client.select_rows(
            "forecasts",
            columns=(
                "forecast_id,venue,market_ticker,market_probability,"
                "pci_rule_probability,model_probability"
            ),
            params={"private_info_used": "eq.false"},
        )
    ]
    markets = (
        market_fetcher(forecasts)
        if market_fetcher is not None
        else _fetch_current_market_snapshots(forecasts, base_url=base_url)
    )
    outcomes = build_outcomes(forecasts=forecasts, markets=markets)
    existing_outcomes = client.select_rows(
        "forecast_outcomes",
        columns="outcome_id,forecast_id,settlement_value",
    )
    outcomes_for_metrics = {
        str(outcome.get("outcome_id") or ""): outcome
        for outcome in [*existing_outcomes, *outcomes]
        if outcome.get("outcome_id")
    }
    metrics = compute_forecast_metrics(
        forecasts=forecasts,
        outcomes=list(outcomes_for_metrics.values()),
        abstentions=[],
    )
    source_health = [
        source_health_row(
            source="kalshi",
            status="success",
            row_count=sum(1 for market in markets if market.get("venue") == "kalshi"),
            details={"refresh": "market snapshots and outcomes"},
        )
    ]
    polymarket_row_count = sum(
        1 for market in markets if market.get("venue") == "polymarket"
    )
    if polymarket_row_count:
        source_health.append(
            source_health_row(
                source="polymarket",
                status="success",
                row_count=polymarket_row_count,
                details={"refresh": "market snapshots"},
            )
        )

    rows_by_table = {
        "pipeline_runs": [
            {
                "run_type": "daily_refresh",
                "status": "success",
                "source": "daily_refresh.py",
                "completed_at": utc_now_iso(),
                "metadata": {
                    "forecasts": len(forecasts),
                    "markets_refreshed": len(markets),
                    "outcomes": len(outcomes),
                    "metrics": metrics,
                },
            }
        ],
        "market_snapshots": [market_to_row(market) for market in markets],
        "forecast_outcomes": [outcome_to_row(outcome) for outcome in outcomes],
        "source_health": source_health,
    }
    context_rows = (
        context_fetcher() if context_fetcher is not None else build_context_rows()
    )
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
        "forecast_outcomes",
        rows_by_table["forecast_outcomes"],
        on_conflict="outcome_id",
    )
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

    forecasts = read_jsonl(forecast_path)
    markets = read_jsonl(market_path)
    outcomes = build_outcomes(forecasts=forecasts, markets=markets)
    metrics = compute_forecast_metrics(
        forecasts=forecasts,
        outcomes=outcomes,
        abstentions=[],
    )
    write_jsonl(outcome_path, [outcome_to_row(outcome) for outcome in outcomes])
    write_json(performance_path, metrics)
    return {
        "forecasts": len(forecasts),
        "outcomes": len(outcomes),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Refresh forecast outcomes and metrics."
    )
    parser.add_argument(
        "--supabase",
        action="store_true",
        help="Read forecasts from Supabase, refresh Kalshi markets, and write outcomes.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-path")
    parser.add_argument("--base-url", default=KALSHI_PRODUCTION_BASE_URL)
    parser.add_argument(
        "--forecast-path", default=str(DATA_ROOT / "debug" / "forecasts.jsonl")
    )
    parser.add_argument(
        "--market-path", default=str(DATA_ROOT / "debug" / "market_snapshots.jsonl")
    )
    parser.add_argument(
        "--outcome-path", default=str(DATA_ROOT / "debug" / "forecast_outcomes.jsonl")
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
