from __future__ import annotations

import argparse
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pci_realtime.registry.context import build_context_rows
from pci_realtime.registry.evidence import utc_now_iso
from pci_realtime.registry.store import (
    UPSERT_CONFLICT_KEYS,
    SupabaseRestClient,
    write_json,
)


LOGGER = logging.getLogger(__name__)
ContextFetcher = Callable[[], dict[str, list[dict[str, Any]]]]


def _build_context_refresh_rows(
    context_fetcher: ContextFetcher | None = None,
) -> dict[str, list[dict[str, Any]]]:
    context_rows = (
        context_fetcher() if context_fetcher is not None else build_context_rows()
    )
    rows_by_table = {
        "source_documents": context_rows["source_documents"],
        "evidence_items": context_rows["evidence_items"],
        "source_links": context_rows["source_links"],
        "source_health": context_rows["source_health"],
    }
    return rows_by_table


def _build_pipeline_run(
    rows_by_table: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    return {
        "run_type": "daily_refresh",
        "status": "success",
        "source": "daily_refresh.py",
        "completed_at": utc_now_iso(),
        "metadata": {table: len(rows) for table, rows in rows_by_table.items()},
    }


def _write_context_refresh_rows(
    rows_by_table: dict[str, list[dict[str, Any]]],
    *,
    client: SupabaseRestClient,
) -> dict[str, Any]:
    client.upsert_rows(
        "source_documents",
        rows_by_table["source_documents"],
        on_conflict=UPSERT_CONFLICT_KEYS["source_documents"],
    )
    client.upsert_rows(
        "evidence_items",
        rows_by_table["evidence_items"],
        on_conflict=UPSERT_CONFLICT_KEYS["evidence_items"],
    )
    client.upsert_rows(
        "source_links",
        rows_by_table["source_links"],
        on_conflict=UPSERT_CONFLICT_KEYS["source_links"],
    )
    client.upsert_rows(
        "source_health",
        rows_by_table["source_health"],
        on_conflict=UPSERT_CONFLICT_KEYS["source_health"],
    )
    pipeline_run = _build_pipeline_run(rows_by_table)
    client.insert_rows("pipeline_runs", [pipeline_run])
    return pipeline_run


def run_daily_refresh(
    *,
    dry_run: bool = False,
    output_path: Path | None = None,
    client: SupabaseRestClient | None = None,
    context_fetcher: ContextFetcher | None = None,
) -> dict[str, int]:
    rows_by_table = _build_context_refresh_rows(context_fetcher)
    if not dry_run:
        client = client or SupabaseRestClient.from_env()
        if client is None:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required"
            )
        pipeline_run = _write_context_refresh_rows(rows_by_table, client=client)
    else:
        pipeline_run = _build_pipeline_run(rows_by_table)

    rows_by_table["pipeline_runs"] = [pipeline_run]
    counts = {table: len(rows) for table, rows in rows_by_table.items()}
    if output_path is not None:
        write_json(output_path, {"counts": counts, "rows": rows_by_table})
    return counts


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Refresh public policy context and source health in Supabase."
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-path")
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = build_arg_parser().parse_args()
    counts = run_daily_refresh(
        dry_run=args.dry_run,
        output_path=Path(args.output_path) if args.output_path else None,
    )
    LOGGER.info("Daily refresh counts: %s", counts)


if __name__ == "__main__":
    main()
