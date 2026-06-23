from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from pci_realtime import service
from pci_realtime.agent_intake import build_agent_evidence_rows
from pci_realtime.forecast_registry.store import SupabaseRestClient
from pci_realtime.scoring.scorer import ScoringResult


DEFAULT_INPUT = Path("data/fixtures/agent_evidence_seed.json")
CORE_TABLE_COLUMNS = {
    "source_documents": {
        "source_doc_id",
        "source",
        "source_name",
        "source_type",
        "external_id",
        "title",
        "agency",
        "url",
        "published_at",
        "fetched_at",
        "content_hash",
        "text_excerpt",
        "raw_public_metadata",
    },
    "evidence_items": {
        "evidence_id",
        "source_doc_id",
        "provision",
        "evidence_type",
        "snippet",
        "normalized_signal",
        "score_dimension",
        "confidence",
        "extractor_version",
        "created_at",
    },
    "scored_deltas": {
        "week",
        "doc_id",
        "provision",
        "specificity_delta",
        "durability_delta",
        "enforceability_delta",
        "rationale",
        "confidence",
        "model",
        "prompt_version",
        "temperature",
        "scored_at",
        "cached",
        "cost_usd",
    },
    "policy_events": {
        "event_id",
        "provision",
        "week",
        "week_start",
        "doc_id",
        "doc_source",
        "agency",
        "title",
        "url",
        "pci_delta",
        "dimension_deltas",
        "rationale",
        "confidence",
        "prompt_version",
        "scored_at",
        "data_origin",
        "created_at",
    },
    "pci_weekly": {
        "provision",
        "week",
        "week_start",
        "pci",
        "specificity",
        "durability",
        "enforceability",
        "n_docs",
        "delta_this_week",
        "data_origin",
        "source_event_ids",
        "provenance_status",
        "updated_at",
    },
    "source_links": {
        "link_id",
        "evidence_id",
        "target_table",
        "target_id",
        "link_type",
        "created_at",
    },
}
CORE_TABLE_ORDER = (
    "source_documents",
    "evidence_items",
    "scored_deltas",
    "policy_events",
    "pci_weekly",
    "source_links",
)
CORE_CONFLICTS = {
    "source_documents": "source_doc_id",
    "evidence_items": "evidence_id",
    "scored_deltas": "week,doc_id,provision",
    "policy_events": "event_id",
    "pci_weekly": "provision,week",
    "source_links": "link_id",
}


@dataclass(frozen=True)
class DeterministicScorer:
    """Validation-only scorer for dry runs without model credentials."""

    def score_document(
        self,
        document: Mapping[str, Any],
        provision: str,
        cache_metadata: Mapping[str, Any] | None = None,
    ) -> ScoringResult:
        return ScoringResult(
            doc_id=str(document["doc_id"]),
            provision=provision,
            specificity_delta=0.0,
            durability_delta=0.0,
            enforceability_delta=0.0,
            rationale="Validation dry run: citation is structured but no live model score was produced.",
            confidence=0.5,
            model="deterministic-validation",
            prompt_version="agent-evidence-seed-validation",
            temperature=0.0,
            scored_at=pd.Timestamp.now(tz="UTC"),
            cached=True,
            cost_usd=0.0,
        )


def load_payloads(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        msg = f"{path} must contain a JSON array"
        raise ValueError(msg)
    return [dict(item) for item in payload]


def dry_run(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [
        build_agent_evidence_rows(
            provision=item["provision"],
            source=item["source"],
            citation=item["citation"],
            claim=item["claim"],
            idempotency_key=item["idempotency_key"],
            agent_name="agent-coi-seed",
            scorer=DeterministicScorer(),
        ).payload()
        for item in payloads
    ]
    return {"mode": "dry_run", "count": len(rows), "submissions": rows}


def promote(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [
        service.submit_policy_evidence(
            provision=item["provision"],
            source=item["source"],
            citation=item["citation"],
            claim=item["claim"],
            idempotency_key=item["idempotency_key"],
            agent_name="agent-coi-seed",
            reviewed_by="agent-coi-seed",
            review_decision_code="seed_fixture",
            approval_basis="Seed fixture reviewed for local provisioning.",
            source_text=str(item["citation"]["quote"]),
        )
        for item in payloads
    ]
    return {"mode": "promote", "count": len(rows), "submissions": rows}


def promote_core_registry(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    client = SupabaseRestClient.from_env()
    if client is None:
        msg = "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required"
        raise RuntimeError(msg)

    scored_rows: list[dict[str, Any]] = client.select_rows("scored_deltas")
    results = []
    for item in sorted(payloads, key=payload_sort_key):
        result = build_agent_evidence_rows(
            provision=item["provision"],
            source=item["source"],
            citation=item["citation"],
            claim=item["claim"],
            idempotency_key=item["idempotency_key"],
            agent_name="agent-coi-seed",
            historical_scored=scored_rows,
        )
        write_core_registry_rows(result.rows_by_table, client=client)
        scored_rows.extend(result.rows_by_table["scored_deltas"])
        results.append(result.payload())
    return {"mode": "core_registry", "count": len(results), "submissions": results}


def write_core_registry_rows(
    rows_by_table: Mapping[str, list[dict[str, Any]]],
    *,
    client: SupabaseRestClient,
) -> None:
    for table in CORE_TABLE_ORDER:
        rows = [
            {
                key: value
                for key, value in row.items()
                if key in CORE_TABLE_COLUMNS[table]
            }
            for row in rows_by_table.get(table, [])
        ]
        client.upsert_rows(table, rows, on_conflict=CORE_CONFLICTS[table])


def payload_sort_key(item: Mapping[str, Any]) -> str:
    source = item.get("source")
    if isinstance(source, Mapping):
        return str(source.get("published_at") or "")
    return ""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Provision source-cited Agent COI evidence through the PCIndex service."
    )
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate payload shape and deterministic row construction without writing.",
    )
    parser.add_argument(
        "--core-registry",
        action="store_true",
        help="Write scored evidence into the existing public registry tables before Agent COI migration 005 is applied.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    payloads = load_payloads(Path(args.input))
    if args.dry_run:
        result = dry_run(payloads)
    elif args.core_registry:
        result = promote_core_registry(payloads)
    else:
        result = promote(payloads)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
