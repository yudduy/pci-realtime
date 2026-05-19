from __future__ import annotations

import pandas as pd
import pytest

from pci_realtime.config import TRACKED_PROVISIONS
from pci_realtime.scoring.calibrate import (
    CalibrationBlockedError,
    calculate_rmse,
    expand_calibration_rows,
    expand_provision_label,
    load_verified_calibration,
)


def test_expand_provision_label_handles_all_and_joined_labels() -> None:
    assert expand_provision_label("ALL") == list(TRACKED_PROVISIONS)
    assert expand_provision_label("45X+45V") == ["45X", "45V"]


def test_load_verified_calibration_blocks_without_yikai_rows(tmp_path) -> None:
    path = tmp_path / "calibration.csv"
    pd.DataFrame(
        [
            {
                "row_id": 1,
                "date": "2024-01-01",
                "provision": "45X",
                "doc_title": "x",
                "url": "",
                "specificity_delta": 0.0,
                "durability_delta": 0.0,
                "enforceability_delta": 0.0,
                "confidence": "medium",
                "notes": "",
                "scored_by": "starter",
                "verified": False,
            }
        ]
    ).to_csv(path, index=False)

    with pytest.raises(CalibrationBlockedError):
        load_verified_calibration(path)


def test_expand_calibration_rows_splits_joined_provisions() -> None:
    expanded = expand_calibration_rows(
        pd.DataFrame(
            [
                {
                    "row_id": 1,
                    "provision": "45X+45V",
                    "specificity_delta": 0.1,
                    "durability_delta": 0.2,
                    "enforceability_delta": 0.3,
                }
            ]
        )
    )

    assert expanded["provision"].tolist() == ["45X", "45V"]


def test_calculate_rmse_by_dimension() -> None:
    expected = pd.DataFrame(
        [
            {
                "row_id": 1,
                "provision": "45X",
                "specificity_delta": 1.0,
                "durability_delta": 0.0,
                "enforceability_delta": -1.0,
            }
        ]
    )
    predicted = pd.DataFrame(
        [
            {
                "row_id": 1,
                "provision": "45X",
                "specificity_delta": 0.5,
                "durability_delta": 0.5,
                "enforceability_delta": -0.5,
            }
        ]
    )

    scores = calculate_rmse(expected, predicted)

    assert scores["specificity_delta"] == pytest.approx(0.5)
    assert scores["durability_delta"] == pytest.approx(0.5)
    assert scores["enforceability_delta"] == pytest.approx(0.5)
    assert scores["overall"] == pytest.approx(0.5)
