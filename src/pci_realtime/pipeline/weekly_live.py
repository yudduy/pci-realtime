from __future__ import annotations

import argparse
import logging
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from pci_realtime.config import PROCESSED_DATA_ROOT, RAW_DATA_ROOT
from pci_realtime.forecast_registry.engine import (
    build_abstentions,
    build_forecasts,
    build_trade_proposals,
    compute_forecast_metrics,
    generate_signals,
    match_signals_to_markets,
)
from pci_realtime.forecast_registry.kalshi import (
    fetch_market_snapshots,
    snapshots_from_fixture,
)
from pci_realtime.forecast_registry.store import (
    SupabaseRestClient,
    build_seed_rows,
    forecast_to_row,
    market_to_row,
    trade_proposal_to_row,
    write_json,
    write_supabase_rows as store_write_supabase_rows,
)
from pci_realtime.ingest.base import parse_date
from pci_realtime.ingest.congress import run_window as ingest_congress
from pci_realtime.ingest.federal_register import run_window as ingest_federal_register
from pci_realtime.ingest.omb import run_window as ingest_omb
from pci_realtime.ingest.treasury import run_window as ingest_treasury
from pci_realtime.pci.builder import (
    BASELINE_WEEK,
    build_weekly_index,
    load_scored_deltas,
    parse_iso_week,
)
from pci_realtime.scoring.scorer import run_week as score_week


LOGGER = logging.getLogger(__name__)
DEFAULT_INGEST_SOURCES = ("federal_register", "treasury", "irs", "omb", "congress")


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
    weekly: pd.DataFrame, *, events: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    event_ids: dict[tuple[str, str], list[str]] = {}
    for event in events:
        key = (str(event["week"]), str(event["provision"]))
        event_ids.setdefault(key, []).append(str(event["event_id"]))

    rows: list[dict[str, Any]] = []
    for item in weekly.to_dict("records"):
        week = str(item["week"])
        provision = str(item["provision"])
        ids = sorted(event_ids.get((week, provision), []))
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
    market_fixture_path: Path | None = None,
    fetch_markets: bool = False,
    query_file: Path = Path("config/policy_market_queries.yml"),
    run_id: str | None = None,
    ingest_sources: tuple[str, ...] = DEFAULT_INGEST_SOURCES,
) -> dict[str, list[dict[str, Any]]]:
    run_id = run_id or str(uuid.uuid4())
    scored_for_pci = load_scored_deltas(scored_dir)
    scored_events = _load_scored_event_frame(scored_dir, through_week=week)
    raw_docs = _load_raw_documents(raw_root)
    policy_events = _policy_events_from_scored(scored_events, raw_docs=raw_docs)
    signal_events = [
        event
        for event in policy_events
        if abs(float(event.get("pci_delta") or 0.0)) > 0
    ]
    signals = generate_signals(signal_events)

    weekly = build_weekly_index(scored_for_pci, end_week=week)
    weekly_rows = _weekly_table_rows(weekly, events=policy_events)

    market_scan: dict[str, int] = {
        "scanned": 0,
        "published": 0,
        "rejected_duplicate": 0,
        "rejected_query_keywords": 0,
        "rejected_not_policy_relevant": 0,
    }
    if market_fixture_path is not None:
        markets = snapshots_from_fixture(market_fixture_path, audit=market_scan)
    elif fetch_markets:
        markets = fetch_market_snapshots(query_file=query_file, audit=market_scan)
    else:
        markets = []

    matches = match_signals_to_markets(signals, markets)
    forecasts = build_forecasts(signals=signals, markets=markets, matches=matches)
    trade_proposals = build_trade_proposals(forecasts)
    abstentions = build_abstentions(signals=signals, matches=matches)
    metrics = compute_forecast_metrics(
        forecasts=forecasts,
        outcomes=[],
        abstentions=abstentions,
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
                "signals": len(signals),
                "markets": len(markets),
                "market_scan": market_scan,
                "matches": len(matches),
                "forecasts": len(forecasts),
                "trade_proposals": len(trade_proposals),
                "abstentions": len(abstentions),
                "metrics": metrics,
            },
        }
    ]

    return {
        "provisions": [_clean_row(row) for row in seed_rows["provisions"]],
        "pipeline_runs": [_clean_row(row) for row in pipeline_runs],
        "pci_weekly": weekly_rows,
        "policy_events": _policy_event_table_rows(policy_events),
        "market_snapshots": [market_to_row(market) for market in markets],
        "forecasts": [
            forecast_to_row(forecast, run_id=run_id) for forecast in forecasts
        ],
        "trade_proposals": [
            trade_proposal_to_row(proposal, run_id=run_id)
            for proposal in trade_proposals
        ],
        "forecast_outcomes": [],
    }


