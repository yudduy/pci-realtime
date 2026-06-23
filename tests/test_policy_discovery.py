from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from pci_realtime import service
from pci_realtime.pipeline.policy_discovery import (
    PolicyDiscoveryLead,
    PolicyDiscoveryResearchResult,
    build_policy_briefs,
    build_policy_discovery_rows,
    candidate_rows_from_leads,
    policy_candidate_id,
    write_policy_discovery_rows,
)
from pci_realtime.scoring.scorer import ScoringResult
from pci_realtime.service_errors import BadRequest


FIXED_RUN_ID = "00000000-0000-0000-0000-000000000101"


def test_policy_discovery_candidates_keep_news_out_of_ledger() -> None:
    official_doc = {
        "doc_id": "treasury:45v-guidance",
        "date": "2026-06-20",
        "source": "treasury",
        "agency": "Treasury",
        "title": "Clean Hydrogen Production Credit Guidance",
        "body": "Treasury clarifies Section 45V eligibility and documentation rules.",
        "url": "https://home.treasury.gov/policy?utm_source=x&b=2&a=1",
        "provisions_mentioned": ["45V"],
    }
    web_result = PolicyDiscoveryResearchResult(
        generated_for="test",
        leads=[
            PolicyDiscoveryLead(
                provision="45V",
                source_title="Analysts expect new hydrogen guidance",
                source_name="Policy News",
                url="https://example.com/news/hydrogen-guidance",
                citation_quote="Analysts expect the agency to clarify the rules.",
                claim="A news lead points to possible 45V implementation changes.",
                source_class="news",
                promotability="ledger_candidate",
                confidence=0.6,
                search_query="45V hydrogen guidance news",
            )
        ],
    )

    rows = build_policy_discovery_rows(
        since=date(2026, 6, 1),
        through=date(2026, 6, 23),
        run_id=FIXED_RUN_ID,
        include_official_ingest=False,
        official_documents=[official_doc],
        web_result=web_result,
    )

    assert rows["pipeline_runs"][0]["run_type"] == "policy_discovery"
    assert "scored_deltas" not in rows
    assert "pci_weekly" not in rows
    assert len(rows["policy_source_candidates"]) == 2

    official = next(
        row
        for row in rows["policy_source_candidates"]
        if row["source_class"] == "official"
    )
    assert official["canonical_url"] == "https://home.treasury.gov/policy?a=1&b=2"
    assert official["review_state"] == "queued"
    assert official["promotability"] == "ledger_candidate"

    news = next(
        row for row in rows["policy_source_candidates"] if row["source_class"] == "news"
    )
    assert news["review_state"] == "needs_primary_source"
    assert news["promotability"] == "ledger_candidate"


def test_policy_discovery_marks_existing_evidence_url_duplicate() -> None:
    lead = PolicyDiscoveryLead(
        provision="45X",
        source_title="Advanced manufacturing update",
        source_name="IRS",
        url="https://www.irs.gov/credits/45x",
        citation_quote="The credit applies to eligible components.",
        claim="IRS confirms 45X administrative mechanics.",
        source_class="official",
        promotability="ledger_candidate",
    )

    rows = candidate_rows_from_leads(
        [lead],
        run_id=FIXED_RUN_ID,
        existing_context=[
            {
                "provision": "45X",
                "canonical_url": "https://www.irs.gov/credits/45x",
                "evidence_id": "evidence:45X:existing",
                "source_title": "Existing 45X evidence",
            }
        ],
    )

    assert rows[0]["review_state"] == "duplicate"
    assert rows[0]["duplicate_of"] == "https://www.irs.gov/credits/45x"
    assert rows[0]["related_evidence_ids"] == ["evidence:45X:existing"]


def test_policy_discovery_promotability_fails_closed_for_priority_words() -> None:
    lead = PolicyDiscoveryLead(
        provision="45V",
        source_title="Hydrogen lead",
        source_name="Policy News",
        url="https://example.com/hydrogen-lead",
        citation_quote="A public lead discusses 45V timing.",
        claim="A lead may matter for 45V implementation timing.",
        source_class="news",
        promotability="high",
    )

    assert lead.promotability == "context_only"


