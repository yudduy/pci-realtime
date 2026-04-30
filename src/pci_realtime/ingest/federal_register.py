from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.exceptions import RequestException

from pci_realtime.config import (
    ALLOWED_FEDERAL_REGISTER_AGENCY_SLUGS,
    FEDERAL_REGISTER_CONFIG,
    FEDERAL_REGISTER_TERMS,
    PROVISION_KEYWORDS,
)


USER_AGENT = "pci-realtime/0.1 (research pipeline)"


@dataclass(frozen=True)
class IngestWindow:
    start_date: date
    end_date: date

    @property
    def iso_week_label(self) -> str:
        iso = self.start_date.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def build_query_params(term: str, start_date: date, end_date: date, page: int = 1, per_page: Optional[int] = None) -> dict:
    per_page = per_page or FEDERAL_REGISTER_CONFIG.default_per_page
    return {
        "conditions[term]": term,
        "conditions[publication_date][gte]": start_date.isoformat(),
        "conditions[publication_date][lte]": end_date.isoformat(),
        "order": "relevance",
        "page": page,
        "per_page": per_page,
    }


def get_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def query_documents_for_term(
    term: str,
    start_date: date,
    end_date: date,
    session: Optional[requests.Session] = None,
) -> list[dict]:
    session = session or get_session()
    all_results: list[dict] = []

    for page in range(1, FEDERAL_REGISTER_CONFIG.max_pages + 1):
        params = build_query_params(term=term, start_date=start_date, end_date=end_date, page=page)
        try:
            response = session.get(
                FEDERAL_REGISTER_CONFIG.base_url,
                params=params,
                timeout=FEDERAL_REGISTER_CONFIG.timeout_seconds,
            )
            response.raise_for_status()
        except RequestException:
            break
        payload = response.json()
        results = payload.get("results", [])
        if not results:
            break

        for result in results:
            result = dict(result)
            result["query_term"] = term
            all_results.append(result)

        total_pages = payload.get("total_pages", 1)
        if page >= total_pages:
            break

    return all_results


def extract_agency_slugs(doc: dict) -> list[str]:
    agencies = doc.get("agencies") or []
    return [agency.get("slug", "") for agency in agencies if agency.get("slug")]


def extract_agency_names(doc: dict) -> list[str]:
    agencies = doc.get("agencies") or []
    names = []
    for agency in agencies:
        name = agency.get("name") or agency.get("raw_name")
        if name:
            names.append(str(name))
    return names


def is_allowed_agency(doc: dict) -> bool:
    slugs = set(extract_agency_slugs(doc))
    return bool(slugs & ALLOWED_FEDERAL_REGISTER_AGENCY_SLUGS)


def clean_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    # Prefer the main article body when possible.
    candidate = (
        soup.select_one("article")
        or soup.select_one("main")
        or soup.select_one(".document")
        or soup.body
        or soup
    )
    text = candidate.get_text(separator=" ", strip=True)
    return " ".join(text.split())


def fetch_document_body(html_url: str, session: Optional[requests.Session] = None) -> str:
    if not html_url:
        return ""

    session = session or get_session()
    response = session.get(html_url, timeout=FEDERAL_REGISTER_CONFIG.timeout_seconds)
    response.raise_for_status()
    return clean_text_from_html(response.text)


def infer_provisions_from_text(text: str) -> list[str]:
    lowered = (text or "").lower()
    matched = []
    for provision, keywords in PROVISION_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            matched.append(provision)
    return sorted(set(matched))


