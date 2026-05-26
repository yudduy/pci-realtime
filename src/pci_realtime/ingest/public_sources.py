from __future__ import annotations

import logging
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable

import pandas as pd
import requests
from requests.exceptions import RequestException

from pci_realtime.config import FEDERAL_REGISTER_TERMS, REQUEST_TIMEOUT_SECONDS
from pci_realtime.ingest.base import (
    BaseIngestor,
    infer_provisions_from_text,
)


LOGGER = logging.getLogger(__name__)

CONGRESS_GOV_KEY_ENV = "CONGRESS_GOV_API_KEY"
GOVINFO_KEY_ENV = "GOVINFO_API_KEY"
REGULATIONS_GOV_KEY_ENV = "REGULATIONS_GOV_API_KEY"
FRED_KEY_ENV = "FRED_API_KEY"
EIA_KEY_ENV = "EIA_API_KEY"
COURTLISTENER_TOKEN_ENV = "COURTLISTENER_API_TOKEN"

CONGRESS_GOV_BASE_URL = "https://api.congress.gov/v3"
GOVINFO_BASE_URL = "https://api.govinfo.gov"
REGULATIONS_GOV_BASE_URL = "https://api.regulations.gov/v4"
REGINFO_BASE_URL = "https://www.reginfo.gov/public/do"
USASPENDING_BASE_URL = "https://api.usaspending.gov/api/v2"
EIA_BASE_URL = "https://api.eia.gov/v2"
FRED_BASE_URL = "https://api.stlouisfed.org/fred"
COURTLISTENER_BASE_URL = "https://www.courtlistener.com/api/rest/v4"

CORE_REGINFO_REPORTS = (
    "EO_RULES_UNDER_REVIEW.xml",
    "EO_RULE_COMPLETED_30_DAYS.xml",
)
USASPENDING_AWARD_TYPE_QUERIES = (
    (
        ("A", "B", "C", "D"),
        (
            "Award ID",
            "Recipient Name",
            "Award Amount",
            "Awarding Agency",
            "Start Date",
            "End Date",
            "Description",
        ),
        "Award Amount",
    ),
    (
        ("02", "03", "04", "05", "F001", "F002"),
        (
            "Award ID",
            "Recipient Name",
            "Award Amount",
            "Awarding Agency",
            "Start Date",
            "End Date",
            "Description",
        ),
        "Award Amount",
    ),
    (
        ("07", "08", "F003", "F004"),
        (
            "Award ID",
            "Recipient Name",
            "Awarding Agency",
            "Start Date",
            "End Date",
        ),
        "Award ID",
    ),
)


@dataclass(frozen=True)
class PublicSourceFetch:
    source: str
    rows: list[dict[str, Any]]
    status: str
    error_class: str | None = None
    error_summary: str | None = None


def parse_optional_date(value: Any) -> date | None:
    if not value:
        return None
    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(parsed):
        return None
    return parsed.date()


def clean_piece(value: Any) -> str:
    return " ".join(str(value or "").split())


def compact_body(parts: Iterable[Any]) -> str:
    return " ".join(clean_piece(part) for part in parts if clean_piece(part))


def amount_float(value: Any) -> float:
    try:
        return float(str(value or "0").replace(",", "").replace("$", ""))
    except ValueError:
        return 0.0


