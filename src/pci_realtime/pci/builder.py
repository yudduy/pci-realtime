from __future__ import annotations

import argparse
import logging
import re
from datetime import date
from pathlib import Path
from typing import Iterable

import pandas as pd

from pci_realtime.config import PROCESSED_DATA_ROOT, PROJECT_ROOT, TRACKED_PROVISIONS


LOGGER = logging.getLogger(__name__)

BASELINE_WEEK = "2022-W33"
MIN_SCORE = 1.0
MAX_SCORE = 5.0
DIMENSION_COLUMNS = ["specificity", "durability", "enforceability"]
DELTA_COLUMNS = [f"{column}_delta" for column in DIMENSION_COLUMNS]
SCHEMA_B_REQUIRED_COLUMNS = [
    "doc_id",
    "provision",
    "specificity_delta",
    "durability_delta",
    "enforceability_delta",
]
SCHEMA_C_COLUMNS = [
    "provision",
    "week",
    "pci",
    "specificity",
    "durability",
    "enforceability",
    "n_docs",
    "delta_this_week",
    "updated_at",
]
ISO_WEEK_RE = re.compile(r"^(?P<year>\d{4})-W(?P<week>\d{2})$")
SCORED_FILE_RE = re.compile(r"^scored_(?P<week>\d{4}-W\d{2})\.parquet$")


def parse_iso_week(week: str) -> pd.Timestamp:
    match = ISO_WEEK_RE.match(str(week))
    if not match:
        msg = f"Invalid ISO week label: {week!r}"
        raise ValueError(msg)

    year = int(match.group("year"))
    week_number = int(match.group("week"))
    try:
        return pd.Timestamp(date.fromisocalendar(year, week_number, 1), tz="UTC")
    except ValueError as exc:
        msg = f"Invalid ISO week label: {week!r}"
        raise ValueError(msg) from exc


def format_iso_week(timestamp: pd.Timestamp) -> str:
    iso = timestamp.date().isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def iter_iso_weeks(start_week: str, end_week: str) -> Iterable[str]:
    current = parse_iso_week(start_week)
    end = parse_iso_week(end_week)
    if current > end:
        msg = f"start_week {start_week} must be <= end_week {end_week}"
        raise ValueError(msg)

    while current <= end:
        yield format_iso_week(current)
        current += pd.Timedelta(days=7)


def scored_week_from_path(path: Path) -> str:
    match = SCORED_FILE_RE.match(path.name)
    if not match:
        msg = f"Scored file name must match scored_YYYY-WW.parquet: {path.name}"
        raise ValueError(msg)
    week = match.group("week")
    parse_iso_week(week)
    return week


def _week_sort_key(week: str) -> pd.Timestamp:
    return parse_iso_week(str(week))


def _clip_score(value: float) -> float:
    return min(MAX_SCORE, max(MIN_SCORE, float(value)))


def _composite_pci(dimensions: dict[str, float]) -> float:
    return round(
        sum(float(dimensions[column]) for column in DIMENSION_COLUMNS)
        / len(DIMENSION_COLUMNS),
        2,
    )


def load_baseline(
    path: Path = PROJECT_ROOT / "data" / "baseline" / "pci_baseline.csv",
) -> pd.DataFrame:
    baseline = pd.read_csv(path)
    return enforce_baseline_schema(baseline)


