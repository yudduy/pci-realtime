from __future__ import annotations

import copy
import json
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest

from pci_realtime.research.base import RequestBudget, ResearchProviderError
from pci_realtime.research.models import LaneBrief
from pci_realtime.research.parallel import ParallelProvider


FIXTURE = json.loads(
    Path("data/fixtures/parallel_task_run_fixture.json").read_text(encoding="utf-8")
)


def _brief(*, max_findings: int = 8) -> LaneBrief:
    return LaneBrief(
        vertical_id="clean-energy-finance",
        vertical_name="Clean Energy Finance",
        provisions=("50141", "50144"),
        coverage_note="Tracks two DOE Loan Programs Office provisions.",
        keywords=("lpo funding", "energy infrastructure reinvestment"),
        since=date(2026, 7, 1),
        max_findings=max_findings,
    )


def _provider(
    *,
    result_payload: dict[str, Any] | None = None,
) -> tuple[ParallelProvider, list[httpx.Request]]:
    requests: list[httpx.Request] = []
    payload = result_payload or FIXTURE["result_response"]

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST":
            return httpx.Response(202, json=FIXTURE["create_response"])
        return httpx.Response(200, json=payload)

    return (
        ParallelProvider(
            api_key="parallel-test-key",
            processor="base",
            transport=httpx.MockTransport(handler),
        ),
        requests,
    )


def test_parallel_provider_pins_task_contract_citations_summary_and_cap() -> None:
    provider, requests = _provider()
    budget = RequestBudget(max_requests=3)

    result = provider.run_research(_brief(max_findings=2), budget=budget)

    assert budget.used == 1
    assert result.requests_used == 1
    assert result.estimated_cost_usd == pytest.approx(0.01)
    assert result.provider == "parallel"
    assert len(result.findings) == 2
    assert result.summary == (
        "DOE clarified Loan Programs Office application guidance while developers "
        "reported a growing project pipeline. The day's developments point to "
        "continued demand for both 50141 funding and 50144 reinvestment authority."
    )

    assert len(requests) == 2
    create_request, result_request = requests
    assert create_request.method == "POST"
    assert create_request.url.path == "/v1/tasks/runs"
    assert create_request.headers["x-api-key"] == "parallel-test-key"
    assert create_request.headers["content-type"] == "application/json"
    create_body = json.loads(create_request.content)
    assert create_body["processor"] == "base"
    assert create_body["task_spec"]["output_schema"]["type"] == "json"
    output_schema = create_body["task_spec"]["output_schema"]["json_schema"]
    assert {"findings", "lane_summary"} <= set(output_schema["properties"])
    assert create_body["metadata"] == {
        "vertical": "clean-energy-finance",
        "prompt_version": "daily-research-v1",
    }
    assert "2-3 sentence lane_summary" in create_body["input"]

    assert result_request.method == "GET"
    assert result_request.url.path == "/v1/tasks/runs/trun_fixture_001/result"
    assert dict(result_request.url.params) == {"timeout": "540"}
    assert result_request.extensions["timeout"]["read"] == 600.0

    assert result.findings[0].raw_public_metadata == {
        "citations": [
            {
                "url": (
                    "https://www.energy.gov/lpo/articles/funding-guidance"
                    "?utm_source=parallel#program-update"
                ),
                "title": "DOE updates Loan Programs Office funding guidance",
                "excerpts": [
                    "The office will continue accepting applications under the "
                    "updated guidance."
                ],
            }
        ]
    }
    assert "reasoning" not in json.dumps(result.findings[0].raw_public_metadata)


def test_parallel_provider_drops_invalid_finding_and_appends_note() -> None:
    payload = copy.deepcopy(FIXTURE["result_response"])
    payload["output"]["content"]["findings"].insert(
        0,
        {
            "provision": "50141",
            "title": "Invalid private source",
            "url": "http://localhost/private",
            "source_name": "Invalid",
            "claim": "This result must be dropped during public URL validation.",
        },
    )
    provider, _ = _provider(result_payload=payload)

    result = provider.run_research(
        _brief(),
        budget=RequestBudget(max_requests=1),
    )

    assert len(result.findings) == 3
    assert result.notes[0].startswith("Dropped Parallel finding 1:")
    assert "publicly reachable" in result.notes[0]
    assert result.notes[1:] == [
        "No additional official 50144 notice was published in the search window."
    ]


def test_parallel_provider_rejects_failed_run_with_error_payload() -> None:
    payload = copy.deepcopy(FIXTURE["result_response"])
    payload["run"]["status"] = "failed"
    payload["run"]["error"] = {"message": "processor crashed"}
    provider, _ = _provider(result_payload=payload)

    with pytest.raises(ResearchProviderError, match="failed.*processor crashed"):
        provider.run_research(_brief(), budget=RequestBudget(max_requests=1))


def test_parallel_provider_maps_httpx_timeout_to_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(202, json=FIXTURE["create_response"])
        raise httpx.TimeoutException("fixture timeout", request=request)

    provider = ParallelProvider(
        api_key="parallel-test-key",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ResearchProviderError, match="fixture timeout"):
        provider.run_research(_brief(), budget=RequestBudget(max_requests=1))


def test_parallel_provider_rejects_unknown_processor_cost() -> None:
    provider = ParallelProvider(
        api_key="parallel-test-key",
        processor="unknown",
        transport=httpx.MockTransport(lambda request: httpx.Response(500)),
    )

    with pytest.raises(
        ValueError,
        match=r"parallel:base, parallel:core, parallel:lite",
    ):
        provider.estimated_cost_per_lane_usd()
