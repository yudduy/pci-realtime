from __future__ import annotations

from datetime import date

from pci_realtime.agent_research import (
    EvidenceCandidate,
    EvidenceResearchResult,
    build_agent_research_prompt,
    candidate_idempotency_key,
    candidate_to_submission,
    normalize_research_result,
    web_search_tools,
)


def test_research_prompt_names_tracked_policies() -> None:
    prompt = build_agent_research_prompt(
        since=date(2026, 6, 1),
        provisions=("45V", "45X"),
        max_candidates_per_provision=1,
    )

    assert "2026-06-01" in prompt
    assert "45V: Clean Hydrogen Production Credit" in prompt
    assert "45X: Advanced Manufacturing Production Credit" in prompt


def test_web_search_tools_are_domain_limited() -> None:
    tools = web_search_tools(["irs.gov", "treasury.gov"])

    assert tools == [
        {
            "type": "web_search",
            "filters": {"allowed_domains": ["irs.gov", "treasury.gov"]},
            "search_context_size": "medium",
        }
    ]


def test_normalize_research_result_dedupes_and_canonicalizes_url() -> None:
    candidate = EvidenceCandidate(
        provision="45v",
        source_title=" Clean Hydrogen Production Credit ",
        source_name=" IRS ",
        url="https://www.irs.gov/path?utm_source=x&b=2&a=1#frag",
        citation_quote="  quoted source span  ",
        claim="  IRS guidance confirms eligibility mechanics. ",
    )

    result = normalize_research_result(
        EvidenceResearchResult(
            generated_for="test",
            candidates=[candidate, candidate],
        )
    )

    assert len(result.candidates) == 1
    normalized = result.candidates[0]
    assert normalized.provision == "45V"
    assert normalized.url == "https://www.irs.gov/path?a=1&b=2"
    assert normalized.source_title == "Clean Hydrogen Production Credit"
    assert normalized.source_name == "IRS"


def test_candidate_submission_payload_is_stable() -> None:
    candidate = EvidenceCandidate(
        provision="45X",
        source_title="Advanced Manufacturing Production Credit",
        source_name="Internal Revenue Service",
        url="https://www.irs.gov/credits-deductions/advanced-manufacturing-production-credit",
        published_at="2026-02-14",
        citation_quote="The advanced manufacturing production credit is a tax credit.",
        citation_section="Overview",
        claim="IRS guidance confirms the credit remains administrable through published guidance.",
    )

    payload = candidate_to_submission(candidate)

    assert payload["provision"] == "45X"
    assert payload["source"]["title"] == "Advanced Manufacturing Production Credit"
    assert payload["citation"]["quote"].startswith("The advanced")
    assert payload["idempotency_key"] == candidate_idempotency_key(candidate)