def normalize_document(raw_doc: dict, fetch_bodies: bool = True, session: Optional[requests.Session] = None) -> dict:
    title = raw_doc.get("title") or ""
    abstract = raw_doc.get("abstract") or ""
    excerpts = raw_doc.get("excerpts") or ""
    html_url = raw_doc.get("html_url") or ""
    body = ""
    if fetch_bodies and html_url:
        try:
            body = fetch_document_body(html_url=html_url, session=session)
        except Exception:
            body = ""

    combined_text = " ".join(part for part in [title, abstract, excerpts, body] if part)
    provisions = infer_provisions_from_text(combined_text)

    return {
        "doc_id": raw_doc.get("document_number") or raw_doc.get("id") or html_url,
        "document_number": raw_doc.get("document_number"),
        "date": raw_doc.get("publication_date"),
        "agency": "; ".join(extract_agency_names(raw_doc)),
        "agency_slugs": "; ".join(extract_agency_slugs(raw_doc)),
        "title": title,
        "abstract": abstract,
        "body": body or abstract,
        "url": html_url,
        "type": raw_doc.get("type"),
        "query_term": raw_doc.get("query_term"),
        "provisions_mentioned": provisions,
    }


def collect_documents(
    start_date: date,
    end_date: date,
    fetch_bodies: bool = True,
    session: Optional[requests.Session] = None,
    terms: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    session = session or get_session()
    terms = list(terms or FEDERAL_REGISTER_TERMS)

    raw_docs: list[dict] = []
    for term in terms:
        raw_docs.extend(query_documents_for_term(term=term, start_date=start_date, end_date=end_date, session=session))

    # Dedupe on document number while preserving all query terms that found the document.
    by_doc_id: dict[str, dict] = {}
    for raw_doc in raw_docs:
        doc_id = raw_doc.get("document_number") or raw_doc.get("html_url")
        if not doc_id:
            continue
        query_term = raw_doc.get("query_term")
        if doc_id not in by_doc_id:
            raw_doc = dict(raw_doc)
            raw_doc["_query_terms"] = {query_term} if query_term else set()
            by_doc_id[doc_id] = raw_doc
        elif query_term:
            by_doc_id[doc_id]["_query_terms"].add(query_term)

    normalized_rows: list[dict] = []
    for raw_doc in by_doc_id.values():
        if not is_allowed_agency(raw_doc):
            continue
        normalized = normalize_document(raw_doc, fetch_bodies=fetch_bodies, session=session)
        query_terms = sorted(raw_doc.get("_query_terms", set()))
        normalized["query_term"] = " | ".join(query_terms)
        if normalized["provisions_mentioned"]:
            normalized_rows.append(normalized)

    if not normalized_rows:
        return pd.DataFrame(
            columns=[
                "doc_id",
                "document_number",
                "date",
                "agency",
                "agency_slugs",
                "title",
                "abstract",
                "body",
                "url",
                "type",
                "query_term",
                "provisions_mentioned",
            ]
        )

    df = pd.DataFrame(normalized_rows).sort_values(["date", "doc_id"]).reset_index(drop=True)
    return df


def output_path_for_window(output_dir: Path, window: IngestWindow) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / f"federal_register_{window.iso_week_label}.parquet"


def save_week_parquet(df: pd.DataFrame, output_dir: Path, window: IngestWindow) -> Path:
    path = output_path_for_window(output_dir=output_dir, window=window)
    df.to_parquet(path, index=False)
    return path


def run_window(start_date: date, end_date: date, output_dir: Path, fetch_bodies: bool = True) -> Path:
    window = IngestWindow(start_date=start_date, end_date=end_date)
    df = collect_documents(start_date=start_date, end_date=end_date, fetch_bodies=fetch_bodies)
    return save_week_parquet(df=df, output_dir=output_dir, window=window)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch Federal Register documents for the PCI monitor.")
    parser.add_argument("--start-date", required=True, help="Inclusive start date in YYYY-MM-DD format.")
    parser.add_argument("--end-date", required=True, help="Inclusive end date in YYYY-MM-DD format.")
    parser.add_argument("--output-dir", required=True, help="Directory where the weekly parquet will be written.")
    parser.add_argument(
        "--skip-bodies",
        action="store_true",
        help="Skip HTML body fetching and use abstract text only.",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    start_date = parse_date(args.start_date)
    end_date = parse_date(args.end_date)
    output_path = run_window(
        start_date=start_date,
        end_date=end_date,
        output_dir=Path(args.output_dir),
        fetch_bodies=not args.skip_bodies,
    )
    print(f"Wrote Federal Register parquet to: {output_path}")


if __name__ == "__main__":
    main()
