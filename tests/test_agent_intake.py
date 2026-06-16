from __future__ import annotations

import json
import importlib.util
import sys
from pathlib import Path
from typing import Any, Mapping

import httpx
import pandas as pd
import pytest

from pci_realtime import service
from pci_realtime.agent_intake import (
    build_agent_evidence_rows,
    canonicalize_url,
    idempotency_key_hash,
)
from pci_realtime.scoring.scorer import ScoringResult
from pci_realtime.service_errors import (
    BadRequest,
    ScoringUnavailable,
    SupabaseUnavailable,
)


_PROVISION_SCRIPT = (
    Path(__file__).resolve().parents[1] / "scripts" / "provision_agent_evidence.py"
)
_PROVISION_SPEC = importlib.util.spec_from_file_location(
    "provision_agent_evidence", _PROVISION_SCRIPT
)
assert _PROVISION_SPEC and _PROVISION_SPEC.loader
_PROVISION_MODULE = importlib.util.module_from_spec(_PROVISION_SPEC)
_PROVISION_SPEC.loader.exec_module(_PROVISION_MODULE)
write_core_registry_rows = _PROVISION_MODULE.write_core_registry_rows


class FixedScorer:
    def score_document(
        self,
        document: Mapping[str, Any],
        provision: str,
        cache_metadata: Mapping[str, Any] | None = None,
    ) -> ScoringResult:
        return ScoringResult(
            doc_id=str(document["doc_id"]),
            provision=provision,
            specificity_delta=0.2,
            durability_delta=0.0,
            enforceability_delta=0.1,
            rationale="Cited evidence clarifies implementation mechanics.",
            confidence=0.81,
            model="test",
            prompt_version="test",
            temperature=0.0,
            scored_at=pd.Timestamp("2026-06-15T00:00:00Z"),
            cached=False,
            cost_usd=0.0,
        )


class FailingScorer:
    def score_document(
        self,
        document: Mapping[str, Any],
        provision: str,
        cache_metadata: Mapping[str, Any] | None = None,
    ) -> ScoringResult:
        raise RuntimeError("no model")


