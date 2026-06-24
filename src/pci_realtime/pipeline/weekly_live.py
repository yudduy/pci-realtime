from __future__ import annotations

import argparse
import logging
import os
import time
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from pci_realtime.config import PROCESSED_DATA_ROOT, RAW_DATA_ROOT
from pci_realtime.forecast_registry.evidence import (
    evidence_rows_from_policy_events,
    source_document_rows_from_raw_docs,
    source_health_row,
    source_links_from_policy_events,
)
from pci_realtime.forecast_registry.store import (
    SupabaseRestClient,
    build_seed_rows,
    scored_delta_to_row,
    write_json,
    write_supabase_rows as store_write_supabase_rows,
)
from pci_realtime.ingest.base import parse_date
from pci_realtime.ingest.congress import (
    PROPUBLICA_KEY_ENV,
    run_window as ingest_congress,
)
from pci_realtime.ingest.federal_register import run_window as ingest_federal_register
from pci_realtime.ingest.omb import run_window as ingest_omb
from pci_realtime.ingest.public_sources import (
    CONGRESS_GOV_KEY_ENV,
    REGULATIONS_GOV_KEY_ENV,
    RegInfoIngestor,
    RegulationsGovIngestor,
    USASpendingIngestor,
)
from pci_realtime.ingest.treasury import run_window as ingest_treasury
from pci_realtime.pci.builder import (
    BASELINE_WEEK,
    build_weekly_index,
    load_scored_deltas,
    parse_iso_week,
)
from pci_realtime.scoring.scorer import SCHEMA_B_COLUMNS, run_week as score_week


LOGGER = logging.getLogger(__name__)
DEFAULT_INGEST_SOURCES = (
    "federal_register",
    "treasury",
    "irs",
    "omb",
    "congress",
    "regulations_gov",
    "reginfo",
    "usaspending",
)
CORE_POLICY_SOURCES = {"federal_register", "congress", "regulations_gov", "reginfo"}
KEYED_INGEST_SOURCES = {"regulations_gov": REGULATIONS_GOV_KEY_ENV}
SCORED_DELTA_COLUMNS = [*SCHEMA_B_COLUMNS, "week"]


@dataclass(frozen=True)
class WeeklyLiveResult:
    run_id: str
    counts: dict[str, int]
    rows_by_table: dict[str, list[dict[str, Any]]]


def _iso_week_from_date(value: date) -> str:
    iso = value.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _json_value(value: Any) -> Any:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, (list, dict, tuple, set)):
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_value(item) for item in value]
    return value


def _clean_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: _json_value(value) for key, value in row.items()}


def _load_raw_documents(raw_root: Path) -> dict[str, dict[str, Any]]:
    frames = [pd.read_parquet(path) for path in sorted(raw_root.glob("*/*.parquet"))]
    if not frames:
        return {}
    raw = pd.concat(frames, ignore_index=True)
    return {
        str(row["doc_id"]): _clean_row(dict(row))
        for row in raw.to_dict("records")
        if row.get("doc_id")
    }


def _load_scored_event_frame(scored_dir: Path, *, through_week: str) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    through_ts = parse_iso_week(through_week)
    for path in sorted(scored_dir.glob("scored_*.parquet")):
        week = path.stem.replace("scored_", "")
        if parse_iso_week(week) > through_ts:
            continue
        frame = pd.read_parquet(path)
        if frame.empty:
            continue
        frame = frame.copy()
        frame["week"] = week
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _empty_scored_delta_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=SCORED_DELTA_COLUMNS)


def _filter_scored_through_week(
    scored: pd.DataFrame, *, through_week: str
) -> pd.DataFrame:
    if scored.empty:
        return _empty_scored_delta_frame()
    through_ts = parse_iso_week(through_week)
    frame = scored.copy()
    frame["week"] = frame["week"].astype(str)
    frame = frame.loc[frame["week"].map(parse_iso_week) <= through_ts].copy()
    if frame.empty:
        return _empty_scored_delta_frame()
    return frame.loc[
        :, [column for column in SCORED_DELTA_COLUMNS if column in frame.columns]
    ]


