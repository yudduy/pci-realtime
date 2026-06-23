"""Collective evidence intake for agent-submitted policy sources."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Mapping, Protocol
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import pandas as pd

from pci_realtime.config import TRACKED_PROVISIONS
from pci_realtime.forecast_registry.evidence import excerpt, stable_hash
from pci_realtime.forecast_registry.store import json_clean, scored_delta_to_row
from pci_realtime.pci.builder import BASELINE_WEEK, build_weekly_index, parse_iso_week
from pci_realtime.scoring.scorer import (
    SCHEMA_B_COLUMNS,
    DocumentScorer,
    ScoringResult,
)
from pci_realtime.service_errors import BadRequest, ScoringUnavailable
from pci_realtime.source_verification import quote_verification_hash


PUBLIC_SOURCE = "contributor_intake"
PUBLIC_SOURCE_NAME = "Contributor intake"
INTAKE_EXTRACTOR_VERSION = "agent-coi-intake-v1"
_TRACKED = set(TRACKED_PROVISIONS)
_UTM_PREFIXES = ("utm_",)
_DROP_QUERY_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


class PolicyScorer(Protocol):
    def score_document(
        self,
        document: Mapping[str, Any],
        provision: str,
        cache_metadata: Mapping[str, Any] | None = None,
    ) -> ScoringResult: ...


@dataclass(frozen=True)
class AgentEvidenceBuildResult:
    status: str
    provision: str
    agent_run_id: str
    submission_id: str
    source_doc_id: str
    evidence_id: str
    event_id: str
    week: str
    claim_hash: str
    idempotency_key_hash: str
    rows_by_table: dict[str, list[dict[str, Any]]]

    def payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "provision": self.provision,
            "agent_run_id": self.agent_run_id,
            "submission_id": self.submission_id,
            "source_doc_id": self.source_doc_id,
            "evidence_id": self.evidence_id,
            "event_id": self.event_id,
            "week": self.week,
            "claim_hash": self.claim_hash,
        }


def normalize_provision(provision: str) -> str:
    code = str(provision or "").strip().upper()
    if code not in _TRACKED:
        tracked = ", ".join(TRACKED_PROVISIONS)
        raise BadRequest(f"Unknown policy unit {provision!r}. Tracked: {tracked}.")
    return code


def idempotency_key_hash(idempotency_key: str) -> str:
    key = _required_text(idempotency_key, "idempotency_key")
    return stable_hash("agent-coi-idempotency", key)


def canonicalize_url(url: str) -> str:
    value = _required_text(url, "source.url")
    parsed = urlparse(value)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    if scheme not in {"http", "https"} or not host:
        raise BadRequest("Evidence sources must use a public http(s) URL.")
    if _private_host(host):
        raise BadRequest("Evidence sources must be publicly reachable URLs.")

    port = ""
    if parsed.port and not (
        (scheme == "https" and parsed.port == 443)
        or (scheme == "http" and parsed.port == 80)
    ):
        port = f":{parsed.port}"

    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith(_UTM_PREFIXES)
        and key.lower() not in _DROP_QUERY_KEYS
    ]
    query.sort()
    path = parsed.path or "/"
    return urlunparse((scheme, f"{host}{port}", path, "", urlencode(query), ""))


def build_agent_evidence_rows(
    *,
    provision: str,
    source: Mapping[str, Any],
    citation: Mapping[str, Any],
    claim: str,
    idempotency_key: str,
    agent_run_id: str | None = None,
    agent_name: str | None = None,
    question: str | None = None,
    submitted_at: str | None = None,
    scorer: PolicyScorer | None = None,
    historical_scored: pd.DataFrame | list[dict[str, Any]] | None = None,
    source_verification: Mapping[str, Any] | None = None,
    reviewed_by: str | None = None,
    review_decision_code: str | None = None,
    approval_basis: str | None = None,
    promotion_policy_version: str | None = None,
) -> AgentEvidenceBuildResult:
    code = normalize_provision(provision)
    clean_claim = _required_text(claim, "claim")
    quote = _citation_quote(citation)
    canonical_url = canonicalize_url(
        str(source.get("url") or citation.get("url") or "")
    )
    source_name = _clean_text(source.get("source_name") or source.get("name"))
    if not source_name:
        source_name = urlparse(canonical_url).hostname or PUBLIC_SOURCE_NAME
    source_title = _clean_text(
        source.get("title") or citation.get("title") or clean_claim
    )
    if not source_title:
        source_title = clean_claim

    submitted_at = _timestamp_iso(submitted_at)
    week, week_start = _week_from_timestamp(
        source.get("published_at") or citation.get("published_at") or submitted_at
    )
    source_hash = stable_hash(canonical_url)
    source_slug = _slug(source_name)
    source_doc_id = f"source:{source_slug}:{source_hash[:16]}"
    claim_hash = stable_hash(code, _normalize_text(clean_claim), _normalize_text(quote))
    verification = _verification_metadata(source_verification, quote)
    review = _review_metadata(
        reviewed_by=reviewed_by,
        review_decision_code=review_decision_code,
        approval_basis=approval_basis,
        promotion_policy_version=promotion_policy_version,
    )
    evidence_id = f"evidence:{code}:{source_hash[:12]}:{claim_hash[:16]}"
    event_id = f"{week}:{source_doc_id}:{code}"
    key_hash = idempotency_key_hash(idempotency_key)
    submission_id = f"submission:{key_hash[:24]}"
    agent_run_id = agent_run_id or f"agent-run:{stable_hash(key_hash, code)[:16]}"

    document = {
        "doc_id": source_doc_id,
        "date": source.get("published_at") or submitted_at,
        "source": PUBLIC_SOURCE,
        "agency": source.get("agency") or source_name,
        "title": source_title,
        "url": canonical_url,
        "body": _document_body(
            target_provision=code,
            title=source_title,
            claim=clean_claim,
            quote=quote,
            rationale=question,
        ),
        "provisions_mentioned": [code],
    }
    score = _score_document(document, code, scorer=scorer, key_hash=key_hash)
    score_row = {
        **score.to_row(),
        "doc_id": source_doc_id,
        "provision": code,
        "week": week,
    }
    dimension_deltas = {
        "specificity": float(score_row["specificity_delta"]),
        "durability": float(score_row["durability_delta"]),
        "enforceability": float(score_row["enforceability_delta"]),
    }
    pci_delta = round(sum(dimension_deltas.values()) / 3.0, 4)
    primary_dimension = _primary_dimension(dimension_deltas)

    scored_frame = _combine_scored(historical_scored, score_row)
    weekly_rows = _weekly_rows(scored_frame, through_week=week)
    now = submitted_at

    rows_by_table = {
        "agent_runs": [
            {
                "agent_run_id": agent_run_id,
                "agent_name": agent_name or "policy-agent",
                "target_provision": code,
                "question": question,
                "status": "completed",
                "started_at": now,
                "completed_at": now,
                "raw_public_metadata": {
                    "intake_version": INTAKE_EXTRACTOR_VERSION,
                    "submission_id": submission_id,
                },
            }
        ],
        "source_documents": [
            {
                "source_doc_id": source_doc_id,
                "source": PUBLIC_SOURCE,
                "source_name": source_name,
                "source_type": "contributor_public_source",
                "external_id": source_hash[:24],
                "title": source_title,
                "agency": source.get("agency"),
                "url": canonical_url,
                "canonical_url": canonical_url,
                "published_at": source.get("published_at") or None,
                "fetched_at": now,
                "first_seen_at": now,
                "last_seen_at": now,
                "submitted_by_agent_run_id": agent_run_id,
                "content_hash": verification.get("source_content_hash")
                or stable_hash(canonical_url, source_title),
                "text_excerpt": excerpt(quote),
                "source_retrieved_at": verification.get("source_retrieved_at"),
                "source_retrieval_method": verification.get("source_retrieval_method"),
                "source_content_hash": verification.get("source_content_hash"),
                "raw_public_metadata": {
                    "provision": code,
                    "citation_section": citation.get("section"),
                    "verification_status": verification["verification_status"],
                },
            }
        ],
        "evidence_items": [
            {
                "evidence_id": evidence_id,
                "source_doc_id": source_doc_id,
                "provision": code,
                "evidence_type": "policy_evidence_citation",
                "snippet": excerpt(clean_claim),
                "normalized_signal": f"{pci_delta:+.2f} PCI",
                "score_dimension": primary_dimension,
                "confidence": score.confidence,
                "extractor_version": INTAKE_EXTRACTOR_VERSION,
                "created_at": now,
                "citation_quote": quote,
                "citation_section": _clean_text(citation.get("section")),
                "citation_page": _clean_text(citation.get("page")),
                "citation_url_fragment": _clean_text(citation.get("url_fragment")),
                "claim_hash": claim_hash,
                "quote_hash": verification["quote_hash"],
                "quote_verified_against_source": verification[
                    "quote_verified_against_source"
                ],
                "quote_locator_type": verification.get("quote_locator_type"),
                "quote_locator_value": verification.get("quote_locator_value"),
                "submitted_by_agent_run_id": agent_run_id,
                "extraction_confidence": _optional_float(
                    citation.get("confidence"), default=score.confidence
                ),
                "raw_public_metadata": {
                    "claim_hash": claim_hash,
                    "citation_required": True,
                    "verification_status": verification["verification_status"],
                },
            }
        ],
        "scored_deltas": [scored_delta_to_row(score_row)],
        "policy_events": [
            {
                "event_id": event_id,
                "provision": code,
                "week": week,
                "week_start": week_start,
                "doc_id": source_doc_id,
                "doc_source": PUBLIC_SOURCE,
                "agency": source.get("agency") or source_name,
                "title": source_title,
                "url": canonical_url,
                "pci_delta": pci_delta,
                "dimension_deltas": dimension_deltas,
                "rationale": score.rationale,
                "confidence": score.confidence,
                "prompt_version": score.prompt_version,
                "scored_at": score.scored_at,
                "data_origin": "agent_evidence",
                "created_at": now,
            }
        ],
        "pci_weekly": weekly_rows,
        "source_links": [
            {
                "link_id": f"link:policy_events:{event_id}",
                "evidence_id": evidence_id,
                "target_table": "policy_events",
                "target_id": event_id,
                "link_type": "score_basis",
                "created_at": now,
            }
        ],
        "evidence_submissions": [
            {
                "submission_id": submission_id,
                "idempotency_key_hash": key_hash,
                "agent_run_id": agent_run_id,
                "provision": code,
                "source_doc_id": source_doc_id,
                "evidence_id": evidence_id,
                "event_id": event_id,
                "canonical_url": canonical_url,
                "source_title": source_title,
                "claim_hash": claim_hash,
                "status": "promoted",
                "rejection_reason": None,
                "verification_status": verification["verification_status"],
                "verification_result": verification,
                **review,
                "promotion_result": {
                    "week": week,
                    "pci_delta": pci_delta,
                    "dimension_deltas": dimension_deltas,
                },
                "submitted_at": now,
                "promoted_at": now,
                "raw_public_metadata": {
                    "source_name": source_name,
                    "citation_section": citation.get("section"),
                    "verification_status": verification["verification_status"],
                },
            }
        ],
    }
    return AgentEvidenceBuildResult(
        status="promoted",
        provision=code,
        agent_run_id=agent_run_id,
        submission_id=submission_id,
        source_doc_id=source_doc_id,
        evidence_id=evidence_id,
        event_id=event_id,
        week=week,
        claim_hash=claim_hash,
        idempotency_key_hash=key_hash,
        rows_by_table=json_clean(rows_by_table),
    )


def _score_document(
    document: Mapping[str, Any],
    provision: str,
    *,
    scorer: PolicyScorer | None,
    key_hash: str,
) -> ScoringResult:
    scorer = scorer or DocumentScorer()
    try:
        return scorer.score_document(
            document,
            provision,
            cache_metadata={
                "agent_intake": True,
                "idempotency_key_hash": key_hash,
            },
        )
    except Exception as exc:  # noqa: BLE001 - exposed as clean service error.
        raise ScoringUnavailable(
            f"Evidence was not promoted because scoring failed: {exc}"
        ) from exc


def _weekly_rows(scored: pd.DataFrame, *, through_week: str) -> list[dict[str, Any]]:
    weekly = build_weekly_index(scored, end_week=through_week)
    event_ids: dict[tuple[str, str], list[str]] = {}
    for row in scored.to_dict("records"):
        week = str(row["week"])
        doc_id = str(row["doc_id"])
        provision = str(row["provision"])
        event_ids.setdefault((week, provision), []).append(
            f"{week}:{doc_id}:{provision}"
        )

    rows: list[dict[str, Any]] = []
    for row in weekly.to_dict("records"):
        week = str(row["week"])
        provision = str(row["provision"])
        n_docs = int(row.get("n_docs") or 0)
        if week == BASELINE_WEEK:
            origin = "paper_anchor"
        elif n_docs:
            origin = "live_scored"
        else:
            origin = "derived_stock"
        rows.append(
            {
                "provision": provision,
                "week": week,
                "week_start": parse_iso_week(week).date(),
                "pci": row["pci"],
                "specificity": row["specificity"],
                "durability": row["durability"],
                "enforceability": row["enforceability"],
                "n_docs": n_docs,
                "delta_this_week": row["delta_this_week"],
                "data_origin": origin,
                "source_event_ids": sorted(set(event_ids.get((week, provision), []))),
                "provenance_status": "complete",
                "updated_at": row["updated_at"],
            }
        )
    return [json_clean(row) for row in rows]


def _combine_scored(
    historical: pd.DataFrame | list[dict[str, Any]] | None,
    score_row: dict[str, Any],
) -> pd.DataFrame:
    frames = []
    if historical is not None:
        if isinstance(historical, pd.DataFrame):
            frames.append(historical.copy())
        elif historical:
            frames.append(pd.DataFrame(historical))
    frames.append(pd.DataFrame([score_row]))
    frame = pd.concat(frames, ignore_index=True)
    for column in [*SCHEMA_B_COLUMNS, "week"]:
        if column not in frame.columns:
            frame[column] = None
    return (
        frame.loc[:, [*SCHEMA_B_COLUMNS, "week"]]
        .drop_duplicates(["week", "doc_id", "provision"], keep="last")
        .reset_index(drop=True)
    )


def _document_body(
    *,
    target_provision: str,
    title: str,
    claim: str,
    quote: str,
    rationale: str | None,
) -> str:
    parts = [
        f"Target provision: {target_provision}",
        (
            "Provision mapping note: this evidence has already been mapped to "
            f"{target_provision}; score only this target policy unit."
        ),
        f"Title: {title}",
        f"Claim: {claim}",
        f"Cited source text: {quote}",
    ]
    if rationale:
        parts.append(f"Policy question: {rationale}")
    return "\n\n".join(parts)


def _citation_quote(citation: Mapping[str, Any]) -> str:
    quote = _clean_text(
        citation.get("quote")
        or citation.get("quoted_text")
        or citation.get("span")
        or citation.get("text")
    )
    if not quote:
        raise BadRequest("Evidence citation requires a quoted source span.")
    return quote


def _verification_metadata(
    source_verification: Mapping[str, Any] | None,
    quote: str,
) -> dict[str, Any]:
    result = dict(source_verification or {})
    status = str(
        result.get("verification_status") or result.get("status") or "not_checked"
    )
    verified = bool(result.get("quote_verified_against_source"))
    return {
        "verification_status": status,
        "quote_verified_against_source": verified,
        "source_retrieved_at": result.get("source_retrieved_at")
        or result.get("retrieved_at"),
        "source_retrieval_method": result.get("source_retrieval_method")
        or result.get("retrieval_method"),
        "source_content_hash": result.get("source_content_hash"),
        "quote_hash": result.get("quote_hash") or quote_verification_hash(quote),
        "quote_locator_type": result.get("quote_locator_type"),
        "quote_locator_value": result.get("quote_locator_value"),
        "source_text_excerpt": result.get("source_text_excerpt"),
        "error_class": result.get("error_class"),
        "error_summary": result.get("error_summary"),
    }


def _review_metadata(
    *,
    reviewed_by: str | None,
    review_decision_code: str | None,
    approval_basis: str | None,
    promotion_policy_version: str | None,
) -> dict[str, Any]:
    return {
        "reviewed_by": _clean_text(reviewed_by) or None,
        "review_decision_code": _clean_text(review_decision_code) or None,
        "approval_basis": _clean_text(approval_basis) or None,
        "promotion_policy_version": _clean_text(promotion_policy_version)
        or INTAKE_EXTRACTOR_VERSION,
    }


def _primary_dimension(deltas: Mapping[str, float]) -> str:
    non_zero = {key: abs(float(value or 0.0)) for key, value in deltas.items()}
    if not any(non_zero.values()):
        return "context"
    return max(non_zero, key=non_zero.get)


def _week_from_timestamp(value: Any) -> tuple[str, str]:
    parsed = _parse_datetime(value)
    iso = parsed.date().isocalendar()
    week = f"{iso.year}-W{iso.week:02d}"
    return week, date.fromisocalendar(iso.year, iso.week, 1).isoformat()


def _timestamp_iso(value: str | None = None) -> str:
    parsed = _parse_datetime(value)
    return parsed.isoformat()


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, datetime.min.time())
    elif value:
        text = str(value).replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            parsed = datetime.now(timezone.utc)
    else:
        parsed = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _optional_float(value: Any, *, default: float | None = None) -> float | None:
    if value is None or value == "":
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return min(1.0, max(0.0, parsed))


def _required_text(value: Any, field: str) -> str:
    text = _clean_text(value)
    if not text:
        raise BadRequest(f"{field} is required.")
    return text


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _normalize_text(value: str) -> str:
    return _clean_text(value).casefold()


def _private_host(host: str) -> bool:
    if host in {"localhost", "0.0.0.0"} or host.endswith(".local"):
        return True
    if host.startswith("127.") or host.startswith("10.") or host.startswith("192.168."):
        return True
    if re.match(r"^172\.(1[6-9]|2\d|3[0-1])\.", host):
        return True
    return False


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "source"


def new_agent_run_id() -> str:
    return f"agent-run:{uuid.uuid4()}"
