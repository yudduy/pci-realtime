from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, ClassVar, Iterable, Optional
from urllib.parse import urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

from pci_realtime.config import PROVISION_KEYWORDS


USER_AGENT = "pci-realtime/0.1 (research pipeline)"
INGESTOR_VERSION = "0.1.0"
SCHEMA_A_COLUMNS = [
    "doc_id",
    "date",
    "source",
    "agency",
    "title",
    "body",
    "body_truncated",
    "url",
    "provisions_mentioned",
    "ingested_at",
    "ingestor_version",
]
ALLOWED_SOURCES = {"federal_register", "treasury", "irs", "congress", "omb"}
MAX_BODY_CHARS = 50_000


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


def get_session(user_agent: str | None = None) -> requests.Session:
    session = requests.Session()
    user_agent = user_agent or os.getenv("FEDERAL_REGISTER_USER_AGENT") or USER_AGENT
    session.headers.update({"User-Agent": user_agent})
    return session


def clean_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    candidate = (
        soup.select_one("article")
        or soup.select_one("main")
        or soup.select_one(".document")
        or soup.body
        or soup
    )
    text = candidate.get_text(separator=" ", strip=True)
    return " ".join(text.split())


def infer_provisions_from_text(text: str) -> list[str]:
    lowered = (text or "").lower()
    matched = []
    for provision, keywords in PROVISION_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            matched.append(provision)
    return sorted(set(matched))


def source_prefixed_doc_id(source: str, native_id: str) -> str:
    native_id = str(native_id).strip()
    if native_id.startswith(f"{source}:"):
        return native_id
    return f"{source}:{native_id}"


def native_id_from_url(url: str) -> str:
    parsed = urlparse(url or "")
    path = parsed.path.strip("/").replace("/", "-")
    if path:
        return path
    return parsed.netloc or "unknown"


class BaseIngestor:
    """Shared Schema A validation and parquet writing for source ingestors."""

    source: ClassVar[str]
    agency: ClassVar[str]
    ingestor_version: ClassVar[str] = INGESTOR_VERSION
    max_body_chars: ClassVar[int] = MAX_BODY_CHARS

    def __init__(
        self,
        session: Optional[requests.Session] = None,
        ingested_at: Optional[pd.Timestamp] = None,
    ) -> None:
        self.session = session or get_session()
        self.ingested_at = ingested_at or pd.Timestamp.now(tz="UTC")

    def collect_documents(
        self, start_date: date, end_date: date, fetch_bodies: bool = True
    ) -> pd.DataFrame:
        raise NotImplementedError

    def build_record(
        self,
        *,
        source: str,
        native_id: str,
        date_value: Any,
        agency: str,
        title: str,
        body: str,
        url: str,
        provisions_mentioned: Optional[Iterable[str]] = None,
    ) -> dict[str, Any]:
        truncated_body = body or ""
        body_truncated = len(truncated_body) > self.max_body_chars
        if body_truncated:
            truncated_body = truncated_body[: self.max_body_chars]

        provisions = sorted(set(provisions_mentioned or []))
        return {
            "doc_id": source_prefixed_doc_id(source, native_id),
            "date": date_value,
            "source": source,
            "agency": agency,
            "title": title or "",
            "body": truncated_body,
            "body_truncated": body_truncated,
            "url": url or "",
            "provisions_mentioned": provisions,
            "ingested_at": self.ingested_at,
            "ingestor_version": self.ingestor_version,
        }

    def enforce_schema(
        self, rows: Iterable[dict[str, Any]] | pd.DataFrame
    ) -> pd.DataFrame:
        df = rows.copy() if isinstance(rows, pd.DataFrame) else pd.DataFrame(list(rows))
        if df.empty:
            return pd.DataFrame(columns=SCHEMA_A_COLUMNS)

        missing = [column for column in SCHEMA_A_COLUMNS if column not in df.columns]
        if missing:
            msg = f"Schema A missing required columns: {missing}"
            raise ValueError(msg)

        df = df.loc[:, SCHEMA_A_COLUMNS].copy()
        df["doc_id"] = df["doc_id"].astype("string")
        df["source"] = df["source"].astype("string")
        invalid_sources = sorted(set(df["source"].dropna()) - ALLOWED_SOURCES)
        if invalid_sources:
            msg = f"Invalid source values for Schema A: {invalid_sources}"
            raise ValueError(msg)

        date_values = pd.to_datetime(df["date"], errors="coerce", utc=True)
        if date_values.isna().any():
            bad_doc_ids = df.loc[date_values.isna(), "doc_id"].tolist()
            msg = f"Invalid document dates for Schema A rows: {bad_doc_ids}"
            raise ValueError(msg)
        df["date"] = date_values.dt.date

        for column in ["agency", "title", "body", "url", "ingestor_version"]:
            df[column] = df[column].fillna("").astype("string")

        df["body_truncated"] = df["body_truncated"].fillna(False).astype(bool)
        df["provisions_mentioned"] = df["provisions_mentioned"].apply(
            lambda value: sorted(set(value)) if isinstance(value, list) else []
        )
        df["ingested_at"] = pd.to_datetime(df["ingested_at"], utc=True)
        return df.sort_values(["date", "doc_id"]).reset_index(drop=True)

    def output_path_for_window(self, output_dir: Path, window: IngestWindow) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir / f"{self.source}_{window.iso_week_label}.parquet"

    def save_week_parquet(
        self, df: pd.DataFrame, output_dir: Path, window: IngestWindow
    ) -> Path:
        schema_df = self.enforce_schema(df)
        path = self.output_path_for_window(output_dir=output_dir, window=window)
        schema_df.to_parquet(path, index=False)
        return path

    def run_window(
        self,
        start_date: date,
        end_date: date,
        output_dir: Path,
        fetch_bodies: bool = True,
    ) -> Path:
        window = IngestWindow(start_date=start_date, end_date=end_date)
        df = self.collect_documents(
            start_date=start_date, end_date=end_date, fetch_bodies=fetch_bodies
        )
        return self.save_week_parquet(df=df, output_dir=output_dir, window=window)
