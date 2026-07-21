"""Run daily, per-vertical policy research and governed evidence promotion.

Unlike ``daily_refresh``, this pipeline inserts ``pipeline_runs`` first among its
own writes because every ``policy_source_candidates.run_id`` is a non-null
foreign key to that client-generated run UUID.
"""

from __future__ import annotations

import argparse
import logging
import os
import uuid
from collections.abc import Callable, Sequence
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from pci_realtime import service
from pci_realtime.config import (
    PROVISION_KEYWORDS,
    RESEARCH_MAX_PROMOTIONS_PER_LANE,
    RESEARCH_MAX_REQUESTS_PER_RUN,
    RESEARCH_RUN_COST_CEILING_USD,
    SCORING_ESTIMATED_COST_PER_CALL_USD,
    VERTICALS,
)
from pci_realtime.env import load_local_env
from pci_realtime.registry.evidence import source_health_row, utc_now_iso
from pci_realtime.registry.store import (
    UPSERT_CONFLICT_KEYS,
    SupabaseRestClient,
    assert_public_payload_safe,
    write_json,
)
from pci_realtime.research.base import ResearchBudgetExceeded, RequestBudget
from pci_realtime.research.chain import FallbackChain, build_provider_chain
from pci_realtime.research.models import (
    CANDIDATE_SCHEMA_VERSION,
    LaneBrief,
    ResearchFinding,
    classify_source_class,
    finding_candidate_id,
    finding_idempotency_key,
    promotability_for,
)
from pci_realtime.service_errors import (
    BadRequest,
    RateLimited,
    ScoringUnavailable,
    ServiceError,
    SupabaseUnavailable,
    UpstreamTimeout,
    UpstreamUnavailable,
)


LOGGER = logging.getLogger(__name__)
SubmitEvidence = Callable[..., dict[str, Any]]
_RETRYABLE_PROMOTION_ERRORS = (
    ScoringUnavailable,
    SupabaseUnavailable,
    UpstreamUnavailable,
    UpstreamTimeout,
    RateLimited,
)


def build_lane_brief(
    vertical_id: str,
    *,
    since: date,
    max_findings: int = 8,
) -> LaneBrief:
    try:
        vertical = VERTICALS[vertical_id]
    except KeyError as exc:
        valid = ", ".join(_ordered_vertical_ids())
        raise ValueError(
            f"Unknown research vertical {vertical_id!r}. Valid verticals: {valid}."
        ) from exc
    provisions = tuple(vertical["provisions"])
    keywords = tuple(
        keyword for provision in provisions for keyword in PROVISION_KEYWORDS[provision]
    )
    return LaneBrief(
        vertical_id=vertical_id,
        vertical_name=str(vertical["name"]),
        provisions=provisions,
        coverage_note=str(vertical["coverage_note"]),
        keywords=keywords,
        since=since,
        max_findings=max_findings,
    )


def finding_to_candidate_row(
    finding: ResearchFinding,
    *,
    run_id: str,
    discovered_at: str,
) -> dict[str, Any]:
    source_class = classify_source_class(
        finding.url,
        finding.reported_source_class,
    )
    return {
        "candidate_id": finding_candidate_id(finding),
        "run_id": run_id,
        "schema_version": CANDIDATE_SCHEMA_VERSION,
        "discovered_at": discovered_at,
        "provision": finding.provision,
        "source_class": source_class,
        "review_state": "queued",
        "promotability": promotability_for(
            source_class,
            finding.citation_quote,
        ),
        "source_name": finding.source_name,
        "source_type": finding.evidence_type,
        "canonical_url": finding.url,
        "resolved_primary_url": None,
        "title": finding.title,
        "published_at": finding.published_at,
        "citation_quote": finding.citation_quote,
        "citation_section": finding.citation_section,
        "claim": finding.claim,
        "decision_relevance": finding.decision_relevance,
        "why_it_matters": finding.why_it_matters,
        "confidence": finding.confidence,
        "search_query": finding.search_query,
        "retrieved_at": discovered_at,
        "model_name": finding.model_name,
        "prompt_version": finding.prompt_version,
        "idempotency_key": finding_idempotency_key(finding),
        "duplicate_of": None,
        "related_evidence_ids": [],
        "reviewer_note": None,
        "reviewed_at": None,
        "promoted_submission_id": None,
        "promotion_result": {},
        "raw_public_metadata": {
            "provider": finding.provider,
            **finding.raw_public_metadata,
        },
        "raw_private_metadata": {},
    }


