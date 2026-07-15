from __future__ import annotations

import pytest

from conftest import RecordingSupabaseClient, SelectingSupabaseClient
from pci_realtime import service
from pci_realtime.config import UNCOVERED_VERTICALS, VERTICALS
from pci_realtime.registry.store import (
    UPSERT_CONFLICT_KEYS,
    build_seed_rows,
    write_supabase_rows,
)
from pci_realtime.service_errors import BadRequest


def test_seed_rows_include_verticals_and_preserve_fk_write_order() -> None:
    rows = build_seed_rows()

    assert [row["id"] for row in rows["verticals"]] == list(VERTICALS)
    assert rows["verticals"][0] == {
        "id": "advanced-manufacturing",
        "name": "Advanced Manufacturing",
        "coverage_note": (
            "Tracks the section 45X production credit only; excludes 48C, tariffs, "
            "and state incentives."
        ),
        "display_order": 1,
    }
    assert len(rows["vertical_provisions"]) == 6
    assert [
        row
        for row in rows["vertical_provisions"]
        if row["vertical_id"] == "clean-energy-finance"
    ] == [
        {
            "vertical_id": "clean-energy-finance",
            "provision_code": "50141",
            "weight": 1.0,
        },
        {
            "vertical_id": "clean-energy-finance",
            "provision_code": "50144",
            "weight": 1.0,
        },
    ]
    assert UPSERT_CONFLICT_KEYS["verticals"] == "id"
    assert UPSERT_CONFLICT_KEYS["vertical_provisions"] == "vertical_id,provision_code"

    rows["policy_events"] = []
    client = RecordingSupabaseClient()
    write_supabase_rows(rows, client=client)  # type: ignore[arg-type]

    tables = [table for _, table, _, _ in client.calls]
    assert tables[:3] == ["provisions", "verticals", "vertical_provisions"]


def test_clean_energy_finance_uses_weighted_provision_average(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(service, "_read_client", lambda: None)

    payload = service.list_verticals()
    finance = next(
        row for row in payload["verticals"] if row["id"] == "clean-energy-finance"
    )

    assert finance["provisions"] == ["50141", "50144"]
    assert finance["vertical_pci"] == 3.17
    assert finance["baseline_pci"] == 3.17


def test_list_verticals_reads_registry_in_display_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = SelectingSupabaseClient(
        [
            {
                "id": "clean-energy-finance",
                "name": "Clean Energy Finance",
                "coverage_note": "Finance coverage",
                "display_order": 5,
                "vertical_pci": 2.5,
                "baseline_pci": 3.17,
                "weekly_delta": -0.5,
                "as_of_week_start": "2026-07-13",
                "last_change_week_start": "2026-07-13",
                "provisions": ["50141", "50144"],
            },
            {
                "id": "advanced-manufacturing",
                "name": "Advanced Manufacturing",
                "coverage_note": "Manufacturing coverage",
                "display_order": 1,
                "vertical_pci": 4.25,
                "baseline_pci": 4.67,
                "weekly_delta": 0.0,
                "as_of_week_start": "2026-07-13",
                "last_change_week_start": "2026-06-29",
                "provisions": ["45X"],
            },
        ]
    )
    monkeypatch.setattr(service, "_read_client", lambda: client)

    payload = service.list_verticals()

    assert payload["source"] == "registry"
    assert [row["id"] for row in payload["verticals"]] == [
        "advanced-manufacturing",
        "clean-energy-finance",
    ]
    assert payload["uncovered"] == UNCOVERED_VERTICALS
    assert client.calls == [("v_vertical_pci", "*", {"order": "display_order.asc"})]


def test_list_verticals_falls_back_to_config_without_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(service, "_read_client", lambda: None)

    payload = service.list_verticals()

    assert payload["source"] == "baseline"
    assert [row["display_order"] for row in payload["verticals"]] == [1, 2, 3, 4, 5]
    assert all(row["weekly_delta"] == 0.0 for row in payload["verticals"])
    assert payload["uncovered"] == UNCOVERED_VERTICALS


def test_vertical_status_rejects_unknown_id() -> None:
    with pytest.raises(BadRequest, match="Unknown vertical 'geothermal'"):
        service.vertical_status("geothermal")
