from __future__ import annotations

import argparse
import logging
import os
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from requests.exceptions import RequestException

from pci_realtime.config import (
    FEDERAL_REGISTER_TERMS,
    PROPUBLICA_CONGRESS_API_URL,
    REQUEST_TIMEOUT_SECONDS,
)
from pci_realtime.ingest.base import BaseIngestor, parse_date
from pci_realtime.ingest.base import infer_provisions_from_text
from pci_realtime.ingest.public_sources import (
    CONGRESS_GOV_KEY_ENV,
    CongressGovClient,
    compact_body,
)


LOGGER = logging.getLogger(__name__)
PROPUBLICA_KEY_ENV = "PROPUBLICA_CONGRESS_API_KEY"


def congress_number_for_year(year: int) -> int:
    return ((year - 1789) // 2) + 1


def congress_numbers_for_window(start_date: date, end_date: date) -> list[int]:
    return sorted(
        {
            congress_number_for_year(year)
            for year in range(start_date.year, end_date.year + 1)
        }
    )


def _parse_optional_date(value: str | None) -> date | None:
    if not value:
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def _document_date(
    bill: dict[str, Any], start_date: date, end_date: date
) -> date | None:
    for key in ["latest_major_action_date", "introduced_date"]:
        value = _parse_optional_date(bill.get(key))
        if value and start_date <= value <= end_date:
            return value
    return None


def _bill_body(bill: dict[str, Any]) -> str:
    parts = [
        bill.get("title"),
        bill.get("short_title"),
        bill.get("summary"),
        bill.get("summary_short"),
        bill.get("latest_major_action"),
        bill.get("primary_subject"),
        bill.get("committees"),
        bill.get("sponsor_name"),
    ]
    return " ".join(str(part) for part in parts if part)


class CongressIngestor(BaseIngestor):
    source = "congress"
    agency = "U.S. Congress"

    def __init__(
        self,
        api_key: str | None = None,
        session: requests.Session | None = None,
        ingested_at: pd.Timestamp | None = None,
    ) -> None:
        super().__init__(session=session, ingested_at=ingested_at)
        self.api_key = api_key or os.getenv(CONGRESS_GOV_KEY_ENV)
        self.propublica_api_key = os.getenv(PROPUBLICA_KEY_ENV)

    def collect_documents(
        self, start_date: date, end_date: date, fetch_bodies: bool = True
    ) -> pd.DataFrame:
        del fetch_bodies
        if self.api_key:
            return self._collect_congress_gov(start_date=start_date, end_date=end_date)
        if not self.propublica_api_key:
            LOGGER.warning(
                "%s is not set; skipping Congress ingest", CONGRESS_GOV_KEY_ENV
            )
            return self.enforce_schema([])

        LOGGER.warning(
            "%s is not set; falling back to ProPublica Congress API",
            CONGRESS_GOV_KEY_ENV,
        )
        return self._collect_propublica(start_date=start_date, end_date=end_date)

    def _collect_congress_gov(
        self, *, start_date: date, end_date: date
    ) -> pd.DataFrame:
        client = CongressGovClient(api_key=str(self.api_key), session=self.session)
        rows_by_doc_id: dict[str, dict[str, Any]] = {}
        try:
            summaries = client.summaries(start_date=start_date, end_date=end_date)
        except RequestException as exc:
            LOGGER.warning("Could not search Congress.gov summaries: %s", exc)
            if self.propublica_api_key:
                return self._collect_propublica(
                    start_date=start_date, end_date=end_date
                )
            return self.enforce_schema([])

        for summary in summaries:
            row = self._normalize_congress_gov_summary(
                summary=summary,
                client=client,
                start_date=start_date,
                end_date=end_date,
            )
            if row is not None:
                rows_by_doc_id[row["doc_id"]] = row
        return self.enforce_schema(rows_by_doc_id.values())

    def _normalize_congress_gov_summary(
        self,
        *,
        summary: dict[str, Any],
        client: CongressGovClient,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any] | None:
        doc_date = _parse_optional_date(
            summary.get("actionDate") or summary.get("updateDate")
        )
        if doc_date is None or not (start_date <= doc_date <= end_date):
            return None

        bill = summary.get("bill") or {}
        congress = bill.get("congress")
        bill_type = str(bill.get("type") or "").lower()
        number = bill.get("number")
        detail: dict[str, Any] = {}
        text_versions: list[dict[str, Any]] = []
        if congress and bill_type and number:
            try:
                detail = client.bill_detail(congress, bill_type, number)
                text_versions = client.bill_text_versions(congress, bill_type, number)
            except RequestException as exc:
                LOGGER.debug("Could not fetch bill detail/text metadata: %s", exc)

        title = (
            bill.get("title")
            or detail.get("title")
            or summary.get("title")
            or f"{bill_type.upper()} {number}"
        )
        sponsors = detail.get("sponsors") or []
        sponsor_names = [
            sponsor.get("fullName")
            for sponsor in sponsors
            if isinstance(sponsor, dict) and sponsor.get("fullName")
        ]
        text_urls = []
        for version in text_versions:
            for fmt in version.get("formats", []):
                if isinstance(fmt, dict) and fmt.get("url"):
                    text_urls.append(fmt["url"])
        body = compact_body(
            [
                title,
                summary.get("text"),
                summary.get("actionDesc"),
                detail.get("latestAction", {}).get("text")
                if isinstance(detail.get("latestAction"), dict)
                else "",
                detail.get("policyArea", {}).get("name")
                if isinstance(detail.get("policyArea"), dict)
                else "",
                " ".join(sponsor_names),
                " ".join(text_urls[:3]),
            ]
        )
        provisions = infer_provisions_from_text(body)
        if not provisions:
            return None

        native_id = f"{congress}-{bill_type}-{number}-{doc_date.isoformat()}"
        url = bill.get("url") or detail.get("url") or ""
        return self.build_record(
            source=self.source,
            native_id=native_id,
            date_value=doc_date,
            agency=self.agency,
            title=title,
            body=body,
            url=url,
            provisions_mentioned=provisions,
        )

    def _collect_propublica(self, *, start_date: date, end_date: date) -> pd.DataFrame:
        rows_by_doc_id: dict[str, dict[str, Any]] = {}
        for congress in congress_numbers_for_window(start_date, end_date):
            for term in FEDERAL_REGISTER_TERMS:
                for bill in self._search_bills(congress=congress, term=term):
                    row = self._normalize_bill(
                        bill=bill, start_date=start_date, end_date=end_date
                    )
                    if row is not None:
                        rows_by_doc_id[row["doc_id"]] = row
        return self.enforce_schema(rows_by_doc_id.values())

    def _search_bills(self, *, congress: int, term: str) -> list[dict[str, Any]]:
        url = f"{PROPUBLICA_CONGRESS_API_URL}/{congress}/bills/search.json"
        try:
            response = self.session.get(
                url,
                params={"query": term},
                headers={"X-API-Key": self.propublica_api_key},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except RequestException as exc:
            LOGGER.warning("Could not search Congress API for %r: %s", term, exc)
            return []

        payload = response.json()
        bills: list[dict[str, Any]] = []
        for result in payload.get("results", []):
            if isinstance(result, dict):
                bills.extend(result.get("bills", []))
        return bills

    def _normalize_bill(
        self, *, bill: dict[str, Any], start_date: date, end_date: date
    ) -> dict[str, Any] | None:
        doc_date = _document_date(bill, start_date=start_date, end_date=end_date)
        if doc_date is None:
            return None

        title = bill.get("short_title") or bill.get("title") or ""
        body = _bill_body(bill)
        provisions = infer_provisions_from_text(f"{title} {body}")
        if not provisions:
            return None

        native_id = bill.get("bill_id") or bill.get("bill_slug") or title
        url = bill.get("congressdotgov_url") or bill.get("govtrack_url") or ""
        return self.build_record(
            source=self.source,
            native_id=native_id,
            date_value=doc_date,
            agency=self.agency,
            title=title,
            body=body,
            url=url,
            provisions_mentioned=provisions,
        )


def collect_documents(
    start_date: date,
    end_date: date,
    fetch_bodies: bool = True,
    api_key: str | None = None,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    return CongressIngestor(api_key=api_key, session=session).collect_documents(
        start_date=start_date, end_date=end_date, fetch_bodies=fetch_bodies
    )


def run_window(
    start_date: date,
    end_date: date,
    output_dir: Path,
    fetch_bodies: bool = True,
    api_key: str | None = None,
) -> Path:
    return CongressIngestor(api_key=api_key).run_window(
        start_date=start_date,
        end_date=end_date,
        output_dir=output_dir,
        fetch_bodies=fetch_bodies,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch Congress API documents for the PCI monitor."
    )
    parser.add_argument(
        "--start-date", required=True, help="Inclusive start date in YYYY-MM-DD format."
    )
    parser.add_argument(
        "--end-date", required=True, help="Inclusive end date in YYYY-MM-DD format."
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where the weekly parquet will be written.",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help=f"Congress.gov API key. Defaults to ${CONGRESS_GOV_KEY_ENV}.",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    output_path = run_window(
        start_date=parse_date(args.start_date),
        end_date=parse_date(args.end_date),
        output_dir=Path(args.output_dir),
        api_key=args.api_key,
    )
    LOGGER.info("Wrote Congress parquet to: %s", output_path)


if __name__ == "__main__":
    main()
