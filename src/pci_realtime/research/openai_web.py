from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pci_realtime.agent_research import (
    DEFAULT_AGENT_RESEARCH_MODEL,
    OFFICIAL_SOURCE_DOMAINS,
    EvidenceResearchResult,
    research_evidence_with_web_search,
)
from pci_realtime.config import RESEARCH_UNIT_COSTS_USD
from pci_realtime.research.base import RequestBudget, ResearchProviderError
from pci_realtime.research.models import (
    LaneBrief,
    ResearchFinding,
    ResearchLaneResult,
)


class OpenAIWebSearchProvider:
    name = "openai"

    def __init__(
        self,
        *,
        model: str = DEFAULT_AGENT_RESEARCH_MODEL,
        allowed_domains: Iterable[str] = OFFICIAL_SOURCE_DOMAINS,
        max_candidates_per_provision: int = 2,
        client: Any | None = None,
    ) -> None:
        self.model = model
        self.allowed_domains = tuple(allowed_domains)
        self.max_candidates_per_provision = max_candidates_per_provision
        self.client = client

    def estimated_cost_per_lane_usd(self) -> float:
        return RESEARCH_UNIT_COSTS_USD[self.name]

    def run_research(
        self,
        brief: LaneBrief,
        *,
        budget: RequestBudget,
    ) -> ResearchLaneResult:
        budget.spend(1)
        try:
            result = research_evidence_with_web_search(
                since=brief.since,
                provisions=brief.provisions,
                max_candidates_per_provision=self.max_candidates_per_provision,
                model=self.model,
                allowed_domains=self.allowed_domains,
                client=self.client,
            )
            findings = findings_from_evidence_candidates(
                result,
                brief,
                model=self.model,
            )
        except Exception as exc:
            raise ResearchProviderError(f"OpenAI web search failed: {exc}") from exc
        return ResearchLaneResult(
            vertical_id=brief.vertical_id,
            provider=self.name,
            findings=findings,
            notes=list(result.notes),
            requests_used=1,
            estimated_cost_usd=self.estimated_cost_per_lane_usd(),
        )


def findings_from_evidence_candidates(
    result: EvidenceResearchResult,
    brief: LaneBrief,
    *,
    model: str,
) -> list[ResearchFinding]:
    del brief  # The wrapped A1 sweep has no custom lane-prompt parameter.
    return [
        ResearchFinding(
            provision=candidate.provision,
            title=candidate.source_title,
            url=candidate.url,
            source_name=candidate.source_name,
            published_at=candidate.published_at,
            citation_quote=candidate.citation_quote,
            citation_section=candidate.citation_section,
            claim=candidate.claim,
            evidence_type=candidate.evidence_type,
            search_query=None,
            provider="openai",
            model_name=model,
        )
        for candidate in result.candidates
    ]