def _combine_scored_delta_frames(*frames: pd.DataFrame) -> pd.DataFrame:
    non_empty = [
        frame.copy() for frame in frames if frame is not None and not frame.empty
    ]
    if not non_empty:
        return _empty_scored_delta_frame()
    combined = pd.concat(non_empty, ignore_index=True)
    for column in SCORED_DELTA_COLUMNS:
        if column not in combined.columns:
            combined[column] = None
    return (
        combined.loc[:, SCORED_DELTA_COLUMNS]
        .drop_duplicates(["week", "doc_id", "provision"], keep="last")
        .sort_values(["week", "doc_id", "provision"])
        .reset_index(drop=True)
    )


def _load_remote_scored_deltas(
    client: SupabaseRestClient | None, *, through_week: str
) -> pd.DataFrame:
    if client is None:
        return _empty_scored_delta_frame()
    rows = client.select_rows(
        "scored_deltas",
        columns=",".join(SCORED_DELTA_COLUMNS),
        params={"week": f"lte.{through_week}"},
    )
    if not rows:
        return _empty_scored_delta_frame()
    return _filter_scored_through_week(pd.DataFrame(rows), through_week=through_week)


def _scored_delta_table_rows(scored: pd.DataFrame) -> list[dict[str, Any]]:
    if scored.empty:
        return []
    return [
        scored_delta_to_row(_clean_row(row))
        for row in scored.to_dict("records")
        if row.get("week") and row.get("doc_id") and row.get("provision")
    ]


def _event_id(*, week: str, doc_id: str, provision: str) -> str:
    safe_doc_id = doc_id.replace("/", "_").replace(" ", "_")
    return f"{week}:{safe_doc_id}:{provision}"


def _policy_events_from_scored(
    scored: pd.DataFrame,
    *,
    raw_docs: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    if scored.empty:
        return []
    rows: list[dict[str, Any]] = []
    for item in scored.to_dict("records"):
        doc_id = str(item["doc_id"])
        provision = str(item["provision"])
        week = str(item["week"])
        raw = raw_docs.get(doc_id, {})
        dimension_deltas = {
            "specificity": float(item.get("specificity_delta") or 0.0),
            "durability": float(item.get("durability_delta") or 0.0),
            "enforceability": float(item.get("enforceability_delta") or 0.0),
        }
        pci_delta = round(sum(dimension_deltas.values()) / 3.0, 4)
        row = {
            "event_id": _event_id(week=week, doc_id=doc_id, provision=provision),
            "provision": provision,
            "provision_name": None,
            "week": week,
            "week_start": parse_iso_week(week).date(),
            "doc_id": doc_id,
            "doc_source": raw.get("source"),
            "agency": raw.get("agency"),
            "title": raw.get("title"),
            "url": raw.get("url"),
            "pci_delta": pci_delta,
            "dimension_deltas": dimension_deltas,
            "rationale": item.get("rationale"),
            "confidence": item.get("confidence"),
            "prompt_version": item.get("prompt_version"),
            "scored_at": item.get("scored_at"),
            "data_origin": "live_scored",
            "source_document": {
                "doc_id": doc_id,
                "source": raw.get("source"),
                "agency": raw.get("agency"),
                "title": raw.get("title"),
                "url": raw.get("url"),
            },
        }
        rows.append(_clean_row(row))
    return sorted(
        rows, key=lambda row: (row["week"], row["provision"], row["event_id"])
    )


def _policy_event_table_rows(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            key: value
            for key, value in event.items()
            if key not in {"schema_version", "source_document", "provision_name"}
        }
        for event in events
    ]