class RecordingClient:
    def __init__(self, existing: list[dict[str, Any]] | None = None) -> None:
        self.existing = existing or []
        self.upserts: list[tuple[str, list[dict[str, Any]], str | None]] = []

    def select_rows(
        self,
        table: str,
        *,
        columns: str = "*",
        params: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        if table == "evidence_submissions":
            return self.existing
        if table == "scored_deltas":
            return []
        return []

    def upsert_rows(
        self,
        table: str,
        rows: list[dict[str, Any]],
        *,
        on_conflict: str | None = None,
    ) -> None:
        self.upserts.append((table, rows, on_conflict))


class MissingAgentMigrationClient(RecordingClient):
    def upsert_rows(
        self,
        table: str,
        rows: list[dict[str, Any]],
        *,
        on_conflict: str | None = None,
    ) -> None:
        if table == "agent_runs":
            request = httpx.Request(
                "POST",
                "https://example.supabase.co/rest/v1/agent_runs",
            )
            response = httpx.Response(404, request=request)
            raise httpx.HTTPStatusError("not found", request=request, response=response)
        super().upsert_rows(table, rows, on_conflict=on_conflict)


def source() -> dict[str, Any]:
    return {
        "url": "https://www.irs.gov/credits?utm_source=x&b=2&a=1",
        "title": "Clean hydrogen production credit guidance",
        "source_name": "Internal Revenue Service",
        "published_at": "2026-06-15T00:00:00Z",
    }


def citation() -> dict[str, Any]:
    return {
        "quote": "The credit applies to qualified clean hydrogen production.",
        "section": "Eligibility",
    }


def test_canonicalize_url_removes_tracking_and_sorts_query() -> None:
    assert (
        canonicalize_url("HTTPS://Example.COM/path?utm_source=x&b=2&a=1#frag")
        == "https://example.com/path?a=1&b=2"
    )


def test_build_agent_evidence_rows_promotes_cited_scoreable_evidence() -> None:
    result = build_agent_evidence_rows(
        provision="45v",
        source=source(),
        citation=citation(),
        claim="IRS guidance clarifies 45V eligibility mechanics.",
        idempotency_key="run-1:45v:irs",
        agent_run_id="agent-run:test",
        scorer=FixedScorer(),
        submitted_at="2026-06-15T00:00:00Z",
    )

    assert result.status == "promoted"
    assert result.provision == "45V"
    assert result.source_doc_id.startswith("source:internal-revenue-service:")
    assert result.evidence_id.startswith("evidence:45V:")
    assert result.rows_by_table["source_documents"][0]["canonical_url"].endswith(
        "?a=1&b=2"
    )
    assert result.rows_by_table["evidence_items"][0]["citation_quote"]
    assert result.rows_by_table["scored_deltas"][0]["specificity_delta"] == 0.2
    assert result.rows_by_table["policy_events"][0]["data_origin"] == "agent_evidence"
    assert result.rows_by_table["pci_weekly"]


def test_agent_evidence_seed_fixture_promotes_all_payloads() -> None:
    payloads = json.loads(
        Path("data/fixtures/agent_evidence_seed.json").read_text(encoding="utf-8")
    )

    results = [
        build_agent_evidence_rows(
            provision=item["provision"],
            source=item["source"],
            citation=item["citation"],
            claim=item["claim"],
            idempotency_key=item["idempotency_key"],
            agent_name="agent-coi-seed",
            scorer=FixedScorer(),
            submitted_at="2026-06-15T00:00:00Z",
        )
        for item in payloads
    ]

    assert len(results) == len(payloads)
    assert {result.status for result in results} == {"promoted"}
    assert {result.provision for result in results} == {
        "30D",
        "45Q",
        "45V",
        "45X",
        "50141",
        "50144",
    }
    assert all(
        result.evidence_id.startswith(f"evidence:{result.provision}:")
        for result in results
    )
    assert all(
        result.rows_by_table["evidence_items"][0]["citation_quote"]
        for result in results
    )


def test_invalid_or_uncited_evidence_is_rejected_cleanly() -> None:
    with pytest.raises(BadRequest):
        build_agent_evidence_rows(
            provision="99Z",
            source=source(),
            citation=citation(),
            claim="claim",
            idempotency_key="bad",
            scorer=FixedScorer(),
        )

    with pytest.raises(BadRequest, match="quoted source span"):
        build_agent_evidence_rows(
            provision="45V",
            source=source(),
            citation={},
            claim="claim",
            idempotency_key="bad",
            scorer=FixedScorer(),
        )


def test_unscoreable_evidence_is_not_promoted() -> None:
    with pytest.raises(ScoringUnavailable):
        build_agent_evidence_rows(
            provision="45V",
            source=source(),
            citation=citation(),
            claim="claim",
            idempotency_key="unscoreable",
            scorer=FailingScorer(),
        )


def test_service_duplicate_submission_returns_existing_row() -> None:
    key_hash = idempotency_key_hash("duplicate-key")
    client = RecordingClient(
        existing=[
            {
                "submission_id": "submission:existing",
                "idempotency_key_hash": key_hash,
                "agent_run_id": "agent-run:existing",
                "provision": "45V",
                "status": "promoted",
                "source_doc_id": "source:existing",
                "evidence_id": "evidence:existing",
                "event_id": "event:existing",
                "claim_hash": "claim:existing",
                "submitted_at": "2026-06-15T00:00:00Z",
                "promoted_at": "2026-06-15T00:00:00Z",
            }
        ]
    )

    result = service.submit_policy_evidence(
        provision="45V",
        source=source(),
        citation=citation(),
        claim="claim",
        idempotency_key="duplicate-key",
        client=client,  # type: ignore[arg-type]
        scorer=FixedScorer(),
    )

    assert result["status"] == "duplicate"
    assert result["submission"]["submission_id"] == "submission:existing"
    assert client.upserts == []


def test_service_writes_promoted_rows_in_dependency_order() -> None:
    client = RecordingClient()

    result = service.submit_policy_evidence(
        provision="45V",
        source=source(),
        citation=citation(),
        claim="IRS guidance clarifies 45V eligibility mechanics.",
        idempotency_key="new-key",
        client=client,  # type: ignore[arg-type]
        scorer=FixedScorer(),
    )

    assert result["status"] == "promoted"
    assert [call[0] for call in client.upserts] == [
        "agent_runs",
        "source_documents",
        "evidence_items",
        "scored_deltas",
        "policy_events",
        "pci_weekly",
        "source_links",
        "evidence_submissions",
    ]


def test_service_reports_missing_agent_intake_migration_cleanly() -> None:
    client = MissingAgentMigrationClient()

    with pytest.raises(SupabaseUnavailable, match="005_agent_evidence_intake"):
        service.submit_policy_evidence(
            provision="45V",
            source=source(),
            citation=citation(),
            claim="IRS guidance clarifies 45V eligibility mechanics.",
            idempotency_key="migration-missing",
            client=client,  # type: ignore[arg-type]
            scorer=FixedScorer(),
        )


def test_core_registry_writer_strips_agent_intake_only_columns() -> None:
    client = RecordingClient()
    result = build_agent_evidence_rows(
        provision="45V",
        source=source(),
        citation=citation(),
        claim="IRS guidance clarifies 45V eligibility mechanics.",
        idempotency_key="core-key",
        scorer=FixedScorer(),
    )

    write_core_registry_rows(result.rows_by_table, client=client)  # type: ignore[arg-type]

    calls_by_table = {table: rows for table, rows, _ in client.upserts}
    assert "agent_runs" not in calls_by_table
    assert "evidence_submissions" not in calls_by_table
    assert "canonical_url" not in calls_by_table["source_documents"][0]
    assert "citation_quote" not in calls_by_table["evidence_items"][0]
    assert "claim_hash" not in calls_by_table["evidence_items"][0]
    assert calls_by_table["policy_events"][0]["data_origin"] == "agent_evidence"


def test_mcp_server_exposes_write_tools() -> None:
    pytest.importorskip("mcp")
    from pci_realtime import mcp_server

    assert callable(mcp_server.submit_policy_evidence)
    assert callable(mcp_server.ingest_source_url)


def test_mcp_stdio_server_lists_tools_and_reads_policies() -> None:
    pytest.importorskip("mcp")
    import anyio
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    root = Path(__file__).resolve().parents[1]

    async def run_smoke() -> None:
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "pci_realtime.mcp_server"],
            cwd=str(root),
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                tool_names = {tool.name for tool in tools.tools}
                assert {
                    "status",
                    "list_policies",
                    "current_pci",
                    "policy_dossier",
                    "submit_policy_evidence",
                    "ingest_source_url",
                    "get_evidence_trace",
                } <= tool_names

                result = await session.call_tool("list_policies", {})
                payload = json.loads(result.content[0].text)
                assert payload["count"] == 6
                assert {policy["code"] for policy in payload["policies"]} == {
                    "30D",
                    "45Q",
                    "45V",
                    "45X",
                    "50141",
                    "50144",
                }

    anyio.run(run_smoke)