def enforce_baseline_schema(baseline: pd.DataFrame) -> pd.DataFrame:
    required = ["provision", *DIMENSION_COLUMNS, "pci"]
    missing = [column for column in required if column not in baseline.columns]
    if missing:
        msg = f"Baseline missing required columns: {missing}"
        raise ValueError(msg)

    df = baseline.loc[:, required].copy()
    df["provision"] = df["provision"].astype(str)
    missing_provisions = sorted(set(TRACKED_PROVISIONS) - set(df["provision"]))
    extra_provisions = sorted(set(df["provision"]) - set(TRACKED_PROVISIONS))
    if missing_provisions or extra_provisions:
        msg = (
            "Baseline provisions do not match tracked provisions: "
            f"missing={missing_provisions}, extra={extra_provisions}"
        )
        raise ValueError(msg)

    for column in [*DIMENSION_COLUMNS, "pci"]:
        df[column] = pd.to_numeric(df[column], errors="raise").astype(float)
        out_of_range = ~df[column].between(MIN_SCORE, MAX_SCORE)
        if out_of_range.any():
            bad = df.loc[out_of_range, ["provision", column]].to_dict("records")
            msg = f"Baseline {column} outside [{MIN_SCORE}, {MAX_SCORE}]: {bad}"
            raise ValueError(msg)

    return df.set_index("provision").loc[list(TRACKED_PROVISIONS)].reset_index()


def load_scored_deltas(
    scored_dir: Path = PROCESSED_DATA_ROOT / "scored",
) -> pd.DataFrame:
    if not scored_dir.exists():
        return pd.DataFrame(columns=[*SCHEMA_B_REQUIRED_COLUMNS, "week"])

    frames: list[pd.DataFrame] = []
    for path in sorted(scored_dir.glob("scored_*.parquet")):
        week = scored_week_from_path(path)
        frame = pd.read_parquet(path)
        if frame.empty:
            continue
        frame = frame.copy()
        frame["week"] = week
        frames.append(frame)

    if not frames:
        return pd.DataFrame(columns=[*SCHEMA_B_REQUIRED_COLUMNS, "week"])
    return pd.concat(frames, ignore_index=True)


def enforce_scored_delta_schema(scored: pd.DataFrame) -> pd.DataFrame:
    if scored.empty:
        return pd.DataFrame(columns=[*SCHEMA_B_REQUIRED_COLUMNS, "week"])

    required = [*SCHEMA_B_REQUIRED_COLUMNS, "week"]
    missing = [column for column in required if column not in scored.columns]
    if missing:
        msg = f"Scored deltas missing required columns: {missing}"
        raise ValueError(msg)

    df = scored.loc[:, required].copy()
    df["doc_id"] = df["doc_id"].astype("string")
    df["provision"] = df["provision"].astype(str)
    invalid = sorted(set(df["provision"].dropna()) - set(TRACKED_PROVISIONS))
    if invalid:
        msg = f"Invalid scored provisions: {invalid}"
        raise ValueError(msg)

    df["week"] = df["week"].astype(str)
    for week in df["week"].dropna().unique():
        parse_iso_week(str(week))

    duplicates = df.duplicated(["doc_id", "provision", "week"])
    if duplicates.any():
        bad = df.loc[duplicates, ["doc_id", "provision", "week"]].to_dict("records")
        msg = f"Duplicate scored rows for (doc_id, provision, week): {bad}"
        raise ValueError(msg)

    for column in DELTA_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="raise").astype(float)
        out_of_range = ~df[column].between(-2.0, 2.0)
        if out_of_range.any():
            bad = df.loc[out_of_range, ["doc_id", "provision", "week", column]].to_dict(
                "records"
            )
            msg = f"{column} outside [-2.0, 2.0]: {bad}"
            raise ValueError(msg)

    return df


def aggregate_weekly_deltas(scored: pd.DataFrame) -> pd.DataFrame:
    df = enforce_scored_delta_schema(scored)
    if df.empty:
        return pd.DataFrame(columns=["week", "provision", *DELTA_COLUMNS, "n_docs"])

    grouped = (
        df.groupby(["week", "provision"], as_index=False)
        .agg(
            specificity_delta=("specificity_delta", "sum"),
            durability_delta=("durability_delta", "sum"),
            enforceability_delta=("enforceability_delta", "sum"),
            n_docs=("doc_id", "nunique"),
        )
    )
    grouped["_week_start"] = grouped["week"].map(_week_sort_key)
    grouped["_provision_order"] = grouped["provision"].map(
        {provision: idx for idx, provision in enumerate(TRACKED_PROVISIONS)}
    )
    return (
        grouped.sort_values(["_week_start", "_provision_order"])
        .drop(columns=["_week_start", "_provision_order"])
        .reset_index(drop=True)
    )


