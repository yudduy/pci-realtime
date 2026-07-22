from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from conftest import RecordingSelectingSupabaseClient
from pci_realtime.pipeline import daily_research
from pci_realtime.pipeline.daily_research import run_daily_research
from pci_realtime.research.base import ResearchBudgetExceeded
from pci_realtime.research.models import ResearchFinding, ResearchLaneResult
from pci_realtime.service_errors import BadRequest, ScoringUnavailable


FIXTURE_PATH = Path("data/fixtures/research_findings_fixture.json")
SINCE = date(2026, 7, 1)


def _fixture_findings() -> dict[str, list[ResearchFinding]]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return {
        vertical_id: [ResearchFinding.model_validate(item) for item in items]
        for vertical_id, items in payload.items()
    }


def _finding(
    suffix: str,
    *,
    provision: str = "45X",
    official: bool = True,
    quote: str | None = "The agency finalized implementation requirements.",
    confidence: float = 0.8,
    raw_public_metadata: dict[str, Any] | None = None,
) -> ResearchFinding:
    host = "www.federalregister.gov" if official else "example.com"
    return ResearchFinding(
        provision=provision,
        title=f"Finding {suffix}",
        url=f"https://{host}/documents/{suffix}",
        source_name="Federal Register" if official else "Example News",
        citation_quote=quote,
        claim=f"Policy finding {suffix} changes implementation details.",
        reported_source_class="official" if official else "news",
        confidence=confidence,
        evidence_type="rulemaking" if official else "news_report",
        provider="fixture",
        raw_public_metadata=raw_public_metadata or {},
    )


class FakeChain:
    name = "fixture"

    def __init__(
        self,
        findings_by_vertical: dict[str, list[ResearchFinding]],
        *,
        errors: dict[str, Exception] | None = None,
        summaries: dict[str, str | None] | None = None,
        cost: float = 0.05,
    ) -> None:
        self.findings_by_vertical = findings_by_vertical
        self.errors = errors or {}
        self.summaries = summaries or {}
        self.cost = cost
        self.calls: list[str] = []

    def estimated_cost_per_lane_usd(self) -> float:
        return self.cost

    def run_research(self, brief, *, budget) -> ResearchLaneResult:
        self.calls.append(brief.vertical_id)
        budget.spend(1)
        if brief.vertical_id in self.errors:
            raise self.errors[brief.vertical_id]
        return ResearchLaneResult(
            vertical_id=brief.vertical_id,
            provider=self.name,
            findings=self.findings_by_vertical.get(brief.vertical_id, []),
            summary=self.summaries.get(brief.vertical_id),
        )


def _enable_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        daily_research.service,
        "status",
        lambda: {"write_configured": True},
    )


def _candidate_rows(
    client: RecordingSelectingSupabaseClient,
) -> list[dict[str, Any]]:
    return next(
        rows
        for _, table, rows, _ in client.calls
        if table == "policy_source_candidates"
    )


def test_write_path_orders_writes_and_only_submits_quoted_official_findings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_writes(monkeypatch)
    chain = FakeChain(_fixture_findings())
    client = RecordingSelectingSupabaseClient()
    submissions = []

    def submit(**kwargs) -> dict[str, Any]:
        submissions.append(kwargs)
        return {"status": "promoted", "submission_id": "submission:new"}

    payload = run_daily_research(
        since=SINCE,
        verticals=("advanced-manufacturing", "clean-hydrogen"),
        write=True,
        client=client,  # type: ignore[arg-type]
        chain=chain,  # type: ignore[arg-type]
        submit=submit,
    )

    assert [
        (method, table, conflict) for method, table, _, conflict in client.calls
    ] == [
        ("insert", "pipeline_runs", None),
        (
            "upsert",
            "policy_source_candidates",
            "provision,canonical_url,idempotency_key",
        ),
        ("upsert", "source_health", "source"),
    ]
    assert len(submissions) == 1
    assert submissions[0]["provision"] == "45X"
    assert submissions[0]["agent_name"] == "pcindex-daily-research"
    rows = _candidate_rows(client)
    assert len(rows) == 3
    assert (
        next(row for row in rows if "irs.gov" in row["canonical_url"])["review_state"]
        == "queued"
    )
    news = next(row for row in rows if "example.com" in row["canonical_url"])
    assert news["review_state"] == "approved"
    assert news["promotability"] == "context_only"
    assert payload["counts"]["promoted"] == 1


