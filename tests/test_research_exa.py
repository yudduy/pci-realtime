from __future__ import annotations

import copy
import json
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest

from pci_realtime.research.base import RequestBudget, ResearchProviderError
from pci_realtime.research.exa import ExaProvider
from pci_realtime.research.models import LaneBrief


FIXTURE = json.loads(
    Path("data/fixtures/exa_search_fixture.json").read_text(encoding="utf-8")
)


def _brief() -> LaneBrief:
    return LaneBrief(
        vertical_id="clean-energy-finance",
        vertical_name="Clean Energy Finance",
        provisions=("50141", "50144"),
        coverage_note="Tracks two DOE Loan Programs Office provisions.",
        keywords=("lpo funding", "energy infrastructure reinvestment"),
        since=date(2026, 7, 1),
    )


def _provider(
    *,
    payload: dict[str, Any] | None = None,
    status_code: int = 200,
) -> tuple[ExaProvider, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(status_code, json=payload or FIXTURE)

    return (
        ExaProvider(
            api_key="exa-test-key",
            results_per_query=3,
            transport=httpx.MockTransport(handler),
        ),
        requests,
    )


def test_exa_provider_pins_request_and_maps_keyword_and_fallback_findings() -> None:
    provider, requests = _provider()
    budget = RequestBudget(max_requests=2)

    result = provider.run_research(_brief(), budget=budget)

    assert budget.used == 1
    assert result.requests_used == 1
    assert result.estimated_cost_usd == pytest.approx(0.007)
    assert result.provider == "exa"
    assert result.summary is None
    assert len(requests) == 1
    request = requests[0]
    assert request.method == "POST"
    assert request.url.path == "/search"
    assert request.headers["x-api-key"] == "exa-test-key"
    body = json.loads(request.content)
    assert body["type"] == "auto"
    assert body["numResults"] == 3
    assert body["startPublishedDate"] == "2026-07-01"
    assert body["contents"] == {
        "highlights": True,
        "text": {"maxCharacters": 1000},
    }
    assert "Clean Energy Finance" in body["query"]
    assert "lpo funding" in body["query"]
    assert "since 2026-07-01" in body["query"]

    assigned, fallback = result.findings[:2]
    assert assigned.provision == "50144"
    assert assigned.source_name == "energy.gov"
    assert assigned.published_at == "2026-07-02T10:00:00Z"
    assert assigned.citation_quote == (
        "The Energy Infrastructure Reinvestment program will use revised "
        "application milestones."
    )
    assert fallback.provision == "50141"
    assert fallback.source_name == "example.com"
    assert all(finding.provider == "exa" for finding in result.findings)
    assert all(finding.model_name == "exa:auto" for finding in result.findings)
    assert all(finding.search_query == body["query"] for finding in result.findings)


def test_exa_provider_drops_invalid_finding_with_note() -> None:
    payload = copy.deepcopy(FIXTURE)
    payload["results"].insert(
        0,
        {
            "title": "Private result",
            "url": "http://127.0.0.1/private",
            "highlights": ["This should not become a public finding."],
        },
    )
    provider, _ = _provider(payload=payload)

    result = provider.run_research(_brief(), budget=RequestBudget(max_requests=1))

    assert len(result.findings) == 3
    assert result.notes[0].startswith("Dropped Exa result 1:")
    assert "publicly reachable" in result.notes[0]


def test_exa_provider_maps_http_error_to_provider_error() -> None:
    provider, _ = _provider(status_code=503)

    with pytest.raises(ResearchProviderError, match="503"):
        provider.run_research(_brief(), budget=RequestBudget(max_requests=1))


def test_exa_provider_maps_timeout_to_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("exa fixture timeout", request=request)

    provider = ExaProvider(
        api_key="exa-test-key",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ResearchProviderError, match="exa fixture timeout"):
        provider.run_research(_brief(), budget=RequestBudget(max_requests=1))
