from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from conftest import TableSelectingSupabaseClient
from pci_realtime import service
from pci_realtime.service_errors import BadRequest, SupabaseUnavailable


EVENT_ID = "2026-W21:federal_register:45v-guidance:45V"
EVIDENCE_ID = "evidence:2026-W21:federal_register:45v-guidance:45V"
CHANGE_EVENT_KEYS = json.loads(
    (
        Path(__file__).resolve().parents[1] / "contracts" / "change-event-keys.json"
    ).read_text(encoding="utf-8")
)


def event_row() -> dict[str, Any]:
    return {
        "event_id": EVENT_ID,
        "provision": "45V",
        "provision_name": "Clean Hydrogen Production Credit",
        "week": "2026-W21",
        "week_start": "2026-05-18",
        "doc_id": "federal_register:45v-guidance",
        "doc_source": "federal_register",
        "agency": "Treasury Department",
        "title": "Clean hydrogen production credit guidance",
        "url": "https://www.federalregister.gov/documents/example",
        "pci_delta": -0.33,
        "dimension_deltas": {
            "specificity": -1,
            "durability": 0,
            "enforceability": 0,
        },
        "rationale": (
            "Treasury guidance narrows eligibility for the clean hydrogen credit."
        ),
        "confidence": 0.82,
        "prompt_version": "test",
        "scored_at": "2026-05-21T12:00:00+00:00",
        "created_at": "2026-05-21T12:00:00+00:00",
    }


def evidence_row() -> dict[str, Any]:
    return {
        "evidence_id": EVIDENCE_ID,
        "source_doc_id": "federal_register:45v-guidance",
        "provision": "45V",
        "provision_name": "Clean Hydrogen Production Credit",
        "evidence_type": "pci_scoring_rationale",
        "snippet": (
            "Treasury guidance narrows eligibility for the clean hydrogen credit."
        ),
        "normalized_signal": "-0.33 PCI",
        "score_dimension": "specificity",
        "confidence": 0.82,
        "extractor_version": "test",
        "created_at": "2026-05-21T12:00:00+00:00",
        "citation_quote": (
            "Treasury guidance narrows eligibility for the clean hydrogen credit."
        ),
        "citation_section": "Eligibility",
        "citation_page": None,
        "citation_url_fragment": None,
        "source": "federal_register",
        "source_name": "Federal Register",
        "source_type": "official_text",
        "source_title": "Clean hydrogen production credit guidance",
        "agency": "Treasury Department",
        "url": "https://www.federalregister.gov/documents/example",
        "canonical_url": "https://www.federalregister.gov/documents/example",
        "published_at": "2026-05-21T12:00:00+00:00",
        "fetched_at": "2026-05-21T12:00:00+00:00",
    }


def link_row() -> dict[str, Any]:
    return {
        "link_id": f"link:policy_events:{EVENT_ID}",
        "evidence_id": EVIDENCE_ID,
        "target_table": "policy_events",
        "target_id": EVENT_ID,
        "link_type": "primary_source",
        "created_at": "2026-05-21T12:00:00+00:00",
    }


def client_with_evidence() -> TableSelectingSupabaseClient:
    return TableSelectingSupabaseClient(
        {
            "v_policy_events": [event_row()],
            "v_source_links": [link_row()],
            "v_evidence_items": [evidence_row()],
        }
    )


def test_list_changes_filters_and_params(monkeypatch: pytest.MonkeyPatch) -> None:
    client = client_with_evidence()
    monkeypatch.setattr(service, "_read_client", lambda: client)

    payload = service.list_changes(
        since="2026-01-01",
        vertical="clean-hydrogen",
    )

    assert client.calls[0] == (
        "v_policy_events",
        "*",
        {
            "order": "created_at.desc.nullslast,event_id.asc",
            "limit": "50",
            "created_at": "gte.2026-01-01T00:00:00.000Z",
            "provision": "in.(45V)",
        },
    )
    assert client.calls[1] == (
        "v_source_links",
        "*",
        {
            "target_id": f'in.("{EVENT_ID}")',
            "target_table": "eq.policy_events",
        },
    )
    assert client.calls[2] == (
        "v_evidence_items",
        "*",
        {
            "evidence_id": f'in.("{EVIDENCE_ID}")',
            "order": "created_at.desc",
        },
    )
    assert payload["count"] == 1
    assert payload["since"] == "2026-01-01T00:00:00.000Z"


def test_list_changes_canonical_key_set(monkeypatch: pytest.MonkeyPatch) -> None:
    client = client_with_evidence()
    monkeypatch.setattr(service, "_read_client", lambda: client)

    change = service.list_changes()["changes"][0]

    assert set(change) == set(CHANGE_EVENT_KEYS["change"])
    assert set(change["provision"]) == set(CHANGE_EVENT_KEYS["provision"])
    assert set(change["source"]) == set(CHANGE_EVENT_KEYS["source"])
    assert (
        change["headline"]
        == "Clean Hydrogen: Clean hydrogen production credit guidance"
    )
    assert change["source"]["url"] == (
        "https://www.federalregister.gov/documents/example#:~:text="
        "Treasury%20guidance%20narrows%20eligibility%20for%20the%20clean%20"
        "hydrogen%20credit."
    )


def test_list_changes_rejects_bad_since() -> None:
    with pytest.raises(BadRequest, match="Invalid since 'bogus'"):
        service.list_changes(since="bogus")


@pytest.mark.parametrize("limit", [0, 501])
def test_list_changes_rejects_out_of_range_limit(limit: int) -> None:
    with pytest.raises(BadRequest, match="use an integer between 1 and 500"):
        service.list_changes(limit=limit)


def test_list_changes_strips_since_whitespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = client_with_evidence()
    monkeypatch.setattr(service, "_read_client", lambda: client)

    payload = service.list_changes(since=" 2026-01-01 ")

    assert payload["since"] == "2026-01-01T00:00:00.000Z"
    assert client.calls[0][2] == {
        "order": "created_at.desc.nullslast,event_id.asc",
        "limit": "50",
        "created_at": "gte.2026-01-01T00:00:00.000Z",
    }


def test_list_changes_rejects_unknown_vertical() -> None:
    with pytest.raises(BadRequest, match="advanced-manufacturing"):
        service.list_changes(vertical="geothermal")


def test_list_changes_requires_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "_read_client", lambda: None)

    with pytest.raises(SupabaseUnavailable):
        service.list_changes()


def test_list_changes_no_linked_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    event = event_row()
    client = TableSelectingSupabaseClient(
        {
            "v_policy_events": [event],
            "v_source_links": [],
        }
    )
    monkeypatch.setattr(service, "_read_client", lambda: client)

    change = service.list_changes()["changes"][0]

    assert change["source"]["url"] == event["url"]
    assert change["source"]["quote"] is None
    assert change["source"]["name"] == event["agency"]


def test_select_in_chunks_and_escapes_values() -> None:
    client = TableSelectingSupabaseClient({"v_test": [{"id": "row"}]})

    rows = service._select_in(
        client,
        "v_test",
        "event_id",
        ["one", "two", 'three"'],
        chunk_size=2,
    )

    assert rows == [{"id": "row"}, {"id": "row"}]
    assert client.calls == [
        (
            "v_test",
            "*",
            {"event_id": 'in.("one","two")'},
        ),
        (
            "v_test",
            "*",
            {"event_id": 'in.("three\\"")'},
        ),
    ]