def run_daily_research(
    *,
    since: date,
    verticals: Sequence[str] | None = None,
    provider_spec: str | None = None,
    max_candidates_per_lane: int = 8,
    confirm_cost: bool = False,
    write: bool = False,
    output_path: Path | None = None,
    client: SupabaseRestClient | None = None,
    chain: FallbackChain | None = None,
    scorer: Any | None = None,
    submit: SubmitEvidence | None = None,
) -> dict[str, Any]:
    lane_ids = _normalize_vertical_ids(verticals)
    provider_chain = chain or build_provider_chain(provider_spec)
    max_promotions_per_lane = _max_promotions_per_lane()
    estimate = len(lane_ids) * provider_chain.estimated_cost_per_lane_usd() + (
        len(lane_ids) * max_promotions_per_lane * SCORING_ESTIMATED_COST_PER_CALL_USD
    )
    ceiling = float(
        os.getenv(
            "PCI_RESEARCH_RUN_COST_CEILING_USD",
            str(RESEARCH_RUN_COST_CEILING_USD),
        )
    )
    if estimate > ceiling and not confirm_cost:
        raise RuntimeError(
            f"Estimated research cost ${estimate:.2f} exceeds ceiling ${ceiling:.2f}. "
            "Pass --confirm-cost to run anyway."
        )

    budget = RequestBudget(
        max_requests=int(
            os.getenv(
                "PCI_RESEARCH_MAX_REQUESTS_PER_RUN",
                str(RESEARCH_MAX_REQUESTS_PER_RUN),
            )
        )
    )
    run_id = str(uuid.uuid4())
    started_at = utc_now_iso()
    run_provisions = tuple(
        dict.fromkeys(
            provision
            for vertical_id in lane_ids
            for provision in VERTICALS[vertical_id]["provisions"]
        )
    )

    write_client = client
    existing_candidates: dict[tuple[str, str], str] = {}
    existing_submissions: dict[tuple[str, str], str] = {}
    if write:
        if not service.status().get("write_configured"):
            raise SupabaseUnavailable(
                "Agent COI writes are not configured. Apply "
                "supabase/migrations/005_agent_evidence_intake.sql, then rerun."
            )
        write_client = write_client or SupabaseRestClient.from_env()
        if write_client is None:
            raise SupabaseUnavailable(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required."
            )
        provision_filter = f"in.({','.join(run_provisions)})"
        prior_candidate_rows = write_client.select_rows(
            "policy_source_candidates",
            columns="candidate_id,provision,canonical_url",
            params={
                "provision": provision_filter,
                "discovered_at": f"gte.{(since - timedelta(days=14)).isoformat()}",
            },
        )
        existing_candidates = {
            (str(row["provision"]), str(row["canonical_url"])): str(row["candidate_id"])
            for row in prior_candidate_rows
            if row.get("candidate_id")
            and row.get("provision")
            and row.get("canonical_url")
        }
        prior_submission_rows = write_client.select_rows(
            "evidence_submissions",
            columns="submission_id,provision,canonical_url",
            params={"provision": provision_filter},
        )
        existing_submissions = {
            (str(row["provision"]), str(row["canonical_url"])): str(
                row["submission_id"]
            )
            for row in prior_submission_rows
            if row.get("submission_id")
            and row.get("provision")
            and row.get("canonical_url")
        }

    lane_metrics = {vertical_id: _empty_lane_metrics() for vertical_id in lane_ids}
    lane_errors: dict[str, dict[str, str]] = {}
    findings_with_lanes: list[tuple[str, ResearchFinding]] = []
    successful_lanes = 0
    for vertical_id in lane_ids:
        brief = build_lane_brief(
            vertical_id,
            since=since,
            max_findings=max_candidates_per_lane,
        )
        try:
            result = provider_chain.run_research(brief, budget=budget)
        except ResearchBudgetExceeded:
            raise
        except Exception as exc:
            lane_metrics[vertical_id]["errors"] = 1
            lane_errors[vertical_id] = {
                "error_class": type(exc).__name__,
                "error_summary": str(exc),
            }
            continue
        successful_lanes += 1
        lane_findings = result.findings[: brief.max_findings]
        lane_metrics[vertical_id]["findings"] = len(lane_findings)
        findings_with_lanes.extend((vertical_id, finding) for finding in lane_findings)

    if successful_lanes == 0:
        raise RuntimeError("Daily research failed for every requested vertical.")

    discovered_at = utc_now_iso()
    seen_sources: set[tuple[str, str]] = set()
    seen_idempotency_keys: set[str] = set()
    candidates: list[tuple[str, ResearchFinding, dict[str, Any]]] = []
    for vertical_id, finding in findings_with_lanes:
        source_key = (finding.provision, finding.url)
        if source_key in seen_sources:
            lane_metrics[vertical_id]["duplicates"] += 1
            continue
        seen_sources.add(source_key)
        idempotency_key = finding_idempotency_key(finding)
        if idempotency_key in seen_idempotency_keys:
            lane_metrics[vertical_id]["duplicates"] += 1
            continue
        seen_idempotency_keys.add(idempotency_key)

        row = finding_to_candidate_row(
            finding,
            run_id=run_id,
            discovered_at=discovered_at,
        )
        if row["source_class"] != "official":
            row["review_state"] = "approved"
        if duplicate_of := existing_candidates.get(source_key):
            row["review_state"] = "duplicate"
            row["duplicate_of"] = duplicate_of
            lane_metrics[vertical_id]["duplicates"] += 1
        else:
            lane_metrics[vertical_id]["new_candidates"] += 1
        candidates.append((vertical_id, finding, row))

    if write:
        assert_public_payload_safe(
            {
                "provider": provider_chain.name,
                "estimated_cost_usd": estimate,
                "requests_used": budget.used,
                "lanes": lane_metrics,
                "lane_errors": lane_errors,
            }
        )
        for _, _, row in candidates:
            assert_public_payload_safe(row)
        assert write_client is not None
        submit_evidence = submit or service.submit_policy_evidence
        for vertical_id in lane_ids:
            promotable = sorted(
                (
                    item
                    for item in candidates
                    if item[0] == vertical_id
                    and item[2]["promotability"] == "ledger_candidate"
                    and item[2]["review_state"] != "duplicate"
                ),
                key=lambda item: item[1].confidence,
                reverse=True,
            )[:max_promotions_per_lane]
            vertical = VERTICALS[vertical_id]
            codes = tuple(vertical["provisions"])
            question = (
                f"What changed for {vertical['name']} ({', '.join(codes)}) "
                f"since {since.isoformat()}?"
            )
            for _, finding, row in promotable:
                source_key = (finding.provision, finding.url)
                if submission_id := existing_submissions.get(source_key):
                    row["review_state"] = "approved"
                    row["promoted_submission_id"] = submission_id
                    row["promotion_result"] = {
                        "status": "already_promoted",
                        "submission_id": submission_id,
                    }
                    lane_metrics[vertical_id]["promoted"] += 1
                    continue
                try:
                    promotion_result = submit_evidence(
                        provision=finding.provision,
                        source={
                            "url": finding.url,
                            "title": finding.title,
                            "source_name": finding.source_name,
                            "published_at": finding.published_at,
                        },
                        citation={
                            "quote": finding.citation_quote,
                            "section": finding.citation_section,
                            "url": finding.url,
                        },
                        claim=finding.claim,
                        idempotency_key=finding_idempotency_key(finding),
                        agent_name="pcindex-daily-research",
                        question=question,
                        client=write_client,
                        scorer=scorer,
                    )
                except BadRequest as exc:
                    row["review_state"] = "needs_primary_source"
                    row["promotion_result"] = _promotion_error(exc)
                    lane_metrics[vertical_id]["errors"] += 1
                except _RETRYABLE_PROMOTION_ERRORS as exc:
                    row["review_state"] = "queued"
                    row["promotion_result"] = _promotion_error(exc)
                    lane_metrics[vertical_id]["errors"] += 1
                except ServiceError as exc:
                    row["review_state"] = "queued"
                    row["promotion_result"] = _promotion_error(exc)
                    lane_metrics[vertical_id]["errors"] += 1
                except Exception as exc:
                    row["review_state"] = "queued"
                    row["promotion_result"] = _promotion_error(exc)
                    lane_metrics[vertical_id]["errors"] += 1
                else:
                    row["promotion_result"] = promotion_result
                    if promotion_result.get("status") == "duplicate":
                        row["review_state"] = "duplicate"
                        row["promoted_submission_id"] = _submission_id(promotion_result)
                        lane_metrics[vertical_id]["duplicates"] += 1
                    else:
                        row["review_state"] = "approved"
                        row["promoted_submission_id"] = _submission_id(promotion_result)
                        lane_metrics[vertical_id]["promoted"] += 1

    completed_at = utc_now_iso()
    candidate_rows = [row for _, _, row in candidates]
    lane_health_rows = [
        _lane_health_row(
            vertical_id,
            provider=provider_chain.name,
            metrics=lane_metrics[vertical_id],
            error=lane_errors.get(vertical_id),
            completed_at=completed_at,
        )
        for vertical_id in lane_ids
    ]
    counts = {
        "lanes": len(lane_ids),
        "successful_lanes": successful_lanes,
        "failed_lanes": len(lane_errors),
        "findings": sum(item["findings"] for item in lane_metrics.values()),
        "candidates": len(candidate_rows),
        "new_candidates": sum(item["new_candidates"] for item in lane_metrics.values()),
        "duplicates": sum(item["duplicates"] for item in lane_metrics.values()),
        "promoted": sum(item["promoted"] for item in lane_metrics.values()),
        "errors": sum(item["errors"] for item in lane_metrics.values()),
    }
    run_row = {
        "run_id": run_id,
        "run_type": "policy_discovery",
        "status": "success",
        "started_at": started_at,
        "completed_at": completed_at,
        "source": "daily_research.py",
        "metadata": {
            "provider": provider_chain.name,
            "estimated_cost_usd": estimate,
            "requests_used": budget.used,
            "lanes": lane_metrics,
            "lane_errors": lane_errors,
        },
    }
    rows_by_table = {
        "pipeline_runs": [run_row],
        "policy_source_candidates": candidate_rows,
        "source_health": lane_health_rows,
    }

    if write:
        assert write_client is not None
        assert_public_payload_safe(run_row)
        write_client.insert_rows("pipeline_runs", [run_row])
        for row in candidate_rows:
            assert_public_payload_safe(row)
        write_client.upsert_rows(
            "policy_source_candidates",
            candidate_rows,
            on_conflict=UPSERT_CONFLICT_KEYS["policy_source_candidates"],
        )
        for row in lane_health_rows:
            assert_public_payload_safe(row)
        write_client.upsert_rows(
            "source_health",
            lane_health_rows,
            on_conflict="source",
        )

    if output_path is not None:
        write_json(
            output_path,
            {
                "counts": counts,
                "rows": rows_by_table,
                "lanes": lane_metrics,
            },
        )

    return {
        "run_id": run_id,
        "counts": counts,
        "lanes": lane_metrics,
        "estimated_cost_usd": estimate,
        "requests_used": budget.used,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Research policy changes by climate-tech vertical and optionally "
            "write governed candidates to Supabase."
        )
    )
    parser.add_argument(
        "--since",
        type=date.fromisoformat,
        default=_yesterday_utc(),
        help="Earliest publication/update date (ISO YYYY-MM-DD; default: yesterday UTC).",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        dest="write",
        action="store_false",
        help="Research without pre-reads, promotions, or Supabase writes (default).",
    )
    mode.add_argument(
        "--write",
        dest="write",
        action="store_true",
        help="Write candidates and promote eligible official evidence.",
    )
    parser.set_defaults(write=False)
    parser.add_argument("--output-path")
    parser.add_argument(
        "--vertical",
        action="append",
        choices=_ordered_vertical_ids(),
        help="Research one vertical; repeatable. Defaults to all verticals.",
    )
    parser.add_argument("--provider")
    parser.add_argument("--max-candidates-per-lane", type=int, default=8)
    parser.add_argument("--confirm-cost", action="store_true")
    return parser


