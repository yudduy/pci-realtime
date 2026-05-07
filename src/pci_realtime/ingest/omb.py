from __future__ import annotations

import argparse
import logging
from datetime import date
from pathlib import Path

import pandas as pd
import requests
from requests.exceptions import RequestException

from pci_realtime.config import OMB_MEMO_PAGES, REQUEST_TIMEOUT_SECONDS
from pci_realtime.ingest.base import (
    BaseIngestor,
    clean_text_from_html,
    infer_provisions_from_text,
    native_id_from_url,
    parse_date,
)
from pci_realtime.ingest.treasury import (
    extract_candidate_urls,
    extract_page_date,
    extract_page_title,
)


LOGGER = logging.getLogger(__name__)


class OmbIngestor(BaseIngestor):
    source = "omb"
    agency = "Office of Management and Budget"

    def collect_documents(
        self, start_date: date, end_date: date, fetch_bodies: bool = True
    ) -> pd.DataFrame:
        rows = []
        seen_urls: set[str] = set()
        for index_url in OMB_MEMO_PAGES:
            try:
                response = self.session.get(index_url, timeout=REQUEST_TIMEOUT_SECONDS)
                response.raise_for_status()
            except RequestException as exc:
                LOGGER.warning("Could not fetch OMB memo index %s: %s", index_url, exc)
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
                LOGGER.warning("Could not fetch OMB memo candidate %s: %s", url, exc)
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
    session: requests.Session | None = None,
) -> pd.DataFrame:
    return OmbIngestor(session=session).collect_documents(
        start_date=start_date, end_date=end_date, fetch_bodies=fetch_bodies
    )


def run_window(
    start_date: date,
    end_date: date,
    output_dir: Path,
    fetch_bodies: bool = True,
) -> Path:
    return OmbIngestor().run_window(
        start_date=start_date,
        end_date=end_date,
        output_dir=output_dir,
        fetch_bodies=fetch_bodies,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch OMB memos for the PCI monitor.")
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
    )
    LOGGER.info("Wrote OMB parquet to: %s", output_path)


if __name__ == "__main__":
    main()
