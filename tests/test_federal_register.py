from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest

from pci_realtime.ingest.federal_register import (
    FEDERAL_REGISTER_API_FIELDS,
    infer_provisions_from_text,
    is_access_limited_body,
    is_allowed_agency,
    normalize_document,
    parse_date,
    query_documents_for_term,
    build_query_params,
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


def test_query_params_request_api_text_fields() -> None:
    params = build_query_params(
        term="clean vehicle credit",
        start_date=parse_date("2026-05-18"),
        end_date=parse_date("2026-05-24"),
    )

    assert params["fields[]"] == list(FEDERAL_REGISTER_API_FIELDS)
    assert "raw_text_url" in params["fields[]"]
    assert "full_text_xml_url" in params["fields[]"]


def test_normalize_document_prefers_api_full_text_url() -> None:
    calls: list[str] = []
    raw_doc = {
        "document_number": "2026-10279",
        "publication_date": "2026-05-22",
        "title": "Agency Information Collection Activities; Comment Request on Clean Vehicle Credits",
        "abstract": "Short API abstract.",
        "excerpts": "API excerpt mentions section 30D.",
        "raw_text_url": "https://example.test/raw.txt",
        "html_url": "https://example.test/human-page",
        "agencies": [
            {"slug": "treasury-department", "name": "Treasury Department"},
            {"slug": "internal-revenue-service", "name": "Internal Revenue Service"},
        ],
    }

    class ApiTextSession:
        def get(self, url: str, **_kwargs: object) -> object:
            calls.append(url)

            class Response:
                text = "Full API text for clean vehicle credits under section 30D."

                def raise_for_status(self) -> None:
                    return None

            return Response()

    row = normalize_document(raw_doc, fetch_bodies=True, session=ApiTextSession())  # type: ignore[arg-type]

    assert calls == ["https://example.test/raw.txt"]
    assert row["body"] == "Full API text for clean vehicle credits under section 30D."
    assert "30D" in row["provisions_mentioned"]


def test_normalize_document_falls_back_to_api_text_when_html_is_blocked() -> None:
    raw_doc = {
        "document_number": "2026-10279",
        "publication_date": "2026-05-22",
        "title": "Agency Information Collection Activities; Comment Request on Clean Vehicle Credits",
        "abstract": "The IRS is inviting comments on a clean vehicle credit information collection.",
        "excerpts": (
            "Revenue Procedure 2022-42 covers clean vehicles eligible for credits "
            'under <span class="match">sections</span> <span class="match">30D</span>, 45W, and 25E.'
        ),
        "html_url": "https://example.test/doc",
        "agencies": [
            {"slug": "treasury-department", "name": "Treasury Department"},
            {"slug": "internal-revenue-service", "name": "Internal Revenue Service"},
        ],
    }

    class BlockedSession:
        def get(self, *_args: object, **_kwargs: object) -> object:
            class Response:
                text = (
                    "Request Access Due to aggressive automated scraping of "
                    "FederalRegister.gov. Please complete the CAPTCHA."
                )

                def raise_for_status(self) -> None:
                    return None

            return Response()

    row = normalize_document(raw_doc, fetch_bodies=True, session=BlockedSession())  # type: ignore[arg-type]

    assert is_access_limited_body(row["body"]) is False
    assert "30D" in row["provisions_mentioned"]
    assert "Request Access" not in row["body"]
    assert "Revenue Procedure 2022-42" in row["body"]


def test_known_documents_are_captured_from_federal_register() -> None:
    if os.getenv("PCI_RUN_NETWORK_TESTS") != "1":
        pytest.skip("Federal Register live API fixture check is opt-in.")

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
