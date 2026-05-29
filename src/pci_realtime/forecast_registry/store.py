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
    REQUEST_TIMEOUT_SECONDS,
)
from pci_realtime.forecast_registry.engine import utc_now_iso
from pci_realtime.forecast_registry.policy import PROVISION_DETAILS


LOGGER = logging.getLogger(__name__)
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
                    "contains_synthetic_forecasts": False,
                },
            }
        ],
    }


def market_to_row(market: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "generated_at",
        "venue",
        "ticker",
        "event_ticker",
        "title",
        "subtitle",
        "yes_sub_title",
        "no_sub_title",
        "status",
        "result",
        "yes_bid",
        "yes_ask",
        "bid_ask_spread",
        "market_probability",
        "liquidity_dollars",
        "volume",
        "volume_24h",
        "open_interest",
        "open_time",
        "close_time",
        "expected_expiration_time",
        "latest_expiration_time",
        "settlement_ts",
        "rules_primary",
        "rules_secondary",
        "resolution_text",
        "policy_relevant",
    }
    row = {key: value for key, value in market.items() if key in allowed}
    row["raw_public_metadata"] = {
        "query_name": market.get("query_name"),
        "source": market.get("source"),
        **(market.get("raw_public_metadata") or {}),
    }
    return json_clean(row)


def market_inventory_to_row(row: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "venue",
        "ticker",
        "latest_run_id",
        "last_seen_at",
        "title",
        "market_url",
        "status",
        "close_time",
        "market_probability",
        "yes_bid",
        "yes_ask",
        "bid_ask_spread",
        "liquidity_dollars",
        "volume",
        "volume_24h",
        "open_interest",
        "resolution_text",
        "source_payload_hash",
        "raw_public_metadata",
    }
    return json_clean({key: value for key, value in row.items() if key in allowed})


def market_assessment_to_row(row: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "assessment_id",
        "schema_version",
        "assessed_at",
        "latest_run_id",
        "venue",
        "ticker",
        "provision",
        "source_text_hash",
        "relevance_class",
        "resolution_fit",
        "orientation",
        "confidence",
        "evidence_span",
        "rationale",
        "eligible_for_forecast",
        "model_provider",
        "model_name",
        "prompt_version",
        "cached",
        "raw_public_metadata",
    }
    return json_clean({key: value for key, value in row.items() if key in allowed})


def forecast_to_row(
    forecast: dict[str, Any], *, run_id: str | None = None
) -> dict[str, Any]:
    market = forecast.get("market_snapshot") or {}
    signal = forecast.get("signal") or {}
    rationale = forecast.get("forecast_rationale") or {}
    metadata = forecast.get("calibration_metadata") or {}
    return json_clean(
        {
            "forecast_id": forecast["forecast_id"],
            "created_at": forecast.get("generated_at") or utc_now_iso(),
            "schema_version": forecast.get("schema_version"),
            "venue": forecast.get("venue", "kalshi"),
            "market_ticker": forecast.get("market_ticker"),
            "market_title": market.get("title"),
            "market_rules": market.get("resolution_text")
            or " ".join(
                part
                for part in [market.get("rules_primary"), market.get("rules_secondary")]
                if part
            ),
            "market_status": market.get("status"),
            "market_close_time": market.get("close_time"),
            "provision": signal.get("provision"),
            "dimension": signal.get("dimension"),
            "pci_delta": signal.get("delta"),
            "shock_type": signal.get("shock_type"),
            "market_probability": forecast.get("market_probability"),
            "pci_rule_probability": forecast.get("rule_probability"),
            "llm_probability": forecast.get("llm_probability"),
            "model_probability": forecast.get("model_probability"),
            "edge": forecast.get("edge"),
            "confidence": forecast.get("confidence"),
            "method_version": metadata.get("version"),
            "model_provider": rationale.get("provider"),
            "model_name": rationale.get("model"),
            "source_doc": signal.get("source_doc") or {},
            "evidence": forecast.get("evidence") or {},
            "reasoning": {
                "signal": signal,
                "match": forecast.get("match") or {},
                "forecast_rationale": rationale,
                "ensemble_weights": forecast.get("ensemble_weights") or {},
            },
            "counterarguments": rationale.get("counterarguments"),
            "resolution_risk_notes": rationale.get("resolution_risk_notes"),
            "private_info_used": bool(forecast.get("private_info_used")),
            "run_id": run_id,
        }
    )