def main() -> None:
    load_local_env()
    logging.basicConfig(level=logging.INFO)
    args = build_arg_parser().parse_args()
    payload = run_daily_research(
        since=args.since,
        verticals=args.vertical,
        provider_spec=args.provider,
        max_candidates_per_lane=args.max_candidates_per_lane,
        confirm_cost=args.confirm_cost,
        write=args.write,
        output_path=Path(args.output_path) if args.output_path else None,
    )
    counts = payload["counts"]
    print(
        "Daily research complete: "
        f"{counts['successful_lanes']}/{counts['lanes']} lanes, "
        f"{counts['candidates']} candidates, {counts['promoted']} promoted, "
        f"{payload['requests_used']} provider requests."
    )


def _normalize_vertical_ids(verticals: Sequence[str] | None) -> tuple[str, ...]:
    if verticals is None:
        return _ordered_vertical_ids()
    lane_ids = tuple(dict.fromkeys(verticals))
    invalid = [vertical_id for vertical_id in lane_ids if vertical_id not in VERTICALS]
    if invalid:
        valid = ", ".join(_ordered_vertical_ids())
        raise ValueError(
            f"Unknown research vertical(s): {', '.join(invalid)}. Valid: {valid}."
        )
    return lane_ids


def _ordered_vertical_ids() -> tuple[str, ...]:
    return tuple(
        sorted(VERTICALS, key=lambda item: int(VERTICALS[item]["display_order"]))
    )


