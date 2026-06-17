from __future__ import annotations

import os
from datetime import date
from typing import Any, Iterable, Sequence

from pydantic import BaseModel, Field, field_validator

from pci_realtime.agent_intake import canonicalize_url, normalize_provision
from pci_realtime.config import TRACKED_PROVISIONS
from pci_realtime.forecast_registry.evidence import stable_hash
from pci_realtime.forecast_registry.policy import PROVISION_DETAILS


OFFICIAL_SOURCE_DOMAINS = (
    "federalregister.gov",
    "irs.gov",
    "treasury.gov",
    "home.treasury.gov",
    "energy.gov",
    "lpo.energy.gov",
    "congress.gov",
    "govinfo.gov",
    "regulations.gov",
    "reginfo.gov",
    "whitehouse.gov",
)
DEFAULT_AGENT_RESEARCH_MODEL = os.getenv("PCI_AGENT_RESEARCH_MODEL", "gpt-5.4-mini")


class EvidenceCandidate(BaseModel):
    provision: str = Field(description="One tracked PCIndex policy code.")
    source_title: str = Field(description="Public source title.")
    source_name: str = Field(description="Agency or official publisher name.")
    url: str = Field(description="Public citeable source URL.")
    published_at: str | None = Field(
        default=None,
        description="Visible publication or update date in ISO-like form when known.",
    )
    citation_quote: str = Field(
        description="Short exact source quote that supports the claim."
    )
    citation_section: str | None = Field(
        default=None,
        description="Section, page, heading, or anchor when visible.",
    )
    claim: str = Field(
        description=(
            "One sentence explaining what the source changes or confirms for "
            "policy credibility."
        )
    )
    evidence_type: str = Field(
        default="official_policy_source",
        description="official_policy_source, agency_guidance, statute, rulemaking, or funding_notice.",
    )

    @field_validator("provision")
    @classmethod
    def valid_provision(cls, value: str) -> str:
        return normalize_provision(value)


class EvidenceResearchResult(BaseModel):
    generated_for: str
    candidates: list[EvidenceCandidate]
    notes: list[str] = Field(default_factory=list)


def build_agent_research_prompt(
    *,
    since: date,
    provisions: Sequence[str] = TRACKED_PROVISIONS,
    max_candidates_per_provision: int = 2,
) -> str:
    lines = [
        "Find current public, citeable policy evidence for PCIndex.",
        f"Only include sources published or materially updated on or after {since.isoformat()} when possible.",
        "Prefer primary official sources over news or commentary.",
        "Use exact quote anchors. Do not invent quotes, dates, titles, or URLs.",
        "Return only evidence that can map to one tracked policy code.",
        f"Return at most {max_candidates_per_provision} candidates per provision.",
        "",
        "Tracked policies:",
    ]
    for code in provisions:
        details = PROVISION_DETAILS[normalize_provision(code)]
        lines.append(f"- {code}: {details['name']} ({details['primary_channel']})")
    return "\n".join(lines)


def web_search_tools(
    allowed_domains: Iterable[str] = OFFICIAL_SOURCE_DOMAINS,
) -> list[dict[str, Any]]:
    return [
        {
            "type": "web_search",
            "filters": {"allowed_domains": sorted(set(allowed_domains))},
            "search_context_size": "medium",
        }
    ]


def research_evidence_with_web_search(
    *,
    since: date,
    provisions: Sequence[str] = TRACKED_PROVISIONS,
    max_candidates_per_provision: int = 2,
    model: str = DEFAULT_AGENT_RESEARCH_MODEL,
    allowed_domains: Iterable[str] = OFFICIAL_SOURCE_DOMAINS,
    client: Any | None = None,
) -> EvidenceResearchResult:
    if client is None:
        from openai import OpenAI

        client = OpenAI()

    response = client.responses.parse(
        model=model,
        instructions=(
            "You are a policy evidence research agent. Search official public "
            "sources and produce structured, citeable PCIndex evidence only."
        ),
        input=build_agent_research_prompt(
            since=since,
            provisions=provisions,
            max_candidates_per_provision=max_candidates_per_provision,
        ),
        tools=web_search_tools(allowed_domains),
        text_format=EvidenceResearchResult,
        max_output_tokens=8000,
    )
    parsed = getattr(response, "output_parsed", None)
    if parsed is None:
        parsed = EvidenceResearchResult.model_validate_json(response.output_text)
    return normalize_research_result(parsed)


def normalize_research_result(result: EvidenceResearchResult) -> EvidenceResearchResult:
    seen: set[tuple[str, str, str]] = set()
    candidates: list[EvidenceCandidate] = []
    for candidate in result.candidates:
        normalized = candidate.model_copy(
            update={
                "provision": normalize_provision(candidate.provision),
                "url": canonicalize_url(candidate.url),
                "source_title": " ".join(candidate.source_title.split()),
                "source_name": " ".join(candidate.source_name.split()),
                "citation_quote": " ".join(candidate.citation_quote.split()),
                "claim": " ".join(candidate.claim.split()),
            }
        )
        key = (
            normalized.provision,
            normalized.url,
            stable_hash(normalized.claim, normalized.citation_quote),
        )
        if key in seen:
            continue
        seen.add(key)
        candidates.append(normalized)
    return EvidenceResearchResult(
        generated_for=result.generated_for,
        candidates=candidates,
        notes=list(result.notes),
    )


def candidate_idempotency_key(candidate: EvidenceCandidate) -> str:
    return ":".join(
        [
            "agent-research",
            candidate.provision,
            stable_hash(
                canonicalize_url(candidate.url),
                candidate.claim,
                candidate.citation_quote,
            )[:24],
        ]
    )


def candidate_to_submission(candidate: EvidenceCandidate) -> dict[str, Any]:
    return {
        "provision": candidate.provision,
        "source": {
            "url": canonicalize_url(candidate.url),
            "title": candidate.source_title,
            "source_name": candidate.source_name,
            "published_at": candidate.published_at,
        },
        "citation": {
            "quote": candidate.citation_quote,
            "section": candidate.citation_section,
            "url": canonicalize_url(candidate.url),
        },
        "claim": candidate.claim,
        "idempotency_key": candidate_idempotency_key(candidate),
    }


def research_result_payload(result: EvidenceResearchResult) -> dict[str, Any]:
    return {
        "generated_for": result.generated_for,
        "candidate_count": len(result.candidates),
        "candidates": [
            {
                **candidate.model_dump(),
                "idempotency_key": candidate_idempotency_key(candidate),
            }
            for candidate in result.candidates
        ],
        "notes": result.notes,
    }
