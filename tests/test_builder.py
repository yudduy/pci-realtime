from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from pci_realtime.pci.builder import (
    BASELINE_WEEK,
    SCHEMA_C_COLUMNS,
    build_weekly_index,
    load_baseline,
    rebuild_pci_weekly,
)


def _scored_row(
    *,
    doc_id: str = "federal_register:test",
    provision: str = "30D",
    week: str = "2024-W44",
    specificity_delta: float = 0.6,
    durability_delta: float = 0.0,
    enforceability_delta: float = 0.3,
) -> dict[str, object]:
    return {
        "doc_id": doc_id,
        "provision": provision,
        "week": week,
        "specificity_delta": specificity_delta,
        "durability_delta": durability_delta,
        "enforceability_delta": enforceability_delta,
    }


def test_build_weekly_index_applies_sticky_weekly_updates() -> None:
    scored = pd.DataFrame([_scored_row()])

    weekly = build_weekly_index(
        scored,
        baseline=load_baseline(),
        end_week="2024-W45",
        updated_at=pd.Timestamp("2026-05-21T12:00:00Z"),
    )

    baseline_row = weekly[
        (weekly["week"] == BASELINE_WEEK) & (weekly["provision"] == "45X")
    ].iloc[0]
    update_row = weekly.query("week == '2024-W44' and provision == '30D'").iloc[0]
    sticky_row = weekly.query("week == '2024-W45' and provision == '30D'").iloc[0]

    assert baseline_row["pci"] == pytest.approx(4.67)
    assert update_row["specificity"] == pytest.approx(4.6)
    assert update_row["enforceability"] == pytest.approx(4.3)
    assert update_row["pci"] == pytest.approx(4.3)
    assert update_row["delta_this_week"] == pytest.approx(0.3)
    assert update_row["n_docs"] == 1
    assert sticky_row["pci"] == pytest.approx(update_row["pci"])
    assert sticky_row["delta_this_week"] == pytest.approx(0.0)
    assert sticky_row["n_docs"] == 0


def test_build_weekly_index_clips_dimensions_to_valid_range() -> None:
    scored = pd.DataFrame(
        [
            _scored_row(
                provision="45X",
                specificity_delta=2.0,
                durability_delta=2.0,
                enforceability_delta=2.0,
            )
        ]
    )

    weekly = build_weekly_index(scored, baseline=load_baseline(), end_week="2024-W44")
    row = weekly.query("week == '2024-W44' and provision == '45X'").iloc[0]

    assert row["specificity"] == pytest.approx(5.0)
    assert row["durability"] == pytest.approx(5.0)
    assert row["enforceability"] == pytest.approx(5.0)
    assert row["pci"] == pytest.approx(5.0)


def test_build_weekly_index_optional_decay_moves_toward_baseline() -> None:
    scored = pd.DataFrame(
        [
            _scored_row(
                specificity_delta=0.6,
                durability_delta=0.0,
                enforceability_delta=0.0,
            )
        ]
    )

    weekly = build_weekly_index(
        scored,
        baseline=load_baseline(),
        end_week="2024-W45",
        decay_rate=0.5,
    )

    update_row = weekly.query("week == '2024-W44' and provision == '30D'").iloc[0]
    decay_row = weekly.query("week == '2024-W45' and provision == '30D'").iloc[0]

    assert update_row["specificity"] == pytest.approx(4.6)
    assert update_row["pci"] == pytest.approx(4.2)
    assert decay_row["specificity"] == pytest.approx(4.3)
    assert decay_row["pci"] == pytest.approx(4.1)
    assert decay_row["delta_this_week"] == pytest.approx(-0.1)


def test_rebuild_pci_weekly_reads_scored_parquet(tmp_path: Path) -> None:
    scored_dir = tmp_path / "scored"
    scored_dir.mkdir()
    pd.DataFrame([_scored_row(provision="45V", enforceability_delta=0.3)]).drop(
        columns=["week"]
    ).to_parquet(scored_dir / "scored_2024-W44.parquet", index=False)
    output_path = tmp_path / "pci_weekly.parquet"

    result_path = rebuild_pci_weekly(
        scored_dir=scored_dir,
        baseline_path=Path("data/baseline/pci_baseline.csv"),
        output_path=output_path,
    )

    weekly = pd.read_parquet(result_path)
    row = weekly.query("week == '2024-W44' and provision == '45V'").iloc[0]

    assert result_path == output_path
    assert list(weekly.columns) == SCHEMA_C_COLUMNS
    assert row["pci"] == pytest.approx(4.43)
    assert row["delta_this_week"] == pytest.approx(0.1)