def _empty_lane_metrics() -> dict[str, int]:
    return {
        "findings": 0,
        "new_candidates": 0,
        "duplicates": 0,
        "promoted": 0,
        "errors": 0,
    }


def _max_promotions_per_lane() -> int:
    maximum = int(
        os.getenv(
            "PCI_RESEARCH_MAX_PROMOTIONS_PER_LANE",
            str(RESEARCH_MAX_PROMOTIONS_PER_LANE),
        )
    )
    if maximum < 0:
        raise ValueError("PCI_RESEARCH_MAX_PROMOTIONS_PER_LANE cannot be negative.")
    return maximum


def _promotion_error(exc: Exception) -> dict[str, Any]:
    message = exc.message if isinstance(exc, ServiceError) else str(exc)
    return {
        "status": "error",
        "error": {"code": type(exc).__name__, "message": message},
    }


def _submission_id(result: dict[str, Any]) -> str | None:
    if result.get("submission_id"):
        return str(result["submission_id"])
    submission = result.get("submission")
    if isinstance(submission, dict) and submission.get("submission_id"):
        return str(submission["submission_id"])
    return None


def _lane_health_row(
    vertical_id: str,
    *,
    provider: str,
    metrics: dict[str, int],
    error: dict[str, str] | None,
    completed_at: str,
) -> dict[str, Any]:
    vertical = VERTICALS[vertical_id]
    status = "failed" if error else "success"
    row = source_health_row(
        source=f"research:{vertical_id}",
        status=status,
        row_count=metrics["new_candidates"],
        last_attempt_at=completed_at,
        last_success_at=completed_at if status == "success" else None,
        error_class=error["error_class"] if error else None,
        error_summary=error["error_summary"] if error else None,
        details={
            "vertical": vertical_id,
            "provider": provider,
            "new_candidates": metrics["new_candidates"],
            "promoted": metrics["promoted"],
            "duplicates": metrics["duplicates"],
        },
    )
    row["source_name"] = f"Research — {vertical['name']}"
    return row


def _yesterday_utc() -> date:
    return datetime.now(timezone.utc).date() - timedelta(days=1)


if __name__ == "__main__":
    main()
