from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from pci_realtime.config import PROJECT_ROOT, TRACKED_PROVISIONS
from pci_realtime.scoring.scorer import DELTA_COLUMNS, DocumentScorer


LOGGER = logging.getLogger(__name__)
CALIBRATION_PATH = PROJECT_ROOT / "data" / "fixtures" / "calibration_set_v1.csv"
CALIBRATION_REPORT_PATH = PROJECT_ROOT / "data" / "debug" / "scorer_calibration.md"


class CalibrationBlockedError(RuntimeError):
    pass


def _is_true(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def expand_provision_label(label: str) -> list[str]:
    label = str(label).strip()
    if label == "ALL":
        return list(TRACKED_PROVISIONS)
    provisions = [part.strip() for part in label.split("+")]
    invalid = sorted(set(provisions) - set(TRACKED_PROVISIONS))
    if invalid:
        msg = f"Invalid calibration provisions: {invalid}"
        raise ValueError(msg)
    return provisions


def load_verified_calibration(path: Path = CALIBRATION_PATH) -> pd.DataFrame:
    df = pd.read_csv(path)
    mask = df["verified"].apply(_is_true) & (
        df["scored_by"].astype(str).str.lower() == "yikai"
    )
    verified = df.loc[mask].copy()
    if verified.empty:
        msg = (
            "Calibration blocked: no rows have verified=TRUE and scored_by=yikai. "
            "Yikai-scored calibration rows are required before RMSE is meaningful."
        )
        raise CalibrationBlockedError(msg)
    return expand_calibration_rows(verified)


def expand_calibration_rows(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in df.to_dict("records"):
        for provision in expand_provision_label(str(row["provision"])):
            expanded = dict(row)
            expanded["provision"] = provision
            rows.append(expanded)
    return pd.DataFrame(rows)


def calibration_document(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "doc_id": f"calibration:{row['row_id']}",
        "date": row["date"],
        "source": "calibration",
        "agency": "",
        "title": row["doc_title"],
        "body": f"{row['doc_title']}\n\nNotes: {row.get('notes', '')}",
        "body_truncated": False,
        "url": row.get("url", ""),
        "provisions_mentioned": [row["provision"]],
    }


def calculate_rmse(expected: pd.DataFrame, predicted: pd.DataFrame) -> dict[str, float]:
    merged = expected.merge(
        predicted,
        on=["row_id", "provision"],
        suffixes=("_expected", "_predicted"),
    )
    if merged.empty:
        msg = "No overlapping calibration predictions to score"
        raise ValueError(msg)

    scores: dict[str, float] = {}
    for column in DELTA_COLUMNS:
        expected_column = f"{column}_expected"
        predicted_column = f"{column}_predicted"
        error = merged[predicted_column] - merged[expected_column]
        scores[column] = float((error.pow(2).mean()) ** 0.5)
    scores["overall"] = float(sum(scores.values()) / len(DELTA_COLUMNS))
    return scores


def write_report(
    scores: dict[str, float], output_path: Path = CALIBRATION_REPORT_PATH
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Calibration Report",
        "",
        "| Metric | RMSE |",
        "| --- | ---: |",
    ]
    lines.extend(f"| {name} | {value:.3f} |" for name, value in scores.items())
    lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def run_calibration(
    *,
    calibration_path: Path = CALIBRATION_PATH,
    output_path: Path = CALIBRATION_REPORT_PATH,
    runs: int = 5,
    scorer: DocumentScorer | None = None,
) -> Path:
    expected = load_verified_calibration(calibration_path)
    document_scorer = scorer or DocumentScorer()
    predictions: list[dict[str, Any]] = []

    for row in expected.to_dict("records"):
        run_rows = []
        for run_number in range(1, runs + 1):
            result = document_scorer.score_document(
                calibration_document(row),
                str(row["provision"]),
                cache_metadata={"calibration_run": run_number},
            )
            run_rows.append(result.to_row())
        averaged = {
            "row_id": row["row_id"],
            "provision": row["provision"],
        }
        for column in DELTA_COLUMNS:
            averaged[column] = float(
                sum(run_row[column] for run_row in run_rows) / len(run_rows)
            )
        predictions.append(averaged)

    scores = calculate_rmse(expected, pd.DataFrame(predictions))
    return write_report(scores, output_path=output_path)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run PCI scorer calibration.")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--calibration-path", default=str(CALIBRATION_PATH))
    parser.add_argument("--output-path", default=str(CALIBRATION_REPORT_PATH))
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = build_arg_parser().parse_args()
    try:
        report = run_calibration(
            calibration_path=Path(args.calibration_path),
            output_path=Path(args.output_path),
            runs=args.runs,
        )
    except CalibrationBlockedError as exc:
        LOGGER.warning("%s", exc)
        return
    LOGGER.info("Wrote calibration report to %s", report)


if __name__ == "__main__":
    main()
