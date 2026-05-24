from __future__ import annotations

import argparse
import logging
from pathlib import Path

from pci_realtime.config import DATA_ROOT
from pci_realtime.forecast_registry.store import (
    SupabaseRestClient,
    build_seed_rows,
    write_json,
    write_supabase_rows,
)


LOGGER = logging.getLogger(__name__)


def seed_supabase(*, dry_run: bool = False, output_path: Path | None = None) -> None:
    rows_by_table = build_seed_rows()
    if output_path is not None:
        write_json(output_path, rows_by_table)
    if dry_run:
        return
    client = SupabaseRestClient.from_env()
    if client is None:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
    rows_by_table.setdefault("policy_events", [])
    rows_by_table.setdefault("market_snapshots", [])
    rows_by_table.setdefault("forecasts", [])
    rows_by_table.setdefault("trade_proposals", [])
    rows_by_table.setdefault("forecast_outcomes", [])
    write_supabase_rows(rows_by_table, client=client)
    LOGGER.info("Seeded Supabase paper anchors")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Seed Supabase with real paper anchors for the lab demo."
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--output-path", default=str(DATA_ROOT / "public" / "seed_payload.json")
    )
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = build_arg_parser().parse_args()
    seed_supabase(dry_run=args.dry_run, output_path=Path(args.output_path))


if __name__ == "__main__":
    main()
