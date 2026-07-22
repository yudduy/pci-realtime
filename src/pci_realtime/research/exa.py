from __future__ import annotations

import ipaddress
import os
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlparse

import httpx

from pci_realtime.config import PROVISION_KEYWORDS, RESEARCH_UNIT_COSTS_USD
from pci_realtime.research.base import RequestBudget, ResearchProviderError
from pci_realtime.research.models import (
    LaneBrief,
    ResearchFinding,
    ResearchLaneResult,
)


_COMMON_SECOND_LEVEL_SUFFIXES = {
    "ac",
    "co",
    "com",
    "edu",
    "gov",
    "net",
    "org",
}


class ExaProvider:
    name = "exa"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = "https://api.exa.ai",
        transport: httpx.BaseTransport | None = None,
        results_per_query: int = 5,
    ) -> None:
        self.api_key = api_key or os.environ.get("EXA_API_KEY")
        self.results_per_query = results_per_query
        self.client = httpx.Client(
            base_url=base_url,
            headers={"x-api-key": self.api_key or ""},
            transport=transport,
        )

    def estimated_cost_per_lane_usd(self) -> float:
        return RESEARCH_UNIT_COSTS_USD[self.name]

    def run_research(
        self,
        brief: LaneBrief,
        *,
        budget: RequestBudget,
    ) -> ResearchLaneResult:
        budget.spend(1)
        if not self.api_key:
            raise ResearchProviderError("EXA_API_KEY is not configured.")

        query = _build_exa_query(brief)
        try:
            response = self.client.post(
                "/search",
                json={
                    "query": query,
                    "type": "auto",
                    "numResults": self.results_per_query,
                    "startPublishedDate": brief.since.isoformat(),
                    "contents": {
                        "highlights": True,
                        "text": {"maxCharacters": 1000},
                    },
                },
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException as exc:
            raise ResearchProviderError(f"Exa search timed out: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise ResearchProviderError(
                f"Exa search failed with HTTP {exc.response.status_code}: "
                f"{_response_error(exc.response)}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ResearchProviderError(f"Exa search failed: {exc}") from exc
        except ValueError as exc:
            raise ResearchProviderError(
                f"Exa search response was not valid JSON: {exc}"
            ) from exc

        if not isinstance(payload, Mapping):
            raise ResearchProviderError("Exa search response must be a JSON object.")
        raw_results = payload.get("results")
        if not isinstance(raw_results, Sequence) or isinstance(
            raw_results, (str, bytes)
        ):
            raise ResearchProviderError(
                "Exa search response did not include a results array."
            )

        notes: list[str] = []
        findings: list[ResearchFinding] = []
        for index, raw_result in enumerate(
            raw_results[: brief.max_findings],
            start=1,
        ):
            try:
                finding = _finding_from_exa_result(raw_result, brief, query=query)
            except Exception as exc:
                notes.append(f"Dropped Exa result {index}: {type(exc).__name__}: {exc}")
                continue
            findings.append(finding)

        return ResearchLaneResult(
            vertical_id=brief.vertical_id,
            provider=self.name,
            findings=findings,
            notes=notes,
            requests_used=1,
            estimated_cost_usd=self.estimated_cost_per_lane_usd(),
            summary=None,
        )


def _build_exa_query(brief: LaneBrief) -> str:
    keywords = ", ".join(dict.fromkeys(brief.keywords))
    return (
        f"{brief.vertical_name} policy developments published since "
        f"{brief.since.isoformat()}; top policy keywords: {keywords}"
    )


def _finding_from_exa_result(
    raw_result: Any,
    brief: LaneBrief,
    *,
    query: str,
) -> ResearchFinding:
    if not isinstance(raw_result, Mapping):
        raise ValueError("result must be a JSON object")
    title = str(raw_result.get("title") or "").strip()
    url = str(raw_result.get("url") or "").strip()
    if not title:
        raise ValueError("result title is required")
    highlights = _highlights(raw_result.get("highlights"))
    provision = _assign_provision(
        brief,
        text=" ".join((title, *highlights)),
    )
    published_at = raw_result.get("publishedDate")
    return ResearchFinding(
        provision=provision,
        title=title,
        url=url,
        source_name=_registrable_hostname(url),
        published_at=str(published_at) if published_at else None,
        citation_quote=highlights[0] if highlights else None,
        claim=f"{title} — reported development relevant to {provision}",
        reported_source_class=None,
        provider="exa",
        model_name="exa:auto",
        search_query=query,
        prompt_version=brief.prompt_version,
    )


def _assign_provision(brief: LaneBrief, *, text: str) -> str:
    normalized = text.casefold()
    matches: list[tuple[bool, int, int, str]] = []
    for lane_index, provision in enumerate(brief.provisions):
        for keyword in PROVISION_KEYWORDS[provision]:
            normalized_keyword = keyword.casefold()
            if normalized_keyword in normalized:
                matches.append(
                    (
                        provision.casefold() in normalized_keyword,
                        len(normalized_keyword),
                        -lane_index,
                        provision,
                    )
                )
    if matches:
        return max(matches)[3]
    return brief.provisions[0]


def _highlights(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _registrable_hostname(url: str) -> str:
    hostname = (urlparse(url).hostname or "").lower()
    if not hostname:
        raise ValueError("result URL must include a hostname")
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        return hostname

    labels = hostname.rstrip(".").split(".")
    if len(labels) <= 2:
        return hostname
    if (
        len(labels) >= 3
        and len(labels[-1]) == 2
        and labels[-2] in _COMMON_SECOND_LEVEL_SUFFIXES
    ):
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def _response_error(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text