def run_official_ingest(
    *,
    start_date: date,
    end_date: date,
    raw_root: Path,
    fetch_bodies: bool,
    sources: tuple[str, ...] = DEFAULT_INGEST_SOURCES,
) -> None:
    for source in sources:
        if source == "federal_register":
            ingest_federal_register(
                start_date=start_date,
                end_date=end_date,
                output_dir=raw_root / "federal_register",
                fetch_bodies=fetch_bodies,
            )
        elif source == "treasury":
            ingest_treasury(
                start_date=start_date,
                end_date=end_date,
                output_dir=raw_root / "treasury",
                fetch_bodies=fetch_bodies,
                source="treasury",
            )
        elif source == "irs":
            ingest_treasury(
                start_date=start_date,
                end_date=end_date,
                output_dir=raw_root / "irs",
                fetch_bodies=fetch_bodies,
                source="irs",
            )
        elif source == "omb":
            ingest_omb(
                start_date=start_date,
                end_date=end_date,
                output_dir=raw_root / "omb",
                fetch_bodies=fetch_bodies,
            )
        elif source == "congress":
            ingest_congress(
                start_date=start_date,
                end_date=end_date,
                output_dir=raw_root / "congress",
                fetch_bodies=fetch_bodies,
            )
        else:
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
    market_fixture_path: Path | None = None,
    fetch_markets: bool = False,
    query_file: Path = Path("config/policy_market_queries.yml"),
    ingest_sources: tuple[str, ...] = DEFAULT_INGEST_SOURCES,
    dry_run: bool = False,
    output_path: Path | None = None,
) -> WeeklyLiveResult:
    week = _iso_week_from_date(start_date)
    run_id = str(uuid.uuid4())
    run_official_ingest(
        start_date=start_date,
        end_date=end_date,
        raw_root=raw_root,
        fetch_bodies=fetch_bodies,
        sources=ingest_sources,
    )
    score_week(
        week=week,
        raw_root=raw_root,
        output_dir=scored_dir,
        confirm_cost=confirm_cost,
    )

    rows_by_table = build_weekly_live_rows(
        week=week,
        raw_root=raw_root,
        scored_dir=scored_dir,
        market_fixture_path=market_fixture_path,
        fetch_markets=fetch_markets,
        query_file=query_file,
        run_id=run_id,
        ingest_sources=ingest_sources,
    )
    counts = {table: len(rows) for table, rows in rows_by_table.items()}
    if output_path is not None:
        write_json(
            output_path, {"run_id": run_id, "counts": counts, "rows": rows_by_table}
        )
    if not dry_run:
        client = SupabaseRestClient.from_env()
        if client is None:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required"
            )
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
    parser.add_argument("--market-fixture-path")
    parser.add_argument("--fetch-markets", action="store_true")
    parser.add_argument("--query-file", default="config/policy_market_queries.yml")
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
        market_fixture_path=Path(args.market_fixture_path)
        if args.market_fixture_path
        else None,
        fetch_markets=args.fetch_markets,
        query_file=Path(args.query_file),
        ingest_sources=tuple(args.ingest_source or DEFAULT_INGEST_SOURCES),
        dry_run=args.dry_run,
        output_path=Path(args.output_path) if args.output_path else None,
    )
    LOGGER.info("Weekly live run %s counts: %s", result.run_id, result.counts)


if __name__ == "__main__":
    main()
