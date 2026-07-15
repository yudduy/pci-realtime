from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

from pci_realtime.config import (
    BASELINE_PCI,
    OBBBA_PCI_DELTAS,
    PROVISION_DETAILS,
    REQUEST_TIMEOUT_SECONDS,
)


LOGGER = logging.getLogger(__name__)
UPSERT_CONFLICT_KEYS = {
    "provisions": "code",
    "scored_deltas": "week,doc_id,provision",
    "pci_weekly": "provision,week",
    "policy_events": "event_id",
    "source_documents": "source_doc_id",
    "evidence_items": "evidence_id",
    "source_links": "link_id",
    "source_health": "source",
}
FORBIDDEN_PUBLIC_STRINGS = (
    "OPENAI_API_KEY",
    "KALSHI_PRIVATE_KEY",
    "raw_response",
    "Company ID",
    "PitchBook",
    "CTVC",
    "trade_signature",
    "/Users/",
)
FORBIDDEN_PUBLIC_PATTERNS = (
    ("OpenAI project key", re.compile(r"sk-proj-[A-Za-z0-9_-]{20,}")),
    ("OpenAI secret key", re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_]{32,}")),
)


def json_clean(value: Any) -> Any:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): json_clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_clean(item) for item in value]
    if hasattr(value, "tolist"):
        return json_clean(value.tolist())
    if not isinstance(value, (list, dict, tuple, set)):
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass
    return value