def _weekly_table_rows(
    weekly: pd.DataFrame,
    *,
    events: list[dict[str, Any]],
    scored_events: pd.DataFrame | None = None,
) -> list[dict[str, Any]]:
    event_ids: dict[tuple[str, str], list[str]] = {}
    for event in events:
        key = (str(event["week"]), str(event["provision"]))
        event_ids.setdefault(key, []).append(str(event["event_id"]))
    if scored_events is not None and not scored_events.empty:
        for item in scored_events.to_dict("records"):
            week = str(item["week"])
            provision = str(item["provision"])
            doc_id = str(item["doc_id"])
            key = (week, provision)
            event_id = _event_id(week=week, doc_id=doc_id, provision=provision)
            event_ids.setdefault(key, []).append(event_id)

    rows: list[dict[str, Any]] = []
    for item in weekly.to_dict("records"):
        week = str(item["week"])
        provision = str(item["provision"])
        ids = sorted(set(event_ids.get((week, provision), [])))
        n_docs = int(item.get("n_docs") or 0)
        if week == BASELINE_WEEK:
            data_origin = "paper_anchor"
        elif n_docs:
            data_origin = "live_scored"
        else:
            data_origin = "derived_stock"
        rows.append(
            _clean_row(
                {
                    "provision": provision,
                    "week": week,
                    "week_start": parse_iso_week(week).date(),
                    "pci": item["pci"],
                    "specificity": item["specificity"],
                    "durability": item["durability"],
                    "enforceability": item["enforceability"],
                    "n_docs": n_docs,
                    "delta_this_week": item["delta_this_week"],
                    "data_origin": data_origin,
                    "source_event_ids": ids,
                    "provenance_status": "complete"
                    if ids or not n_docs
                    else "missing_source_documents",
                    "updated_at": item["updated_at"],
                }
            )
        )
    return rows


