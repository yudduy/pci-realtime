from __future__ import annotations

import argparse
import logging
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from requests.exceptions import RequestException

from pci_realtime.config import (
    FEDERAL_REGISTER_TERMS,
    REQUEST_TIMEOUT_SECONDS,
    TREASURY_GUIDANCE_PAGES,
)
from pci_realtime.ingest.base import (
    BaseIngestor,
    clean_text_from_html,
    infer_provisions_from_text,
    native_id_from_url,
    parse_date,
)


LOGGER = logging.getLogger(__name__)
SOURCE_AGENCIES = {
    "treasury": "U.S. Department of the Treasury",
    "irs": "Internal Revenue Service",
}
DATE_PATTERNS = [
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
        r"[a-z]*\.?\s+\d{1,2},\s+\d{4}\b",
        re.IGNORECASE,
    ),
]


def _safe_parse_date(value: str) -> date | None:
    try:
        return date_parser.parse(value).date()
    except (TypeError, ValueError, date_parser.ParserError):
        return None


def _text_matches_scope(text: str) -> bool:
    lowered = (text or "").lower()
    terms = ["inflation reduction act", *FEDERAL_REGISTER_TERMS]
    return any(term.lower() in lowered for term in terms)


def extract_candidate_urls(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html or "", "html.parser")
    urls: list[str] = []
    for anchor in soup.find_all("a", href=True):
        label = anchor.get_text(" ", strip=True)
        href = str(anchor["href"])
        target = urljoin(base_url, href)
        if _text_matches_scope(f"{label} {target}"):
            urls.append(target)
    if _text_matches_scope(soup.get_text(" ", strip=True)):
        urls.append(base_url)
    return sorted(set(urls))


def extract_page_date(html: str) -> date | None:
    soup = BeautifulSoup(html or "", "html.parser")
    for selector in [
        "time[datetime]",
        "meta[property='article:published_time']",
        "meta[name='date']",
        "meta[name='dc.date']",
    ]:
        tag = soup.select_one(selector)
        if not tag:
            continue
        value = tag.get("datetime") or tag.get("content")
        if value:
            parsed = _safe_parse_date(str(value))
            if parsed:
                return parsed

    text = soup.get_text(" ", strip=True)
    for pattern in DATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        parsed = _safe_parse_date(match.group(0))
        if parsed:
            return parsed
    return None


def extract_page_title(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    heading = soup.select_one("h1") or soup.select_one("title")
    return heading.get_text(" ", strip=True) if heading else ""


class TreasuryIngestor(BaseIngestor):
    source = "treasury"
    agency = SOURCE_AGENCIES["treasury"]

    def __init__(
        self,
        source: str = "treasury",
        session: requests.Session | None = None,
        ingested_at: pd.Timestamp | None = None,
    ) -> None:
        if source not in SOURCE_AGENCIES:
            msg = f"Unsupported Treasury-family source: {source}"
            raise ValueError(msg)
        super().__init__(session=session, ingested_at=ingested_at)
        self.source = source
        self.agency = SOURCE_AGENCIES[source]

    def collect_documents(
        self, start_date: date, end_date: date, fetch_bodies: bool = True
    ) -> pd.DataFrame:
        rows = []
        seen_urls: set[str] = set()
        for index_url in TREASURY_GUIDANCE_PAGES[self.source]:
            try:
                response = self.session.get(index_url, timeout=REQUEST_TIMEOUT_SECONDS)
                response.raise_for_status()
            except RequestException as exc:
                LOGGER.warning("Could not fetch Treasury index %s: %s", index_url, exc)
                continue

            for url in extract_candidate_urls(response.text, index_url):
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                row = self._fetch_candidate(
                    url=url,
                    fallback_html=response.text if url == index_url else "",
                    start_date=start_date,
                    end_date=end_date,
                    fetch_body=fetch_bodies,
                )
                if row is not None:
                    rows.append(row)
        return self.enforce_schema(rows)

    def _fetch_candidate(
        self,
        *,
        url: str,
        fallback_html: str,
        start_date: date,
        end_date: date,
        fetch_body: bool,
    ) -> dict | None:
        html = fallback_html
        if fetch_body or not html:
            try:
                response = self.session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
                response.raise_for_status()
                html = response.text
            except RequestException as exc:
                LOGGER.warning("Could not fetch Treasury candidate %s: %s", url, exc)
                return None

        doc_date = extract_page_date(html)
        if doc_date is None or not start_date <= doc_date <= end_date:
            return None

        title = extract_page_title(html)
        body = clean_text_from_html(html)
        provisions = infer_provisions_from_text(f"{title} {body}")
        if not provisions:
            return None

        return self.build_record(
            source=self.source,
            native_id=native_id_from_url(url),
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
    source: str = "treasury",
    session: requests.Session | None = None,
) -> pd.DataFrame:
    return TreasuryIngestor(source=source, session=session).collect_documents(
        start_date=start_date, end_date=end_date, fetch_bodies=fetch_bodies
    )


def run_window(
    start_date: date,
    end_date: date,
    output_dir: Path,
    fetch_bodies: bool = True,
    source: str = "treasury",
) -> Path:
    return TreasuryIngestor(source=source).run_window(
        start_date=start_date,
        end_date=end_date,
        output_dir=output_dir,
        fetch_bodies=fetch_bodies,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch Treasury or IRS guidance pages for the PCI monitor."
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
        "--source",
        choices=sorted(SOURCE_AGENCIES),
        default="treasury",
        help="Treasury-family source to ingest.",
    )
    parser.add_argument(
        "--skip-bodies",
        action="store_true",
        help="Skip candidate page body fetching when possible.",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    output_path = run_window(
        start_date=parse_date(args.start_date),
        end_date=parse_date(args.end_date),
        output_dir=Path(args.output_dir),
        fetch_bodies=not args.skip_bodies,
        source=args.source,
    )
    LOGGER.info("Wrote %s parquet to: %s", args.source, output_path)


if __name__ == "__main__":
    main()
