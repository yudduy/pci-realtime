from __future__ import annotations

from datetime import date
from typing import Any, Iterable
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

from pci_realtime.agent_intake import canonicalize_url, normalize_provision
from pci_realtime.agent_research import OFFICIAL_SOURCE_DOMAINS
from pci_realtime.registry.evidence import stable_hash


RESEARCH_PROMPT_VERSION = "daily-research-v1"
CANDIDATE_SCHEMA_VERSION = "policy-source-candidate-v1"


class LaneBrief(BaseModel):
    model_config = ConfigDict(frozen=True)

    vertical_id: str
    vertical_name: str
    provisions: tuple[str, ...]
    coverage_note: str
    keywords: tuple[str, ...]
    since: date
    max_findings: int = Field(default=8, gt=0)
    prompt_version: str = RESEARCH_PROMPT_VERSION


class ResearchFinding(BaseModel):
    provision: str
    title: str
    url: str
    source_name: str
    published_at: str | None = None
    citation_quote: str | None = None
    citation_section: str | None = None
    claim: str
    why_it_matters: str | None = None
    decision_relevance: str | None = None
    reported_source_class: str | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence_type: str | None = None
    search_query: str | None = None
    provider: str
    model_name: str | None = None
    prompt_version: str = RESEARCH_PROMPT_VERSION
    raw_public_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("provision")
    @classmethod
    def valid_provision(cls, value: str) -> str:
        return normalize_provision(value)

    @field_validator("url")
    @classmethod
    def valid_url(cls, value: str) -> str:
        return canonicalize_url(value)


class ResearchLaneResult(BaseModel):
    vertical_id: str
    provider: str
    findings: list[ResearchFinding]
    notes: list[str] = Field(default_factory=list)
    requests_used: int = 0
    estimated_cost_usd: float = 0.0
    summary: str | None = None


def is_official_domain(
    url: str,
    official_domains: Iterable[str] = OFFICIAL_SOURCE_DOMAINS,
) -> bool:
    try:
        hostname = (urlparse(url).hostname or "").lower()
    except ValueError:
        return False
    return any(
        hostname == domain or hostname.endswith(f".{domain}")
        for domain in (item.lower() for item in official_domains)
    )


def classify_source_class(url: str, reported: str | None) -> str:
    if is_official_domain(url):
        return "official"
    if reported in {"news", "analysis"}:
        return reported
    return "news"


def promotability_for(source_class: str, citation_quote: str | None) -> str:
    if source_class == "official" and citation_quote and citation_quote.strip():
        return "ledger_candidate"
    return "context_only"


def finding_idempotency_key(finding: ResearchFinding) -> str:
    digest = _finding_hash(finding)
    return f"daily-research:{finding.provision}:{digest[:24]}"


def finding_candidate_id(finding: ResearchFinding) -> str:
    digest = _finding_hash(finding)
    return f"cand:{finding.provision}:{digest[:24]}"


def _finding_hash(finding: ResearchFinding) -> str:
    return stable_hash(
        canonicalize_url(finding.url),
        _normalize_text(finding.claim),
        _normalize_text(finding.citation_quote or ""),
    )


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().split())
