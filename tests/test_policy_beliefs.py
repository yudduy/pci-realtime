from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from pci_realtime.pipeline.policy_beliefs import (
    build_policy_belief_rows,
    posterior_from_likelihood,
    seed_policy_theses,
    write_policy_belief_rows,
)


FIXED_RUN_ID = "00000000-0000-0000-0000-000000000202"


class RecordingSupabaseClient:
    def __init__(self) -> None:
        self.inserts: list[tuple[str, int]] = []
        self.upserts: list[tuple[str, int, str | None]] = []

    def insert_rows(self, table: str, rows: list[dict[str, Any]]) -> None:
        self.inserts.append((table, len(rows)))

    def upsert_rows(
        self,
        table: str,
        rows: list[dict[str, Any]],
        *,
        on_conflict: str | None = None,
    ) -> None:
        self.upserts.append((table, len(rows), on_conflict))


def _verified_evidence(**overrides: Any) -> dict[str, Any]:
    row = {
        "evidence_id": "evidence:45V:test",
        "source_doc_id": "source:treasury:test",
        "provision": "45V",
        "evidence_type": "policy_evidence_citation",
        "snippet": "Treasury guidance clarifies 45V eligibility.",
        "normalized_signal": "+0.20 PCI",
        "score_dimension": "specificity",
        "confidence": 0.8,
        "created_at": "2026-06-20T00:00:00Z",
        "citation_quote": "Treasury guidance clarifies 45V eligibility.",
        "claim_hash": "claim:45v",
        "quote_hash": "quote:45v",
        "quote_verified_against_source": True,
        "source_title": "45V guidance",
        "source_name": "Treasury",
    }
    row.update(overrides)
    return row


def test_posterior_from_likelihood_uses_odds_update() -> None:
    assert posterior_from_likelihood(0.5, 2.0) == pytest.approx(0.6667)
    assert posterior_from_likelihood(0.5, 0.5) == pytest.approx(0.3333)


def test_policy_beliefs_build_verified_updates_and_briefs() -> None:
    rows = build_policy_belief_rows(
        since=date(2026, 6, 1),
        through=date(2026, 6, 23),
        run_id=FIXED_RUN_ID,
        provisions=("45V",),
        evidence_items=[_verified_evidence()],
        context_candidates=[
            {
                "candidate_id": "candidate:context",
                "provision": "45V",
                "review_state": "approved",
                "promotability": "context_only",
                "source_class": "analysis",
                "title": "Reviewed hydrogen context",
                "decision_relevance": "Prepare oversight questions.",
                "discovered_at": "2026-06-21T00:00:00Z",
            },
            {
                "candidate_id": "candidate:raw-news",
                "provision": "45V",
                "review_state": "queued",
                "promotability": "context_only",
                "source_class": "news",
                "title": "Unreviewed news",
                "discovered_at": "2026-06-21T00:00:00Z",
            },
        ],
        market_snapshots=[
            {
                "snapshot_id": "11111111-1111-1111-1111-111111111111",
                "query_name": "45V public market",
                "title": "Will 45V guidance change?",
                "market_probability": 0.42,
            }
        ],
        source_health=[{"source": "treasury", "status": "success"}],
    )

    assert rows["pipeline_runs"][0]["run_type"] == "policy_beliefs"
    assert len(rows["policy_theses"]) == 4
    assert len(rows["belief_updates"]) >= 1
    update = rows["belief_updates"][0]
    assert update["affected_evidence_ids"] == ["evidence:45V:test"]
    assert update["affected_candidate_ids"] == []
    assert update["market_snapshot_ids"] == ["11111111-1111-1111-1111-111111111111"]
    assert update["posterior_probability"] > update["prior_probability"]
    brief = rows["policy_briefs"][0]
    assert brief["candidate_ids"] == ["candidate:context"]
    assert "verified belief update" in brief["summary"]


def test_policy_beliefs_replay_hash_ignores_submission_idempotency() -> None:
    first = build_policy_belief_rows(
        since=date(2026, 6, 1),
        through=date(2026, 6, 23),
        run_id=FIXED_RUN_ID,
        provisions=("45V",),
        evidence_items=[_verified_evidence(raw_public_metadata={"idempotency_key": "a"})],
    )
    second = build_policy_belief_rows(
        since=date(2026, 6, 1),
        through=date(2026, 6, 23),
        run_id=FIXED_RUN_ID,
        provisions=("45V",),
        evidence_items=[_verified_evidence(raw_public_metadata={"idempotency_key": "b"})],
    )

    assert first["belief_updates"][0]["replay_hash"] == second["belief_updates"][0][
        "replay_hash"
    ]


def test_policy_beliefs_ignore_unverified_and_market_evidence() -> None:
    rows = build_policy_belief_rows(
        since=date(2026, 6, 1),
        through=date(2026, 6, 23),
        run_id=FIXED_RUN_ID,
        provisions=("45V",),
        evidence_items=[
            _verified_evidence(quote_verified_against_source=False),
            _verified_evidence(
                evidence_id="market:evidence",
                evidence_type="market_snapshot",
                quote_verified_against_source=True,
            ),
        ],
    )

    assert rows["belief_updates"] == []
    assert rows["policy_briefs"][0]["evidence_ids"] == []


def test_policy_belief_write_order() -> None:
    rows = build_policy_belief_rows(
        since=date(2026, 6, 1),
        through=date(2026, 6, 23),
        run_id=FIXED_RUN_ID,
        provisions=("45V",),
        evidence_items=[_verified_evidence()],
    )
    client = RecordingSupabaseClient()

    write_policy_belief_rows(rows, client=client)  # type: ignore[arg-type]

    assert client.inserts == [("pipeline_runs", 1)]
    assert client.upserts == [
        ("policy_theses", 4, "thesis_id"),
        ("belief_updates", len(rows["belief_updates"]), "update_id"),
        ("policy_briefs", 1, "brief_id"),
    ]


def test_seed_policy_theses_stays_scoped_to_tracked_provisions() -> None:
    rows = seed_policy_theses(provisions=("45X", "45V"))
    assert {row["provision"] for row in rows} == {"45X", "45V"}
    assert {row["thesis_type"] for row in rows} == {
        "legal_durability",
        "implementation_timing",
        "budget_exposure",
        "administrative_capacity",
    }
