from __future__ import annotations

from pathlib import Path

import pandas as pd

from pci_realtime.ingest.federal_register import (
    infer_provisions_from_text,
    is_allowed_agency,
    parse_date,
    query_documents_for_term,
)


def test_infer_provisions_from_text_detects_multiple_provisions() -> None:
    text = (
        "The guidance clarifies section 45V clean hydrogen production credit rules "
        "and also revises transferability mechanics for the section 30D clean vehicle credit."
    )
    assert infer_provisions_from_text(text) == ["30D", "45V"]


def test_is_allowed_agency_uses_federal_register_slugs() -> None:
    doc = {
        "agencies": [
            {"slug": "treasury-department", "name": "Treasury Department"},
            {"slug": "internal-revenue-service", "name": "Internal Revenue Service"},
        ]
    }
    assert is_allowed_agency(doc) is True


def test_is_allowed_agency_rejects_unrelated_agencies() -> None:
    doc = {
        "agencies": [
            {"slug": "transportation-department", "name": "Transportation Department"},
        ]
    }
    assert is_allowed_agency(doc) is False


def test_known_documents_are_captured_from_federal_register() -> None:
    fixture_path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "fixtures"
        / "federal_register_known_documents.csv"
    )
    fixture = pd.read_csv(fixture_path)

    for row in fixture.itertuples(index=False):
        results = query_documents_for_term(
            term=row.query_term,
            start_date=parse_date(row.start_date),
            end_date=parse_date(row.end_date),
        )
        captured = {doc.get("document_number"): doc for doc in results}
        assert row.document_number in captured, (
            f"Did not capture {row.document_number} for query term {row.query_term!r}"
        )

        title = captured[row.document_number].get("title", "")
        assert row.title_contains.lower() in title.lower()