class CongressGovClient:
    def __init__(
        self,
        *,
        api_key: str,
        session: requests.Session | None = None,
        base_url: str = CONGRESS_GOV_BASE_URL,
    ) -> None:
        self.api_key = api_key
        self.session = session or requests.Session()
        self.base_url = base_url.rstrip("/")

    def summaries(
        self,
        *,
        start_date: date,
        end_date: date,
        limit: int = 100,
        max_pages: int = 10,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        for _ in range(max_pages):
            response = self.session.get(
                f"{self.base_url}/summaries",
                params={
                    "api_key": self.api_key,
                    "format": "json",
                    "fromDateTime": f"{start_date.isoformat()}T00:00:00Z",
                    "toDateTime": f"{end_date.isoformat()}T23:59:59Z",
                    "limit": limit,
                    "offset": offset,
                },
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
            batch = payload.get("summaries", [])
            rows.extend(batch)
            if len(batch) < limit:
                break
            offset += limit
        return rows

    def bill_detail(
        self, congress: str | int, bill_type: str, number: str | int
    ) -> dict[str, Any]:
        response = self.session.get(
            f"{self.base_url}/bill/{congress}/{bill_type}/{number}",
            params={"api_key": self.api_key, "format": "json"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        bill = payload.get("bill", {})
        return bill if isinstance(bill, dict) else {}

    def bill_text_versions(
        self, congress: str | int, bill_type: str, number: str | int
    ) -> list[dict[str, Any]]:
        response = self.session.get(
            f"{self.base_url}/bill/{congress}/{bill_type}/{number}/text",
            params={"api_key": self.api_key, "format": "json"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        versions = payload.get("textVersions", [])
        return [item for item in versions if isinstance(item, dict)]


class GovInfoClient:
    def __init__(
        self,
        *,
        api_key: str,
        session: requests.Session | None = None,
        base_url: str = GOVINFO_BASE_URL,
    ) -> None:
        self.api_key = api_key
        self.session = session or requests.Session()
        self.base_url = base_url.rstrip("/")

    def collection_packages(
        self,
        *,
        collection: str,
        start_date_time: str,
        page_size: int = 10,
    ) -> dict[str, Any]:
        response = self.session.get(
            f"{self.base_url}/collections/{collection}/{start_date_time}",
            params={
                "api_key": self.api_key,
                "pageSize": page_size,
                "offsetMark": "*",
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()

    def package_summary(self, package_id: str) -> dict[str, Any]:
        response = self.session.get(
            f"{self.base_url}/packages/{package_id}/summary",
            params={"api_key": self.api_key},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()


class RegulationsGovClient:
    def __init__(
        self,
        *,
        api_key: str,
        session: requests.Session | None = None,
        base_url: str = REGULATIONS_GOV_BASE_URL,
    ) -> None:
        self.api_key = api_key
        self.session = session or requests.Session()
        self.base_url = base_url.rstrip("/")

    def documents(
        self,
        *,
        search_term: str,
        page_size: int = 25,
    ) -> list[dict[str, Any]]:
        response = self.session.get(
            f"{self.base_url}/documents",
            params={
                "api_key": self.api_key,
                "filter[searchTerm]": search_term,
                "page[size]": max(5, page_size),
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        return [item for item in payload.get("data", []) if isinstance(item, dict)]

    def docket(self, docket_id: str) -> dict[str, Any]:
        response = self.session.get(
            f"{self.base_url}/dockets/{docket_id}",
            params={"api_key": self.api_key},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()


class RegInfoClient:
    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        base_url: str = REGINFO_BASE_URL,
    ) -> None:
        self.session = session or requests.Session()
        self.base_url = base_url.rstrip("/")

    def xml_report(self, report_name: str) -> list[dict[str, str]]:
        response = self.session.get(
            f"{self.base_url}/XMLViewFileAction",
            params={"f": report_name},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        root = ET.fromstring(response.content)
        rows = []
        for regact in root.findall(".//REGACT"):
            rows.append({child.tag: clean_piece(child.text) for child in regact})
        return rows


class USASpendingClient:
    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        base_url: str = USASPENDING_BASE_URL,
    ) -> None:
        self.session = session or requests.Session()
        self.base_url = base_url.rstrip("/")

    def award_search(
        self, *, keyword: str, start_date: date, end_date: date, limit: int = 25
    ) -> list[dict[str, Any]]:
        rows_by_id: dict[str, dict[str, Any]] = {}
        for award_type_codes, fields, sort_field in USASPENDING_AWARD_TYPE_QUERIES:
            response = self.session.post(
                f"{self.base_url}/search/spending_by_award/",
                json={
                    "filters": {
                        "keywords": [keyword],
                        "award_type_codes": list(award_type_codes),
                        "time_period": [
                            {
                                "start_date": start_date.isoformat(),
                                "end_date": end_date.isoformat(),
                            }
                        ],
                    },
                    "fields": list(fields),
                    "page": 1,
                    "limit": limit,
                    "sort": sort_field,
                    "order": "desc",
                },
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
            for item in payload.get("results", []):
                if isinstance(item, dict):
                    key = str(item.get("Award ID") or len(rows_by_id))
                    rows_by_id[key] = item
        return sorted(
            rows_by_id.values(),
            key=lambda row: amount_float(row.get("Award Amount")),
            reverse=True,
        )[:limit]


class EIAClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        session: requests.Session | None = None,
        base_url: str = EIA_BASE_URL,
    ) -> None:
        self.api_key = api_key or os.getenv(EIA_KEY_ENV) or "DEMO_KEY"
        self.session = session or requests.Session()
        self.base_url = base_url.rstrip("/")

    def latest_electricity_price(self) -> dict[str, Any]:
        response = self.session.get(
            f"{self.base_url}/electricity/retail-sales/data/",
            params={
                "api_key": self.api_key,
                "frequency": "monthly",
                "data[0]": "price",
                "facets[stateid][]": "US",
                "facets[sectorid][]": "ALL",
                "sort[0][column]": "period",
                "sort[0][direction]": "desc",
                "length": 1,
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        return (payload.get("response", {}).get("data") or [{}])[0]


class FREDClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        session: requests.Session | None = None,
        base_url: str = FRED_BASE_URL,
    ) -> None:
        self.api_key = api_key or os.getenv(FRED_KEY_ENV)
        self.session = session or requests.Session()
        self.base_url = base_url.rstrip("/")

    def observations(
        self, *, series_id: str, start_date: date | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        if not self.api_key:
            return []
        params: dict[str, Any] = {
            "api_key": self.api_key,
            "file_type": "json",
            "series_id": series_id,
            "limit": limit,
            "sort_order": "desc",
        }
        if start_date:
            params["observation_start"] = start_date.isoformat()
        response = self.session.get(
            f"{self.base_url}/series/observations",
            params=params,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        return [
            item for item in payload.get("observations", []) if isinstance(item, dict)
        ]


class CourtListenerClient:
    def __init__(
        self,
        *,
        token: str | None = None,
        session: requests.Session | None = None,
        base_url: str = COURTLISTENER_BASE_URL,
    ) -> None:
        self.token = token or os.getenv(COURTLISTENER_TOKEN_ENV)
        self.session = session or requests.Session()
        self.base_url = base_url.rstrip("/")

    def search(self, *, query: str, page_size: int = 10) -> list[dict[str, Any]]:
        headers = {}
        if self.token:
            headers["Authorization"] = f"Token {self.token}"
        response = self.session.get(
            f"{self.base_url}/search/",
            params={"q": query, "type": "o", "page_size": page_size},
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        return [item for item in payload.get("results", []) if isinstance(item, dict)]


class RegulationsGovIngestor(BaseIngestor):
    source = "regulations_gov"
    agency = "Regulations.gov"

    def __init__(
        self,
        api_key: str | None = None,
        session: requests.Session | None = None,
        ingested_at: pd.Timestamp | None = None,
    ) -> None:
        super().__init__(session=session, ingested_at=ingested_at)
        self.api_key = api_key or os.getenv(REGULATIONS_GOV_KEY_ENV)

    def collect_documents(
        self, start_date: date, end_date: date, fetch_bodies: bool = True
    ) -> pd.DataFrame:
        del fetch_bodies
        if not self.api_key:
            LOGGER.warning(
                "%s is not set; skipping Regulations.gov ingest",
                REGULATIONS_GOV_KEY_ENV,
            )
            return self.enforce_schema([])
        client = RegulationsGovClient(api_key=self.api_key, session=self.session)
        rows: dict[str, dict[str, Any]] = {}
        for term in FEDERAL_REGISTER_TERMS:
            for item in client.documents(search_term=term):
                row = self._normalize_document(
                    item, start_date=start_date, end_date=end_date
                )
                if row:
                    rows[row["doc_id"]] = row
        return self.enforce_schema(rows.values())

    def _normalize_document(
        self, item: dict[str, Any], *, start_date: date, end_date: date
    ) -> dict[str, Any] | None:
        attrs = item.get("attributes") or {}
        doc_date = parse_optional_date(
            attrs.get("postedDate") or attrs.get("lastModifiedDate")
        )
        if doc_date is None or not (start_date <= doc_date <= end_date):
            return None
        body = compact_body(
            [
                attrs.get("title"),
                attrs.get("documentType"),
                attrs.get("subtype"),
                attrs.get("docketId"),
                attrs.get("frDocNum"),
                attrs.get("commentStartDate"),
                attrs.get("commentEndDate"),
            ]
        )
        provisions = infer_provisions_from_text(body)
        if not provisions:
            return None
        doc_id = str(item.get("id") or attrs.get("documentId") or attrs.get("frDocNum"))
        return self.build_record(
            source=self.source,
            native_id=doc_id,
            date_value=doc_date,
            agency=str(attrs.get("agencyId") or self.agency),
            title=str(attrs.get("title") or doc_id),
            body=body,
            url=f"https://www.regulations.gov/document/{doc_id}",
            provisions_mentioned=provisions,
        )


class RegInfoIngestor(BaseIngestor):
    source = "reginfo"
    agency = "OIRA / RegInfo"

    def collect_documents(
        self, start_date: date, end_date: date, fetch_bodies: bool = True
    ) -> pd.DataFrame:
        del fetch_bodies
        client = RegInfoClient(session=self.session)
        rows: dict[str, dict[str, Any]] = {}
        for report in CORE_REGINFO_REPORTS:
            try:
                items = client.xml_report(report)
            except (RequestException, ET.ParseError) as exc:
                LOGGER.warning("Could not fetch RegInfo report %s: %s", report, exc)
                continue
            for item in items:
                row = self._normalize_regact(
                    item,
                    report=report,
                    start_date=start_date,
                    end_date=end_date,
                )
                if row:
                    rows[row["doc_id"]] = row
        return self.enforce_schema(rows.values())

    def _normalize_regact(
        self,
        item: dict[str, str],
        *,
        report: str,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any] | None:
        doc_date = parse_optional_date(
            item.get("DATE_RECEIVED")
            or item.get("DATE_COMPLETED")
            or item.get("DATE_CONCLUDED")
        )
        if doc_date is None or not (start_date <= doc_date <= end_date):
            return None
        rin = (
            item.get("RIN") or item.get("AGENCY_CODE") or item.get("TITLE") or "unknown"
        )
        body = compact_body(
            [
                item.get("TITLE"),
                item.get("RIN"),
                item.get("STAGE"),
                item.get("ECONOMICALLY_SIGNIFICANT"),
                item.get("LEGAL_DEADLINE"),
                item.get("CONCLUSION_ACTION"),
                report,
            ]
        )
        provisions = infer_provisions_from_text(body)
        if not provisions:
            return None
        return self.build_record(
            source=self.source,
            native_id=f"{report}:{rin}",
            date_value=doc_date,
            agency=self.agency,
            title=item.get("TITLE") or rin,
            body=body,
            url=f"https://www.reginfo.gov/public/do/eAgendaViewRule?RIN={rin}",
            provisions_mentioned=provisions,
        )


class USASpendingIngestor(BaseIngestor):
    source = "usaspending"
    agency = "USAspending"

    def collect_documents(
        self, start_date: date, end_date: date, fetch_bodies: bool = True
    ) -> pd.DataFrame:
        del fetch_bodies
        client = USASpendingClient(session=self.session)
        rows: dict[str, dict[str, Any]] = {}
        for term in FEDERAL_REGISTER_TERMS:
            try:
                awards = client.award_search(
                    keyword=term, start_date=start_date, end_date=end_date, limit=10
                )
            except RequestException as exc:
                LOGGER.warning("Could not search USAspending for %r: %s", term, exc)
                continue
            for award in awards:
                row = self._normalize_award(
                    award, start_date=start_date, end_date=end_date
                )
                if row:
                    rows[row["doc_id"]] = row
        return self.enforce_schema(rows.values())

    def _normalize_award(
        self, award: dict[str, Any], *, start_date: date, end_date: date
    ) -> dict[str, Any] | None:
        doc_date = parse_optional_date(award.get("Start Date"))
        if doc_date is None or not (start_date <= doc_date <= end_date):
            return None
        body = compact_body(
            [
                award.get("Award ID"),
                award.get("Recipient Name"),
                award.get("Awarding Agency"),
                award.get("Award Amount"),
                award.get("Description"),
            ]
        )
        provisions = infer_provisions_from_text(body)
        if not provisions:
            return None
        award_id = str(
            award.get("generated_internal_id") or award.get("Award ID") or body[:48]
        )
        return self.build_record(
            source=self.source,
            native_id=award_id,
            date_value=doc_date,
            agency=str(award.get("Awarding Agency") or self.agency),
            title=f"Federal award: {award.get('Recipient Name') or award_id}",
            body=body,
            url="https://www.usaspending.gov/search",
            provisions_mentioned=provisions,
        )