def test_promotions_are_capped_per_lane_and_sorted_by_confidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_writes(monkeypatch)
    monkeypatch.setenv("PCI_RESEARCH_MAX_PROMOTIONS_PER_LANE", "2")
    findings = [
        _finding("low", confidence=0.1),
        _finding("highest", confidence=0.95),
        _finding("middle", confidence=0.7),
        _finding("high", confidence=0.85),
    ]
    client = RecordingSelectingSupabaseClient()
    submitted_urls = []

    def submit(**kwargs) -> dict[str, Any]:
        submitted_urls.append(kwargs["source"]["url"])
        return {
            "status": "promoted",
            "submission_id": f"submission:{len(submitted_urls)}",
        }

    run_daily_research(
        since=SINCE,
        verticals=("advanced-manufacturing",),
        write=True,
        client=client,  # type: ignore[arg-type]
        chain=FakeChain({"advanced-manufacturing": findings}),  # type: ignore[arg-type]
        submit=submit,
    )

    assert [url.rsplit("/", 1)[-1] for url in submitted_urls] == [
        "highest",
        "high",
    ]


def test_promotion_outcomes_are_isolated_and_mapped_to_review_states(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_writes(monkeypatch)
    findings = [
        _finding("success", confidence=0.9),
        _finding("bad-request", confidence=0.8),
        _finding("transient", confidence=0.7),
    ]
    client = RecordingSelectingSupabaseClient()
    submitted = []

    def submit(**kwargs) -> dict[str, Any]:
        suffix = kwargs["source"]["url"].rsplit("/", 1)[-1]
        submitted.append(suffix)
        if suffix == "bad-request":
            raise BadRequest("quote does not support the claim")
        if suffix == "transient":
            raise ScoringUnavailable("scorer unavailable")
        return {"status": "promoted", "submission_id": "submission:success"}

    run_daily_research(
        since=SINCE,
        verticals=("advanced-manufacturing",),
        write=True,
        client=client,  # type: ignore[arg-type]
        chain=FakeChain({"advanced-manufacturing": findings}),  # type: ignore[arg-type]
        submit=submit,
    )

    assert submitted == ["success", "bad-request", "transient"]
    rows = {
        row["canonical_url"].rsplit("/", 1)[-1]: row for row in _candidate_rows(client)
    }
    assert rows["success"]["review_state"] == "approved"
    assert rows["success"]["promoted_submission_id"] == "submission:success"
    assert rows["bad-request"]["review_state"] == "needs_primary_source"
    assert rows["bad-request"]["promotion_result"]["status"] == "error"
    assert rows["transient"]["review_state"] == "queued"
    assert rows["transient"]["promotion_result"]["error"]["code"] == (
        "ScoringUnavailable"
    )


def test_cross_day_duplicates_and_already_promoted_sources_skip_submission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_writes(monkeypatch)
    duplicate = _finding("cross-day")
    promoted = _finding("already-promoted")
    client = RecordingSelectingSupabaseClient(
        {
            "policy_source_candidates": [
                {
                    "candidate_id": "cand:existing",
                    "provision": duplicate.provision,
                    "canonical_url": duplicate.url,
                }
            ],
            "evidence_submissions": [
                {
                    "submission_id": "submission:existing",
                    "provision": promoted.provision,
                    "canonical_url": promoted.url,
                }
            ],
        }
    )
    submissions = []

    run_daily_research(
        since=SINCE,
        verticals=("advanced-manufacturing",),
        write=True,
        client=client,  # type: ignore[arg-type]
        chain=FakeChain({"advanced-manufacturing": [duplicate, promoted]}),  # type: ignore[arg-type]
        submit=lambda **kwargs: submissions.append(kwargs),
    )

    assert submissions == []
    assert [call[:2] for call in client.select_calls] == [
        (
            "policy_source_candidates",
            "candidate_id,provision,canonical_url",
        ),
        ("evidence_submissions", "submission_id,provision,canonical_url"),
    ]
    rows = {
        row["canonical_url"].rsplit("/", 1)[-1]: row for row in _candidate_rows(client)
    }
    assert rows["cross-day"]["review_state"] == "duplicate"
    assert rows["cross-day"]["duplicate_of"] == "cand:existing"
    assert rows["already-promoted"]["review_state"] == "approved"
    assert rows["already-promoted"]["promotion_result"]["status"] == "already_promoted"
    assert rows["already-promoted"]["promoted_submission_id"] == "submission:existing"


def test_cost_guard_runs_before_provider_and_confirm_cost_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PCI_RESEARCH_RUN_COST_CEILING_USD", "0.0001")
    chain = FakeChain({"advanced-manufacturing": []})

    with pytest.raises(RuntimeError, match="Pass --confirm-cost"):
        run_daily_research(
            since=SINCE,
            verticals=("advanced-manufacturing",),
            chain=chain,  # type: ignore[arg-type]
        )

    assert chain.calls == []

    payload = run_daily_research(
        since=SINCE,
        verticals=("advanced-manufacturing",),
        confirm_cost=True,
        chain=chain,  # type: ignore[arg-type]
    )
    assert chain.calls == ["advanced-manufacturing"]
    assert payload["counts"]["findings"] == 0


def test_shared_request_budget_exhaustion_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PCI_RESEARCH_MAX_REQUESTS_PER_RUN", "1")

    class OverspendingChain:
        name = "overspending"

        def estimated_cost_per_lane_usd(self) -> float:
            return 0.0

        def run_research(self, brief, *, budget):
            budget.spend(2)

    with pytest.raises(ResearchBudgetExceeded):
        run_daily_research(
            since=SINCE,
            verticals=("advanced-manufacturing",),
            chain=OverspendingChain(),  # type: ignore[arg-type]
        )


def test_dry_run_invokes_research_without_client_calls_and_writes_payload(
    tmp_path: Path,
) -> None:
    lane_summary = "Manufacturing guidance changed; hydrogen coverage was quiet."
    chain = FakeChain(
        _fixture_findings(),
        summaries={"advanced-manufacturing": lane_summary},
    )
    client = RecordingSelectingSupabaseClient()
    output_path = tmp_path / "daily-research.json"

    result = run_daily_research(
        since=SINCE,
        verticals=("advanced-manufacturing", "clean-hydrogen"),
        write=False,
        output_path=output_path,
        client=client,  # type: ignore[arg-type]
        chain=chain,  # type: ignore[arg-type]
    )

    output = json.loads(output_path.read_text(encoding="utf-8"))
    assert client.calls == []
    assert client.select_calls == []
    assert chain.calls == ["advanced-manufacturing", "clean-hydrogen"]
    assert set(result) == {
        "run_id",
        "counts",
        "lanes",
        "estimated_cost_usd",
        "requests_used",
    }
    assert set(output) == {"counts", "rows", "lanes"}
    assert set(output["rows"]) == {
        "pipeline_runs",
        "policy_source_candidates",
        "source_health",
    }
    assert result["lanes"] == {
        "advanced-manufacturing": {
            "findings": 3,
            "new_candidates": 2,
            "duplicates": 1,
            "promoted": 0,
            "errors": 0,
            "summary": lane_summary,
        },
        "clean-hydrogen": {
            "findings": 1,
            "new_candidates": 1,
            "duplicates": 0,
            "promoted": 0,
            "errors": 0,
            "summary": None,
        },
    }
    health_rows = {row["source"]: row for row in output["rows"]["source_health"]}
    assert health_rows["research:advanced-manufacturing"]["details"] == {
        "vertical": "advanced-manufacturing",
        "provider": "fixture",
        "new_candidates": 2,
        "promoted": 0,
        "duplicates": 1,
        "summary": lane_summary,
    }
    assert health_rows["research:clean-hydrogen"]["details"] == {
        "vertical": "clean-hydrogen",
        "provider": "fixture",
        "new_candidates": 1,
        "promoted": 0,
        "duplicates": 0,
        "summary": None,
    }


def test_one_failed_lane_records_failed_health_and_other_lanes_continue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_writes(monkeypatch)
    chain = FakeChain(
        {"clean-hydrogen": []},
        errors={"advanced-manufacturing": RuntimeError("provider down")},
    )
    client = RecordingSelectingSupabaseClient()

    result = run_daily_research(
        since=SINCE,
        verticals=("advanced-manufacturing", "clean-hydrogen"),
        write=True,
        client=client,  # type: ignore[arg-type]
        chain=chain,  # type: ignore[arg-type]
        submit=lambda **kwargs: {},
    )

    assert result["counts"]["successful_lanes"] == 1
    health_rows = next(
        rows for _, table, rows, _ in client.calls if table == "source_health"
    )
    failed = next(
        row for row in health_rows if row["source"] == "research:advanced-manufacturing"
    )
    succeeded = next(
        row for row in health_rows if row["source"] == "research:clean-hydrogen"
    )
    assert failed["status"] == "failed"
    assert failed["last_error_class"] == "RuntimeError"
    assert failed["source_name"] == "Research — Advanced Manufacturing"
    assert result["lanes"]["advanced-manufacturing"] == {
        "findings": 0,
        "new_candidates": 0,
        "duplicates": 0,
        "promoted": 0,
        "errors": 1,
        "summary": None,
    }
    assert failed["details"] == {
        "vertical": "advanced-manufacturing",
        "provider": "fixture",
        "new_candidates": 0,
        "promoted": 0,
        "duplicates": 0,
        "summary": None,
    }
    assert succeeded["details"]["summary"] is None


def test_all_failed_lanes_abort_the_run() -> None:
    chain = FakeChain(
        {},
        errors={
            "advanced-manufacturing": RuntimeError("first down"),
            "clean-hydrogen": RuntimeError("second down"),
        },
    )

    with pytest.raises(RuntimeError, match="every requested vertical"):
        run_daily_research(
            since=SINCE,
            verticals=("advanced-manufacturing", "clean-hydrogen"),
            chain=chain,  # type: ignore[arg-type]
        )


def test_forbidden_lane_error_is_not_written_to_public_health(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_writes(monkeypatch)
    client = RecordingSelectingSupabaseClient()
    submissions = []
    chain = FakeChain(
        {"clean-hydrogen": [_finding("safe", provision="45V")]},
        errors={"advanced-manufacturing": RuntimeError("raw_response leaked")},
    )

    with pytest.raises(ValueError, match="raw_response"):
        run_daily_research(
            since=SINCE,
            verticals=("advanced-manufacturing", "clean-hydrogen"),
            write=True,
            client=client,  # type: ignore[arg-type]
            chain=chain,  # type: ignore[arg-type]
            submit=lambda **kwargs: submissions.append(kwargs),
        )

    assert submissions == []
    assert client.calls == []


def test_forbidden_public_metadata_fails_before_candidate_upsert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_writes(monkeypatch)
    client = RecordingSelectingSupabaseClient()
    submissions = []
    unsafe = _finding(
        "unsafe",
        raw_public_metadata={"raw_response": "x"},
    )

    with pytest.raises(ValueError, match="raw_response"):
        run_daily_research(
            since=SINCE,
            verticals=("advanced-manufacturing",),
            write=True,
            client=client,  # type: ignore[arg-type]
            chain=FakeChain({"advanced-manufacturing": [unsafe]}),  # type: ignore[arg-type]
            submit=lambda **kwargs: submissions.append(kwargs),
        )

    assert submissions == []
    assert client.calls == []
