from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError

from pci_realtime.agent_intake import canonicalize_url
from pci_realtime.config import (
    RESEARCH_PARALLEL_PROCESSOR,
    RESEARCH_UNIT_COSTS_USD,
)
from pci_realtime.research.base import RequestBudget, ResearchProviderError
from pci_realtime.research.models import (
    LaneBrief,
    ResearchFinding,
    ResearchLaneResult,
)
from pci_realtime.research.prompts import build_lane_research_prompt


class ParallelFinding(BaseModel):
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
    confidence: float = 0.5


class ParallelLaneOutput(BaseModel):
    findings: list[ParallelFinding]
    lane_summary: str | None = None
    notes: list[str] = Field(default_factory=list)


class ParallelProvider:
    name = "parallel"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        processor: str = RESEARCH_PARALLEL_PROCESSOR,
        base_url: str = "https://api.parallel.ai",
        transport: httpx.BaseTransport | None = None,
        api_timeout_seconds: int = 540,
    ) -> None:
        self.api_key = api_key or os.environ.get("PARALLEL_API_KEY")
        self.processor = processor
        self.api_timeout_seconds = api_timeout_seconds
        self.client = httpx.Client(
            base_url=base_url,
            headers={"x-api-key": self.api_key or ""},
            transport=transport,
            timeout=api_timeout_seconds + 60,
        )

    def estimated_cost_per_lane_usd(self) -> float:
        cost_key = f"parallel:{self.processor}"
        try:
            return RESEARCH_UNIT_COSTS_USD[cost_key]
        except KeyError as exc:
            valid = ", ".join(
                sorted(
                    key
                    for key in RESEARCH_UNIT_COSTS_USD
                    if key.startswith("parallel:")
                )
            )
            raise ValueError(
                f"Unknown Parallel processor {self.processor!r}. "
                f"Valid cost keys: {valid}."
            ) from exc

    def run_research(
        self,
        brief: LaneBrief,
        *,
        budget: RequestBudget,
    ) -> ResearchLaneResult:
        budget.spend(1)
        if not self.api_key:
            raise ResearchProviderError("PARALLEL_API_KEY is not configured.")

        create_payload = {
            "processor": self.processor,
            "input": build_lane_research_prompt(brief),
            "task_spec": {
                "output_schema": {
                    "type": "json",
                    "json_schema": ParallelLaneOutput.model_json_schema(),
                }
            },
            "metadata": {
                "vertical": brief.vertical_id,
                "prompt_version": brief.prompt_version,
            },
        }
        create_result = self._request_json(
            "create",
            lambda: self.client.post(
                "/v1/tasks/runs",
                headers={"content-type": "application/json"},
                json=create_payload,
            ),
        )
        run_id = create_result.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            raise ResearchProviderError(
                "Parallel create response did not include a valid run_id."
            )

        result_payload = self._request_json(
            "result",
            lambda: self.client.get(
                f"/v1/tasks/runs/{run_id}/result",
                params={"timeout": self.api_timeout_seconds},
            ),
        )
        run = result_payload.get("run")
        status = run.get("status") if isinstance(run, Mapping) else None
        if status != "completed":
            error_payload = _parallel_error_payload(result_payload, run)
            suffix = (
                f" Error payload: {json.dumps(error_payload, sort_keys=True)}"
                if error_payload is not None
                else ""
            )
            raise ResearchProviderError(
                f"Parallel task {run_id} returned status {status!r}.{suffix}"
            )

        output = result_payload.get("output")
        if not isinstance(output, Mapping) or output.get("type") != "json":
            raise ResearchProviderError(
                f"Parallel task {run_id} returned a non-JSON output payload."
            )
        try:
            lane_output = ParallelLaneOutput.model_validate(output.get("content"))
        except ValidationError as exc:
            raise ResearchProviderError(
                f"Parallel task {run_id} returned invalid lane output: {exc}"
            ) from exc

        basis = output.get("basis")
        notes: list[str] = []
        findings: list[ResearchFinding] = []
        for index, parallel_finding in enumerate(
            lane_output.findings[: brief.max_findings],
            start=1,
        ):
            try:
                finding = ResearchFinding(
                    **parallel_finding.model_dump(),
                    provider=self.name,
                    model_name=f"parallel:{self.processor}",
                    prompt_version=brief.prompt_version,
                    search_query=None,
                    raw_public_metadata={
                        "citations": _url_matched_citations(
                            parallel_finding.url,
                            basis,
                        )
                    },
                )
            except Exception as exc:
                notes.append(
                    f"Dropped Parallel finding {index}: {type(exc).__name__}: {exc}"
                )
                continue
            findings.append(finding)

        return ResearchLaneResult(
            vertical_id=brief.vertical_id,
            provider=self.name,
            findings=findings,
            notes=[*notes, *lane_output.notes],
            requests_used=1,
            estimated_cost_usd=self.estimated_cost_per_lane_usd(),
            summary=lane_output.lane_summary,
        )

    def _request_json(
        self,
        operation: str,
        request: Any,
    ) -> dict[str, Any]:
        try:
            response = request()
            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException as exc:
            raise ResearchProviderError(
                f"Parallel {operation} request timed out: {exc}"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise ResearchProviderError(
                f"Parallel {operation} request failed with HTTP "
                f"{exc.response.status_code}: {_response_error(exc.response)}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ResearchProviderError(
                f"Parallel {operation} request failed: {exc}"
            ) from exc
        except ValueError as exc:
            raise ResearchProviderError(
                f"Parallel {operation} response was not valid JSON: {exc}"
            ) from exc
        if not isinstance(payload, dict):
            raise ResearchProviderError(
                f"Parallel {operation} response must be a JSON object."
            )
        return payload


def _url_matched_citations(
    finding_url: str,
    basis: Any,
) -> list[dict[str, Any]]:
    try:
        canonical_finding_url = canonicalize_url(finding_url)
    except Exception:
        return []
    if not isinstance(basis, Sequence) or isinstance(basis, (str, bytes)):
        return []

    matches: list[dict[str, Any]] = []
    for basis_item in basis:
        if not isinstance(basis_item, Mapping):
            continue
        citations = basis_item.get("citations")
        if not isinstance(citations, Sequence) or isinstance(citations, (str, bytes)):
            continue
        for citation in citations:
            if not isinstance(citation, Mapping):
                continue
            citation_url = citation.get("url")
            try:
                canonical_citation_url = canonicalize_url(str(citation_url or ""))
            except Exception:
                continue
            if canonical_citation_url != canonical_finding_url:
                continue
            matches.append(
                {
                    "url": citation_url,
                    "title": citation.get("title"),
                    "excerpts": citation.get("excerpts"),
                }
            )
    return matches


def _parallel_error_payload(
    payload: Mapping[str, Any],
    run: Mapping[str, Any] | Any,
) -> Any:
    if isinstance(run, Mapping) and run.get("error") is not None:
        return run["error"]
    return payload.get("error")


def _response_error(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text