def enforce_schema_c(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return pd.DataFrame(columns=SCHEMA_C_COLUMNS)

    missing = [column for column in SCHEMA_C_COLUMNS if column not in rows.columns]
    if missing:
        msg = f"Schema C missing required columns: {missing}"
        raise ValueError(msg)

    df = rows.loc[:, SCHEMA_C_COLUMNS].copy()
    df["provision"] = df["provision"].astype(str)
    invalid = sorted(set(df["provision"].dropna()) - set(TRACKED_PROVISIONS))
    if invalid:
        msg = f"Invalid Schema C provisions: {invalid}"
        raise ValueError(msg)

    df["week"] = df["week"].astype(str)
    for week in df["week"].dropna().unique():
        parse_iso_week(str(week))

    duplicates = df.duplicated(["provision", "week"])
    if duplicates.any():
        bad = df.loc[duplicates, ["provision", "week"]].to_dict("records")
        msg = f"Duplicate Schema C rows: {bad}"
        raise ValueError(msg)

    for column in ["pci", *DIMENSION_COLUMNS]:
        df[column] = pd.to_numeric(df[column], errors="raise").astype(float)
        out_of_range = ~df[column].between(MIN_SCORE, MAX_SCORE)
        if out_of_range.any():
            bad = df.loc[out_of_range, ["provision", "week", column]].to_dict("records")
            msg = f"{column} outside [{MIN_SCORE}, {MAX_SCORE}]: {bad}"
            raise ValueError(msg)

    df["n_docs"] = pd.to_numeric(df["n_docs"], errors="raise").astype("int64")
    df["delta_this_week"] = pd.to_numeric(
        df["delta_this_week"], errors="raise"
    ).astype(float)
    df["updated_at"] = pd.to_datetime(df["updated_at"], utc=True)
    df["_week_start"] = df["week"].map(_week_sort_key)
    df["_provision_order"] = df["provision"].map(
        {provision: idx for idx, provision in enumerate(TRACKED_PROVISIONS)}
    )
    return (
        df.sort_values(["_week_start", "_provision_order"])
        .drop(columns=["_week_start", "_provision_order"])
        .reset_index(drop=True)
    )


def build_weekly_index(
    scored: pd.DataFrame,
    *,
    baseline: pd.DataFrame | None = None,
    start_week: str = BASELINE_WEEK,
    end_week: str | None = None,
    decay_rate: float = 0.0,
    updated_at: pd.Timestamp | None = None,
) -> pd.DataFrame:
    if not 0.0 <= decay_rate <= 1.0:
        msg = f"decay_rate must be in [0, 1], got {decay_rate}"
        raise ValueError(msg)

    baseline_df = (
        load_baseline() if baseline is None else enforce_baseline_schema(baseline)
    )
    weekly = aggregate_weekly_deltas(scored)
    if end_week is None:
        end_week = (
            max(weekly["week"], key=lambda value: _week_sort_key(str(value)))
            if not weekly.empty
            else start_week
        )

    start_ts = parse_iso_week(start_week)
    end_ts = parse_iso_week(end_week)
    if not weekly.empty:
        before_start = weekly["week"].map(_week_sort_key) < start_ts
        after_end = weekly["week"].map(_week_sort_key) > end_ts
        if before_start.any():
            bad = sorted(weekly.loc[before_start, "week"].unique())
            msg = f"Scored weeks precede start_week {start_week}: {bad}"
            raise ValueError(msg)
        weekly = weekly.loc[~after_end].copy()

    weekly_lookup = {
        (str(row["week"]), str(row["provision"])): row
        for row in weekly.to_dict("records")
    }
    baseline_by_provision = baseline_df.set_index("provision")
    current_dimensions = {
        provision: {
            column: float(baseline_by_provision.loc[provision, column])
            for column in DIMENSION_COLUMNS
        }
        for provision in TRACKED_PROVISIONS
    }
    last_pci = {
        provision: round(float(baseline_by_provision.loc[provision, "pci"]), 2)
        for provision in TRACKED_PROVISIONS
    }
    updated_at = updated_at or pd.Timestamp.now(tz="UTC")
    rows: list[dict[str, object]] = []

    for week in iter_iso_weeks(start_week, end_week):
        for provision in TRACKED_PROVISIONS:
            n_docs = 0
            if week != start_week:
                previous_pci = last_pci[provision]
                if decay_rate:
                    for column in DIMENSION_COLUMNS:
                        baseline_value = float(
                            baseline_by_provision.loc[provision, column]
                        )
                        current_value = current_dimensions[provision][column]
                        current_dimensions[provision][column] = baseline_value + (
                            current_value - baseline_value
                        ) * (1.0 - decay_rate)

                deltas = weekly_lookup.get((week, provision))
                if deltas is not None:
                    n_docs = int(deltas["n_docs"])
                    for column, delta_column in zip(
                        DIMENSION_COLUMNS, DELTA_COLUMNS, strict=True
                    ):
                        current_dimensions[provision][column] = _clip_score(
                            current_dimensions[provision][column]
                            + float(deltas[delta_column])
                        )

                pci = _composite_pci(current_dimensions[provision])
                delta_this_week = round(pci - previous_pci, 10)
                last_pci[provision] = pci
            else:
                pci = last_pci[provision]
                delta_this_week = 0.0

            rows.append(
                {
                    "provision": provision,
                    "week": week,
                    "pci": pci,
                    "specificity": round(
                        current_dimensions[provision]["specificity"], 10
                    ),
                    "durability": round(
                        current_dimensions[provision]["durability"], 10
                    ),
                    "enforceability": round(
                        current_dimensions[provision]["enforceability"], 10
                    ),
                    "n_docs": n_docs,
                    "delta_this_week": delta_this_week,
                    "updated_at": updated_at,
                }
            )

    return enforce_schema_c(pd.DataFrame(rows))


def rebuild_pci_weekly(
    *,
    scored_dir: Path = PROCESSED_DATA_ROOT / "scored",
    baseline_path: Path = PROJECT_ROOT / "data" / "baseline" / "pci_baseline.csv",
    output_path: Path = PROCESSED_DATA_ROOT / "pci_weekly.parquet",
    start_week: str = BASELINE_WEEK,
    end_week: str | None = None,
    decay_rate: float = 0.0,
) -> Path:
    scored = load_scored_deltas(scored_dir)
    baseline = load_baseline(baseline_path)
    weekly = build_weekly_index(
        scored,
        baseline=baseline,
        start_week=start_week,
        end_week=end_week,
        decay_rate=decay_rate,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    weekly.to_parquet(output_path, index=False)
    return output_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the weekly PCI time series.")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild from scored files.")
    parser.add_argument("--scored-dir", default=str(PROCESSED_DATA_ROOT / "scored"))
    parser.add_argument(
        "--baseline-path",
        default=str(PROJECT_ROOT / "data" / "baseline" / "pci_baseline.csv"),
    )
    parser.add_argument(
        "--output-path", default=str(PROCESSED_DATA_ROOT / "pci_weekly.parquet")
    )
    parser.add_argument("--start-week", default=BASELINE_WEEK)
    parser.add_argument("--end-week")
    parser.add_argument(
        "--decay-rate",
        type=float,
        default=0.0,
        help="Optional weekly decay toward baseline; 0.0 is the sticky default.",
    )
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = build_arg_parser().parse_args()
    if not args.rebuild:
        LOGGER.info(
            "--rebuild not provided; rebuilding is the only supported mode for now."
        )

    output_path = rebuild_pci_weekly(
        scored_dir=Path(args.scored_dir),
        baseline_path=Path(args.baseline_path),
        output_path=Path(args.output_path),
        start_week=args.start_week,
        end_week=args.end_week,
        decay_rate=args.decay_rate,
    )
    LOGGER.info("Wrote weekly PCI time series to %s", output_path)


if __name__ == "__main__":
    main()
