from __future__ import annotations

from datetime import date

import pytest

from pci_realtime.agent_research import EvidenceCandidate, EvidenceResearchResult
from pci_realtime.research import openai_web
from pci_realtime.research.base import (
    RequestBudget,
    ResearchBudgetExceeded,
    ResearchProviderError,
)
from pci_realtime.research.chain import FallbackChain, build_provider_chain
from pci_realtime.research.models import LaneBrief, ResearchLaneResult
from pci_realtime.research.openai_web import OpenAIWebSearchProvider


def _brief() -> LaneBrief:
    return LaneBrief(
        vertical_id="clean-energy-finance",
        vertical_name="Clean Energy Finance",
        provisions=("50141", "50144"),
        coverage_note="Tracks two LPO provisions.",
        keywords=("lpo funding", "energy infrastructure reinvestment"),
        since=date(2026, 7, 1),
    )


def test_openai_provider_forwards_lane_and_maps_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}
    fake_client = object()

    def research(**kwargs) -> EvidenceResearchResult:
        captured.update(kwargs)
        return EvidenceResearchResult(
            generated_for="fixture",
            candidates=[
                EvidenceCandidate(
                    provision="50141",
                    source_title="LPO funding notice",
                    source_name="Department of Energy",
                    url="https://www.energy.gov/lpo/funding-notice",
                    citation_quote="The funding remains available for eligible projects.",
                    claim="DOE confirmed availability of program funding.",
                    evidence_type="funding_notice",
                )
            ],
            notes=["quiet second provision"],
        )

    monkeypatch.setattr(openai_web, "research_evidence_with_web_search", research)
    provider = OpenAIWebSearchProvider(
        model="test-model",
        allowed_domains=("energy.gov",),
        max_candidates_per_provision=1,
        client=fake_client,
    )
    budget = RequestBudget(max_requests=2)

    result = provider.run_research(_brief(), budget=budget)

    assert captured == {
        "since": date(2026, 7, 1),
        "provisions": ("50141", "50144"),
        "max_candidates_per_provision": 1,
        "model": "test-model",
        "allowed_domains": ("energy.gov",),
        "client": fake_client,
    }
    assert budget.used == 1
    assert result.requests_used == 1
    assert result.findings[0].title == "LPO funding notice"
    assert result.findings[0].provider == "openai"
    assert result.findings[0].model_name == "test-model"
    assert result.notes == ["quiet second provision"]


class FakeProvider:
    def __init__(
        self,
        name: str,
        *,
        cost: float,
        result: ResearchLaneResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.name = name
        self.cost = cost
        self.result = result
        self.error = error
        self.calls = 0

    def estimated_cost_per_lane_usd(self) -> float:
        return self.cost

    def run_research(self, brief, *, budget) -> ResearchLaneResult:
        self.calls += 1
        if self.error:
            raise self.error
        assert self.result is not None
        return self.result


def _result(provider: str, *, notes: list[str] | None = None) -> ResearchLaneResult:
    return ResearchLaneResult(
        vertical_id="clean-energy-finance",
        provider=provider,
        findings=[],
        notes=notes or [],
    )


def test_fallback_chain_falls_through_only_on_errors_and_sums_costs() -> None:
    failed = FakeProvider(
        "first",
        cost=0.2,
        error=ResearchProviderError("unavailable"),
    )
    succeeded = FakeProvider("second", cost=0.3, result=_result("second"))
    chain = FallbackChain([failed, succeeded])

    result = chain.run_research(_brief(), budget=RequestBudget(max_requests=5))

    assert chain.name == "first>second"
    assert chain.estimated_cost_per_lane_usd() == pytest.approx(0.5)
    assert failed.calls == succeeded.calls == 1
    assert result.provider == "second"
    assert result.notes[0].startswith("first failed:")


def test_fallback_chain_does_not_fall_through_on_empty_findings() -> None:
    quiet = FakeProvider("quiet", cost=0.1, result=_result("quiet"))
    unused = FakeProvider("unused", cost=0.2, result=_result("unused"))

    result = FallbackChain([quiet, unused]).run_research(
        _brief(),
        budget=RequestBudget(max_requests=5),
    )

    assert result.findings == []
    assert quiet.calls == 1
    assert unused.calls == 0


def test_fallback_chain_raises_when_every_provider_fails() -> None:
    chain = FallbackChain(
        [
            FakeProvider("one", cost=0.1, error=ResearchProviderError("one")),
            FakeProvider("two", cost=0.2, error=ResearchProviderError("two")),
        ]
    )

    with pytest.raises(ResearchProviderError, match="All research providers failed"):
        chain.run_research(_brief(), budget=RequestBudget(max_requests=5))


def test_request_budget_raises_before_overrunning_cap() -> None:
    budget = RequestBudget(max_requests=2)
    budget.spend(2)

    with pytest.raises(ResearchBudgetExceeded):
        budget.spend()

    assert budget.used == 2


def test_build_provider_chain_parses_env_and_requires_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PCI_RESEARCH_PROVIDERS", " openai ")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    chain = build_provider_chain()

    assert chain.name == "openai"

    monkeypatch.delenv("OPENAI_API_KEY")
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        build_provider_chain()


def test_build_provider_chain_rejects_unknown_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    with pytest.raises(RuntimeError, match="Valid providers: openai"):
        build_provider_chain("exa")