def build_weekly_live_rows(
    *,
    week: str,
    raw_root: Path = RAW_DATA_ROOT,
    scored_dir: Path = PROCESSED_DATA_ROOT / "scored",
    historical_scored: pd.DataFrame | None = None,
    run_id: str | None = None,
    ingest_sources: tuple[str, ...] = DEFAULT_INGEST_SOURCES,
    source_health: list[dict[str, Any]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    run_id = run_id or str(uuid.uuid4())
    local_scored = _filter_scored_through_week(
        load_scored_deltas(scored_dir), through_week=week
    )
    historical_scored = (
        _filter_scored_through_week(historical_scored, through_week=week)
        if historical_scored is not None
        else _empty_scored_delta_frame()
    )
    scored_for_pci = _combine_scored_delta_frames(historical_scored, local_scored)
    scored_events = scored_for_pci
    raw_docs = _load_raw_documents(raw_root)
    policy_events = _policy_events_from_scored(scored_events, raw_docs=raw_docs)

    weekly = build_weekly_index(scored_for_pci, end_week=week)
    weekly_rows = _weekly_table_rows(
        weekly, events=policy_events, scored_events=scored_events
    )

    seed_rows = build_seed_rows()
    pipeline_runs = [
        {
            "run_id": run_id,
            "run_type": "weekly",
            "status": "success",
            "source": "weekly_live.py",
            "metadata": {
                "week": week,
                "ingest_sources": list(ingest_sources),
                "policy_events": len(policy_events),
            },
        }
    ]

    return {
        "provisions": [_clean_row(row) for row in seed_rows["provisions"]],
        "pipeline_runs": [_clean_row(row) for row in pipeline_runs],
        "scored_deltas": _scored_delta_table_rows(scored_for_pci),
        "pci_weekly": weekly_rows,
        "policy_events": _policy_event_table_rows(policy_events),
        "market_snapshots": [],
        "market_discovery_candidates": [],
        "source_documents": [*source_document_rows_from_raw_docs(raw_docs)],
        "evidence_items": [*evidence_rows_from_policy_events(policy_events)],
        "source_links": [
            *source_links_from_policy_events(policy_events),
        ],
        "source_health": source_health or [],
        "forecasts": [],
        "trade_proposals": [],
        "forecast_outcomes": [],
    }


def run_official_ingest(
    *,
    start_date: date,
    end_date: date,
    raw_root: Path,
    fetch_bodies: bool,
    sources: tuple[str, ...] = DEFAULT_INGEST_SOURCES,
) -> list[dict[str, Any]]:
    health_rows: list[dict[str, Any]] = []
    successful_core_sources: set[str] = set()
    for source in sources:
        if (
            source == "congress"
            and not os.getenv(CONGRESS_GOV_KEY_ENV)
            and not os.getenv(PROPUBLICA_KEY_ENV)
        ):
            health_rows.append(
                source_health_row(
                    source=source,
                    status="disabled",
                    row_count=0,
                    error_class="MissingApiKey",
                    error_summary=(
                        f"{CONGRESS_GOV_KEY_ENV} is not configured; "
                        f"{PROPUBLICA_KEY_ENV} fallback is also missing"
                    ),
                )
            )
            continue
        key_env = KEYED_INGEST_SOURCES.get(source)
        if key_env and not os.getenv(key_env):
            health_rows.append(
                source_health_row(
                    source=source,
                    status="disabled",
                    row_count=0,
                    error_class="MissingApiKey",
                    error_summary=f"{key_env} is not configured",
                )
            )
            continue
        started = time.monotonic()
        try:
            path = _run_single_ingest_source(
                source=source,
                start_date=start_date,
                end_date=end_date,
                raw_root=raw_root,
                fetch_bodies=fetch_bodies,
            )
            row_count = _parquet_row_count(path)
            latency_ms = int((time.monotonic() - started) * 1000)
            health_rows.append(
                source_health_row(
                    source=source,
                    status="success",
                    row_count=row_count,
                    latency_ms=latency_ms,
                    details={
                        "window_start": start_date.isoformat(),
                        "window_end": end_date.isoformat(),
                    },
                )
            )
            if source in CORE_POLICY_SOURCES:
                successful_core_sources.add(source)
        except ValueError:
            raise
        except Exception as exc:  # noqa: BLE001 - source failures should degrade.
            latency_ms = int((time.monotonic() - started) * 1000)
            LOGGER.warning("Source %s failed and will be skipped: %s", source, exc)
            health_rows.append(
                source_health_row(
                    source=source,
                    status="failed",
                    latency_ms=latency_ms,
                    error_class=type(exc).__name__,
                    error_summary=str(exc),
                )
            )

    requested_core_sources = CORE_POLICY_SOURCES.intersection(sources)
    if requested_core_sources and not successful_core_sources:
        msg = (
            f"All core official policy sources failed: {sorted(requested_core_sources)}"
        )
        raise RuntimeError(msg)
    return health_rows


def _parquet_row_count(path: Path) -> int:
    if not path.exists():
        return 0
    return len(pd.read_parquet(path, columns=["doc_id"]))


def _run_single_ingest_source(
    *,
    source: str,
    start_date: date,
    end_date: date,
    raw_root: Path,
    fetch_bodies: bool,
) -> Path:
    if source == "federal_register":
        return ingest_federal_register(
            start_date=start_date,
            end_date=end_date,
            output_dir=raw_root / "federal_register",
            fetch_bodies=fetch_bodies,
        )
    if source == "treasury":
        return ingest_treasury(
            start_date=start_date,
            end_date=end_date,
            output_dir=raw_root / "treasury",
            fetch_bodies=fetch_bodies,
            source="treasury",
        )
    if source == "irs":
        return ingest_treasury(
            start_date=start_date,
            end_date=end_date,
            output_dir=raw_root / "irs",
            fetch_bodies=fetch_bodies,
            source="irs",
        )
    if source == "omb":
        return ingest_omb(
            start_date=start_date,
            end_date=end_date,
            output_dir=raw_root / "omb",
            fetch_bodies=fetch_bodies,
        )
    if source == "congress":
        return ingest_congress(
            start_date=start_date,
            end_date=end_date,
            output_dir=raw_root / "congress",
            fetch_bodies=fetch_bodies,
        )
    if source == "regulations_gov":
        return RegulationsGovIngestor().run_window(
            start_date=start_date,
            end_date=end_date,
            output_dir=raw_root / "regulations_gov",
            fetch_bodies=fetch_bodies,
        )
    if source == "reginfo":
        return RegInfoIngestor().run_window(
            start_date=start_date,
            end_date=end_date,
            output_dir=raw_root / "reginfo",
            fetch_bodies=fetch_bodies,
        )
    if source == "usaspending":
        return USASpendingIngestor().run_window(
            start_date=start_date,
            end_date=end_date,
            output_dir=raw_root / "usaspending",
            fetch_bodies=fetch_bodies,
        )
    msg = f"Unsupported ingest source: {source}"
    raise ValueError(msg)


def write_supabase_rows(
    rows_by_table: dict[str, list[dict[str, Any]]],
    *,
    client: SupabaseRestClient,
) -> None:
    store_write_supabase_rows(rows_by_table, client=client)


def run_weekly_live(
    *,
    start_date: date,
    end_date: date,
    raw_root: Path = RAW_DATA_ROOT,
    scored_dir: Path = PROCESSED_DATA_ROOT / "scored",
    fetch_bodies: bool = True,
    confirm_cost: bool = False,
    ingest_sources: tuple[str, ...] = DEFAULT_INGEST_SOURCES,
    dry_run: bool = False,
    output_path: Path | None = None,
) -> WeeklyLiveResult:
    week = _iso_week_from_date(start_date)
    run_id = str(uuid.uuid4())
    client = None if dry_run else SupabaseRestClient.from_env()
    if not dry_run and client is None:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")

    source_health = (
        run_official_ingest(
            start_date=start_date,
            end_date=end_date,
            raw_root=raw_root,
            fetch_bodies=fetch_bodies,
            sources=ingest_sources,
        )
        or []
    )
    score_week(
        week=week,
        raw_root=raw_root,
        output_dir=scored_dir,
        confirm_cost=confirm_cost,
    )
    historical_scored = _load_remote_scored_deltas(client, through_week=week)

    rows_by_table = build_weekly_live_rows(
        week=week,
        raw_root=raw_root,
        scored_dir=scored_dir,
        historical_scored=historical_scored,
        run_id=run_id,
        ingest_sources=ingest_sources,
        source_health=source_health,
    )
    counts = {table: len(rows) for table, rows in rows_by_table.items()}
    if output_path is not None:
        write_json(
            output_path, {"run_id": run_id, "counts": counts, "rows": rows_by_table}
        )
    if not dry_run:
        assert client is not None
        write_supabase_rows(rows_by_table, client=client)
    return WeeklyLiveResult(run_id=run_id, counts=counts, rows_by_table=rows_by_table)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the live weekly backend loop and write Supabase rows."
    )
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--raw-root", default=str(RAW_DATA_ROOT))
    parser.add_argument("--scored-dir", default=str(PROCESSED_DATA_ROOT / "scored"))
    parser.add_argument("--confirm-cost", action="store_true")
    parser.add_argument(
        "--ingest-source",
        action="append",
        choices=DEFAULT_INGEST_SOURCES,
        help=(
            "Official document source to ingest. May be repeated. "
            "Defaults to all official sources."
        ),
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-path")
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = build_arg_parser().parse_args()
    result = run_weekly_live(
        start_date=parse_date(args.start_date),
        end_date=parse_date(args.end_date),
        raw_root=Path(args.raw_root),
        scored_dir=Path(args.scored_dir),
        fetch_bodies=True,
        confirm_cost=args.confirm_cost,
        ingest_sources=tuple(args.ingest_source or DEFAULT_INGEST_SOURCES),
        dry_run=args.dry_run,
        output_path=Path(args.output_path) if args.output_path else None,
    )
    LOGGER.info("Weekly live run %s counts: %s", result.run_id, result.counts)


if __name__ == "__main__":
    main()
