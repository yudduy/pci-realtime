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
    assert result.summary is None


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


def test_fallback_chain_runs_openai_after_parallel_error_and_sums_costs() -> None:
    failed = FakeProvider(
        "parallel",
        cost=0.2,
        error=ResearchProviderError("unavailable"),
    )
    succeeded = FakeProvider("openai", cost=0.3, result=_result("openai"))
    chain = FallbackChain([failed, succeeded])

    result = chain.run_research(_brief(), budget=RequestBudget(max_requests=5))

    assert chain.name == "parallel>openai"
    assert chain.estimated_cost_per_lane_usd() == pytest.approx(0.5)
    assert failed.calls == succeeded.calls == 1
    assert result.provider == "openai"
    assert result.notes[0].startswith("parallel failed:")


def test_fallback_chain_does_not_fall_through_on_empty_parallel_findings() -> None:
    quiet = FakeProvider("parallel", cost=0.1, result=_result("parallel"))
    unused = FakeProvider("openai", cost=0.2, result=_result("openai"))

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


def test_build_provider_chain_skips_parallel_when_key_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.delenv("PARALLEL_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    chain = build_provider_chain("parallel,openai")

    assert chain.name == "openai"
    assert "PARALLEL_API_KEY is not configured" in caplog.text


def test_build_provider_chain_raises_when_parallel_and_openai_keys_are_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PARALLEL_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError) as exc_info:
        build_provider_chain("parallel,openai")

    assert "PARALLEL_API_KEY" in str(exc_info.value)
    assert "OPENAI_API_KEY" in str(exc_info.value)


def test_build_provider_chain_builds_parallel_then_openai_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PARALLEL_API_KEY", "parallel-test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")

    chain = build_provider_chain("parallel,openai")

    assert chain.name == "parallel>openai"


def test_build_provider_chain_rejects_unknown_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    with pytest.raises(RuntimeError, match="Valid providers: exa, openai, parallel"):
        build_provider_chain("unknown")
