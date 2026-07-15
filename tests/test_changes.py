from __future__ import annotations

import re

import pytest

from conftest import TableSelectingSupabaseClient
from pci_realtime import service
from pci_realtime.service_errors import BadRequest


def test_list_changes_filters_and_resolves_linked_citation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = TableSelectingSupabaseClient(
        {
            "v_policy_events": [
                {
                    "event_id": "event:30D",
                    "provision": "30D",
                    "week_start": "2025-12-15",
                    "title": "Clean vehicle transition guidance",
                    "url": "https://www.irs.gov/old-guidance",
                    "pci_delta": -0.1,
                    "dimension_deltas": {
                        "specificity": 0,
                        "durability": -0.3,
                        "enforceability": 0,
                    },
                    "rationale": "The transition period changed.",
                    "created_at": "2025-12-16T00:00:00Z",
                },
                {
                    "event_id": "event:45V",
                    "provision": "45V",
                    "week_start": "2026-05-18",
                    "title": "Clean hydrogen production credit guidance",
                    "url": "https://example.com/event-fallback",
                    "pci_delta": -0.33,
                    "dimension_deltas": {
                        "specificity": -1,
                        "durability": 0,
                        "enforceability": 0,
                    },
                    "rationale": "Treasury narrowed credit eligibility.",
                    "prompt_version": "prompt-v2",
                    "schema_version": "schema-b-v1",
                    "method_version": "pci-v1",
                    "created_at": "2026-05-20T00:00:00Z",
                },
            ],
            "v_evidence_items": [
                {
                    "evidence_id": "evidence:45V",
                    "citation_quote": "Treasury narrowed hydrogen eligibility.",
                    "snippet": "Fallback snippet.",
                    "canonical_url": "https://www.federalregister.gov/example",
                    "url": "https://example.com/evidence-fallback",
                    "source_name": "Federal Register",
                    "published_at": "2026-05-19T14:00:00Z",
                    "created_at": "2026-05-20T00:00:00Z",
                }
            ],
            "v_source_links": [
                {
                    "evidence_id": "evidence:45V",
                    "target_table": "policy_events",
                    "target_id": "event:45V",
                    "created_at": "2026-05-20T00:00:00Z",
                }
            ],
        }
    )
    monkeypatch.setattr(service, "_read_client", lambda: client)

    payload = service.list_changes(
        since="2026-01-01",
        vertical="clean-hydrogen",
        limit=10,
    )

    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T.*Z", payload["as_of"])
    assert payload["count"] == 1
    assert payload["changes"] == [
        {
            "id": "event:45V",
            "date": "2026-05-18",
            "verticals": ["clean-hydrogen"],
            "provisions": ["45V"],
            "title": "Clean hydrogen production credit guidance",
            "summary": "Treasury narrowed credit eligibility.",
            "pci_delta": -0.33,
            "dimensions": {
                "specificity": -1,
                "durability": 0,
                "enforceability": 0,
            },
            "citation": {
                "url": (
                    "https://www.federalregister.gov/example"
                    "#:~:text=Treasury%20narrowed%20hydrogen%20eligibility."
                ),
                "quote": "Treasury narrowed hydrogen eligibility.",
                "source_name": "Federal Register",
                "published_at": "2026-05-19T14:00:00Z",
            },
            "method": {
                "schema_version": "schema-b-v1",
                "method_version": "pci-v1",
                "prompt_version": "prompt-v2",
            },
        }
    ]
    assert client.calls == [
        (
            "v_policy_events",
            "*",
            {"order": "week_start.desc,created_at.desc"},
        ),
        ("v_evidence_items", "*", {"order": "created_at.desc"}),
        ("v_source_links", "*", {"order": "created_at.desc"}),
    ]


def test_list_changes_rejects_unknown_vertical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(service, "_read_client", lambda: None)

    with pytest.raises(BadRequest, match="Unknown vertical 'geothermal'"):
        service.list_changes(vertical="geothermal")