def assert_public_payload_safe(payload: Any) -> None:
    text = json.dumps(json_clean(payload), sort_keys=True)
    for forbidden in FORBIDDEN_PUBLIC_STRINGS:
        if forbidden in text:
            msg = f"Public payload contains forbidden token: {forbidden}"
            raise ValueError(msg)
    for label, pattern in FORBIDDEN_PUBLIC_PATTERNS:
        if pattern.search(text):
            msg = f"Public payload contains forbidden token: {label}"
            raise ValueError(msg)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    assert_public_payload_safe(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(json_clean(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        assert_public_payload_safe(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(json_clean(row), sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


@dataclass(frozen=True)
class SupabaseRestClient:
    url: str
    service_role_key: str
    timeout_seconds: int = REQUEST_TIMEOUT_SECONDS

    @classmethod
    def from_env(cls) -> SupabaseRestClient | None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SECRET_KEY")
        if not url or not key:
            return None
        return cls(url=url.rstrip("/"), service_role_key=key)

    def insert_rows(self, table: str, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        response = httpx.post(
            f"{self.url}/rest/v1/{table}",
            headers=self._headers("resolution=ignore-duplicates"),
            json=json_clean(rows),
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()

    def upsert_rows(
        self,
        table: str,
        rows: list[dict[str, Any]],
        *,
        on_conflict: str | None = None,
    ) -> None:
        if not rows:
            return
        response = httpx.post(
            f"{self.url}/rest/v1/{table}",
            headers=self._headers("resolution=merge-duplicates"),
            params={"on_conflict": on_conflict} if on_conflict else None,
            json=json_clean(rows),
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()

    def select_rows(
        self,
        table: str,
        *,
        columns: str = "*",
        params: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        query = {"select": columns}
        if params:
            query.update(params)
        response = httpx.get(
            f"{self.url}/rest/v1/{table}",
            headers=self._headers(),
            params=query,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            msg = f"Expected list payload from Supabase table {table}"
            raise TypeError(msg)
        return [json_clean(row) for row in payload]

    def _headers(self, prefer: str | None = None) -> dict[str, str]:
        headers = {
            "apikey": self.service_role_key,
            "Authorization": f"Bearer {self.service_role_key}",
            "Content-Type": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        return headers


def build_seed_rows() -> dict[str, list[dict[str, Any]]]:
    provisions = []
    pci_weekly = []
    for code, baseline in BASELINE_PCI.items():
        details = PROVISION_DETAILS[code]
        obbba_delta = float(OBBBA_PCI_DELTAS[code])
        provisions.append(
            {
                "code": code,
                "name": details["name"],
                "provision_type": details["type"],
                "primary_channel": details["primary_channel"],
                "paper_role": details["paper_role"],
                "baseline_specificity": baseline["specificity"],
                "baseline_durability": baseline["durability"],
                "baseline_enforceability": baseline["enforceability"],
                "baseline_pci": baseline["pci"],
                "baseline_as_of": "2022-08-16",
                "obbba_delta_pci": obbba_delta,
                "obbba_post_pci": round(float(baseline["pci"]) + obbba_delta, 2),
                "obbba_summary": details["obbba_shock"],
                "data_origin": "paper_anchor",
            }
        )
        pci_weekly.append(
            {
                "provision": code,
                "week": "2022-W33",
                "week_start": "2022-08-15",
                "pci": baseline["pci"],
                "specificity": baseline["specificity"],
                "durability": baseline["durability"],
                "enforceability": baseline["enforceability"],
                "n_docs": 0,
                "delta_this_week": 0,
                "data_origin": "paper_anchor",
                "source_event_ids": [],
                "provenance_status": "complete",
            }
        )
    return {
        "provisions": provisions,
        "pci_weekly": pci_weekly,
        "pipeline_runs": [
            {
                "run_type": "seed",
                "status": "success",
                "source": "seed_supabase.py",
                "metadata": {
                    "description": "Seeded paper anchors and baseline PCI.",
                },
            }
        ],
    }


def scored_delta_to_row(row: dict[str, Any]) -> dict[str, Any]:
    return json_clean(
        {
            "week": row["week"],
            "doc_id": row["doc_id"],
            "provision": row["provision"],
            "specificity_delta": row["specificity_delta"],
            "durability_delta": row["durability_delta"],
            "enforceability_delta": row["enforceability_delta"],
            "rationale": row.get("rationale"),
            "confidence": row.get("confidence"),
            "model": row.get("model"),
            "prompt_version": row.get("prompt_version"),
            "temperature": row.get("temperature"),
            "scored_at": row.get("scored_at"),
            "cached": bool(row.get("cached")),
            "cost_usd": row.get("cost_usd"),
        }
    )


def write_supabase_rows(
    rows_by_table: dict[str, list[dict[str, Any]]],
    *,
    client: SupabaseRestClient,
) -> None:
    client.upsert_rows(
        "provisions",
        rows_by_table["provisions"],
        on_conflict=UPSERT_CONFLICT_KEYS["provisions"],
    )
    client.upsert_rows(
        "scored_deltas",
        rows_by_table.get("scored_deltas", []),
        on_conflict=UPSERT_CONFLICT_KEYS["scored_deltas"],
    )
    client.upsert_rows(
        "pci_weekly",
        rows_by_table["pci_weekly"],
        on_conflict=UPSERT_CONFLICT_KEYS["pci_weekly"],
    )
    client.upsert_rows(
        "policy_events",
        rows_by_table["policy_events"],
        on_conflict=UPSERT_CONFLICT_KEYS["policy_events"],
    )
    client.insert_rows("pipeline_runs", rows_by_table["pipeline_runs"])
    client.upsert_rows(
        "source_documents",
        rows_by_table.get("source_documents", []),
        on_conflict=UPSERT_CONFLICT_KEYS["source_documents"],
    )
    client.upsert_rows(
        "evidence_items",
        rows_by_table.get("evidence_items", []),
        on_conflict=UPSERT_CONFLICT_KEYS["evidence_items"],
    )
    client.upsert_rows(
        "source_links",
        rows_by_table.get("source_links", []),
        on_conflict=UPSERT_CONFLICT_KEYS["source_links"],
    )
    client.upsert_rows(
        "source_health",
        rows_by_table.get("source_health", []),
        on_conflict=UPSERT_CONFLICT_KEYS["source_health"],
    )