class RecordingSupabaseClient:
    def __init__(self, rows: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self.rows = rows or {}
        self.inserts: list[tuple[str, int]] = []
        self.upserts: list[tuple[str, int, str | None]] = []

    def insert_rows(self, table: str, rows: list[dict[str, Any]]) -> None:
        self.inserts.append((table, len(rows)))
        self.rows.setdefault(table, []).extend(rows)

    def upsert_rows(
        self,
        table: str,
        rows: list[dict[str, Any]],
        *,
        on_conflict: str | None = None,
    ) -> None:
        self.upserts.append((table, len(rows), on_conflict))
        self.rows.setdefault(table, []).extend(rows)

    def select_rows(
        self,
        table: str,
        *,
        columns: str = "*",
        params: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        del columns
        rows = list(self.rows.get(table, []))
        if params and "candidate_id" in params:
            candidate_id = params["candidate_id"].removeprefix("eq.")
            rows = [row for row in rows if row.get("candidate_id") == candidate_id]
        if params and "review_state" in params:
            state = params["review_state"].removeprefix("eq.")
            rows = [row for row in rows if row.get("review_state") == state]
        return rows


def test_policy_discovery_write_order_keeps_run_before_candidates() -> None:
    rows = {
        "pipeline_runs": [{"run_id": FIXED_RUN_ID, "run_type": "policy_discovery"}],
        "policy_source_candidates": [{"candidate_id": "policy-source:test"}],
        "source_health": [],
    }
    client = RecordingSupabaseClient()

    write_policy_discovery_rows(rows, client=client)  # type: ignore[arg-type]

    assert client.inserts[0] == ("pipeline_runs", 1)
    assert ("policy_source_candidates", 1, "candidate_id") in client.upserts
    assert all(
        table not in {"scored_deltas", "pci_weekly"} for table, *_ in client.upserts
    )


def test_policy_briefs_include_confirmed_evidence_and_reviewed_context() -> None:
    briefs = build_policy_briefs(
        provisions=("45V",),
        evidence_items=[
            {
                "provision": "45V",
                "evidence_id": "evidence:45V:1",
                "source_title": "Treasury guidance",
                "created_at": "2026-06-20T00:00:00Z",
            }
        ],
        context_candidates=[
            {
                "provision": "45V",
                "review_state": "approved",
                "promotability": "context_only",
                "title": "Industry analysis",
                "discovered_at": "2026-06-21T00:00:00Z",
            }
        ],
    )

    assert (
        briefs[0]["summary"]
        == "45V has 1 confirmed cited evidence item(s) in the ledger."
    )
    assert len(briefs[0]["confirmed_evidence"]) == 1
    assert len(briefs[0]["reviewed_context_leads"]) == 1


class FakeScorer:
    def score_document(
        self,
        document: dict[str, Any],
        provision: str,
        cache_metadata: dict[str, Any] | None = None,
    ) -> ScoringResult:
        del cache_metadata
        return ScoringResult(
            doc_id=str(document["doc_id"]),
            provision=provision,
            specificity_delta=0.1,
            durability_delta=0.0,
            enforceability_delta=0.0,
            rationale="Cited evidence modestly improves specificity.",
            confidence=0.7,
            model="fake",
            prompt_version="test",
            temperature=0.0,
            scored_at=pd.Timestamp("2026-06-23T00:00:00Z"),
            cached=True,
            cost_usd=0.0,
        )


def _candidate(
    source_class: str = "official", promotability: str = "ledger_candidate"
) -> dict[str, Any]:
    return {
        "candidate_id": policy_candidate_id(
            "45V",
            "https://home.treasury.gov/45v",
            "Treasury clarifies 45V.",
            "Treasury clarifies 45V eligibility.",
        ),
        "run_id": FIXED_RUN_ID,
        "discovered_at": "2026-06-23T00:00:00Z",
        "provision": "45V",
        "source_class": source_class,
        "review_state": "queued",
        "promotability": promotability,
        "source_name": "Treasury",
        "source_type": "policy_discovery_lead",
        "canonical_url": "https://home.treasury.gov/45v",
        "resolved_primary_url": "https://home.treasury.gov/45v",
        "title": "45V guidance",
        "published_at": "2026-06-20",
        "citation_quote": "Treasury clarifies 45V eligibility.",
        "citation_section": "Overview",
        "claim": "Treasury clarifies 45V.",
        "decision_relevance": "implementation_watch",
        "why_it_matters": "Review 45V implementation.",
        "confidence": 0.8,
        "idempotency_key": "policy-discovery:45V:test",
        "related_evidence_ids": [],
        "promotion_result": {},
        "raw_public_metadata": {},
    }


def test_promote_policy_source_candidate_uses_governed_intake() -> None:
    client = RecordingSupabaseClient({"policy_source_candidates": [_candidate()]})

    result = service.promote_policy_source_candidate(
        _candidate()["candidate_id"],
        client=client,  # type: ignore[arg-type]
        scorer=FakeScorer(),
    )

    assert result["status"] == "approved"
    assert any(table == "scored_deltas" for table, *_ in client.upserts)
    assert any(table == "pci_weekly" for table, *_ in client.upserts)
    updated_candidates = [
        row
        for row in client.rows["policy_source_candidates"]
        if row.get("review_state") == "approved"
    ]
    assert updated_candidates


def test_promote_policy_source_candidate_blocks_news_and_context() -> None:
    news_client = RecordingSupabaseClient(
        {"policy_source_candidates": [_candidate(source_class="news")]}
    )
    context_client = RecordingSupabaseClient(
        {"policy_source_candidates": [_candidate(promotability="context_only")]}
    )

    try:
        service.promote_policy_source_candidate(
            _candidate()["candidate_id"],
            client=news_client,  # type: ignore[arg-type]
            scorer=FakeScorer(),
        )
    except BadRequest as exc:
        assert "official primary-source" in exc.message
    else:  # pragma: no cover
        raise AssertionError("news candidate was promoted")

    try:
        service.promote_policy_source_candidate(
            _candidate()["candidate_id"],
            client=context_client,  # type: ignore[arg-type]
            scorer=FakeScorer(),
        )
    except BadRequest as exc:
        assert "ledger_candidate" in exc.message
    else:  # pragma: no cover
        raise AssertionError("context candidate was promoted")