def trade_proposal_to_row(
    proposal: dict[str, Any], *, run_id: str | None = None
) -> dict[str, Any]:
    return json_clean(
        {
            "proposal_id": proposal["proposal_id"],
            "created_at": proposal.get("generated_at") or utc_now_iso(),
            "forecast_id": proposal.get("forecast_id"),
            "venue": proposal.get("venue", "kalshi"),
            "market_ticker": proposal.get("market_ticker"),
            "proposed_side": proposal.get("proposed_side"),
            "order_type": proposal.get("order_type"),
            "limit_price": proposal.get("limit_price"),
            "contracts": proposal.get("contracts"),
            "max_order_usd": proposal.get("max_order_usd"),
            "estimated_exposure_usd": proposal.get("estimated_exposure_usd"),
            "edge": proposal.get("edge"),
            "confidence": proposal.get("confidence"),
            "risk_passed": bool(proposal.get("risk_passed")),
            "approval_status": proposal.get("approval_status"),
            "human_approval_required": bool(proposal.get("human_approval_required")),
            "execution_enabled": bool(proposal.get("execution_enabled")),
            "rejection_reasons": proposal.get("rejection_reasons") or [],
            "risk_checks": proposal.get("risk_checks") or [],
            "run_id": run_id,
        }
    )


def outcome_to_row(outcome: dict[str, Any]) -> dict[str, Any]:
    return json_clean(
        {
            "outcome_id": outcome["outcome_id"],
            "forecast_id": outcome.get("forecast_id"),
            "generated_at": outcome.get("generated_at"),
            "venue": outcome.get("venue", "kalshi"),
            "market_ticker": outcome.get("market_ticker"),
            "result": outcome.get("result"),
            "settlement_value": outcome.get("settlement_value"),
            "resolved_at": outcome.get("resolved_at"),
            "outcome_source": outcome.get("outcome_source"),
            "market_status": outcome.get("market_status"),
        }
    )


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
    client.upsert_rows("provisions", rows_by_table["provisions"], on_conflict="code")
    client.upsert_rows(
        "scored_deltas",
        rows_by_table.get("scored_deltas", []),
        on_conflict="week,doc_id,provision",
    )
    client.upsert_rows(
        "pci_weekly",
        rows_by_table["pci_weekly"],
        on_conflict="provision,week",
    )
    client.upsert_rows(
        "policy_events",
        rows_by_table["policy_events"],
        on_conflict="event_id",
    )
    client.insert_rows("pipeline_runs", rows_by_table["pipeline_runs"])
    client.upsert_rows(
        "market_inventory",
        rows_by_table.get("market_inventory", []),
        on_conflict="venue,ticker",
    )
    client.upsert_rows(
        "market_assessments",
        rows_by_table.get("market_assessments", []),
        on_conflict="assessment_id",
    )
    client.insert_rows("market_snapshots", rows_by_table["market_snapshots"])
    client.upsert_rows(
        "market_discovery_candidates",
        rows_by_table.get("market_discovery_candidates", []),
        on_conflict="candidate_id",
    )
    client.upsert_rows(
        "source_documents",
        rows_by_table.get("source_documents", []),
        on_conflict="source_doc_id",
    )
    client.upsert_rows(
        "document_chunks",
        rows_by_table.get("document_chunks", []),
        on_conflict="chunk_id",
    )
    client.upsert_rows(
        "evidence_items",
        rows_by_table.get("evidence_items", []),
        on_conflict="evidence_id",
    )
    client.upsert_rows(
        "source_links",
        rows_by_table.get("source_links", []),
        on_conflict="link_id",
    )
    client.upsert_rows(
        "source_health",
        rows_by_table.get("source_health", []),
        on_conflict="source",
    )
    client.insert_rows("forecasts", rows_by_table["forecasts"])
    client.insert_rows("trade_proposals", rows_by_table["trade_proposals"])
    client.insert_rows("forecast_outcomes", rows_by_table.get("forecast_outcomes", []))
