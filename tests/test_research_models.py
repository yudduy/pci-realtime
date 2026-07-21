from __future__ import annotations

from datetime import date

from pci_realtime.pipeline.daily_research import (
    build_lane_brief,
    finding_to_candidate_row,
)
from pci_realtime.research.models import (
    CANDIDATE_SCHEMA_VERSION,
    ResearchFinding,
    classify_source_class,
    finding_candidate_id,
    finding_idempotency_key,
    promotability_for,
)
from pci_realtime.research.prompts import build_lane_research_prompt


def _finding(**overrides) -> ResearchFinding:
    values = {
        "provision": "45v",
        "title": "Clean hydrogen guidance",
        "url": "https://www.irs.gov/path?utm_source=test&b=2&a=1#section",
        "source_name": "IRS",
        "citation_quote": " The agency  clarified eligibility. ",
        "claim": " IRS  clarified eligibility mechanics. ",
        "provider": "fixture",
    }
    values.update(overrides)
    return ResearchFinding(**values)


def test_source_classification_trusts_domains_not_provider_labels() -> None:
    assert classify_source_class("https://www.irs.gov/x", "news") == "official"
    assert classify_source_class("https://home.treasury.gov/x", None) == "official"
    assert classify_source_class("https://medium.com/x", "official") == "news"
    assert classify_source_class("https://irs.gov.attacker.com/x", "official") == "news"


def test_promotability_requires_an_official_source_and_nonblank_quote() -> None:
    assert promotability_for("official", None) == "context_only"
    assert promotability_for("official", "  ") == "context_only"
    assert promotability_for("news", "quoted") == "context_only"
    assert promotability_for("official", "quoted") == "ledger_candidate"


def test_candidate_and_idempotency_ids_share_normalized_hash() -> None:
    first = _finding()
    second = _finding(
        url="https://www.irs.gov/path?a=1&b=2",
        claim="IRS clarified eligibility mechanics.",
        citation_quote="The agency clarified eligibility.",
    )

    candidate_id = finding_candidate_id(first)
    idempotency_key = finding_idempotency_key(first)

    assert candidate_id == finding_candidate_id(second)
    assert idempotency_key == finding_idempotency_key(second)
    assert candidate_id.split(":", 2)[-1] == idempotency_key.split(":", 2)[-1]
    assert len(candidate_id.split(":", 2)[-1]) == 24


def test_candidate_row_matches_migration_006_column_contract() -> None:
    row = finding_to_candidate_row(
        _finding(raw_public_metadata={"query_id": "query-1"}),
        run_id="00000000-0000-0000-0000-000000000001",
        discovered_at="2026-07-20T00:00:00+00:00",
    )

    assert list(row) == [
        "candidate_id",
        "run_id",
        "schema_version",
        "discovered_at",
        "provision",
        "source_class",
        "review_state",
        "promotability",
        "source_name",
        "source_type",
        "canonical_url",
        "resolved_primary_url",
        "title",
        "published_at",
        "citation_quote",
        "citation_section",
        "claim",
        "decision_relevance",
        "why_it_matters",
        "confidence",
        "search_query",
        "retrieved_at",
        "model_name",
        "prompt_version",
        "idempotency_key",
        "duplicate_of",
        "related_evidence_ids",
        "reviewer_note",
        "reviewed_at",
        "promoted_submission_id",
        "promotion_result",
        "raw_public_metadata",
        "raw_private_metadata",
    ]
    assert row["schema_version"] == CANDIDATE_SCHEMA_VERSION
    assert row["raw_public_metadata"] == {
        "provider": "fixture",
        "query_id": "query-1",
    }
    assert row["raw_private_metadata"] == {}


def test_lane_prompt_contains_vertical_provisions_keywords_and_recency() -> None:
    brief = build_lane_brief(
        "clean-energy-finance",
        since=date(2026, 7, 1),
    )

    prompt = build_lane_research_prompt(brief)

    assert "Clean Energy Finance" in prompt
    assert "2026-07-01" in prompt
    assert "50141: Loan Programs Office Funding" in prompt
    assert "50144: Energy Infrastructure Reinvestment" in prompt
    assert "DOE loan guarantee program funding" in prompt
    assert "energy infrastructure reinvestment" in prompt
