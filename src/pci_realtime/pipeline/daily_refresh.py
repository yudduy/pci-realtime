from __future__ import annotations

import argparse
import logging
from pathlib import Path

from pci_realtime.config import DATA_ROOT
from pci_realtime.forecast_registry.engine import (
    build_outcomes,
    compute_forecast_metrics,
)
from pci_realtime.forecast_registry.kalshi import read_jsonl
from pci_realtime.forecast_registry.store import outcome_to_row, write_json, write_jsonl


LOGGER = logging.getLogger(__name__)


def run_daily_refresh(
    *,
    forecast_path: Path = DATA_ROOT / "debug" / "forecasts.jsonl",
    market_path: Path = DATA_ROOT / "debug" / "market_snapshots.jsonl",
    outcome_path: Path = DATA_ROOT / "debug" / "forecast_outcomes.jsonl",
    performance_path: Path = DATA_ROOT / "debug" / "performance.json",
) -> dict[str, int]:
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
    )
    LOGGER.info("Daily refresh counts: %s", counts)


if __name__ == "__main__":
    main()
