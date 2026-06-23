"""Agent-facing service interface for PCIndex reads and evidence intake."""

from __future__ import annotations

from typing import Any, Mapping

import httpx
import pandas as pd
from bs4 import BeautifulSoup

from pci_realtime.agent_intake import (
    AgentEvidenceBuildResult,
    PolicyScorer,
    build_agent_evidence_rows,
    canonicalize_url,
    idempotency_key_hash,
    normalize_provision,
)
from pci_realtime.config import BASELINE_PCI, TRACKED_PROVISIONS
from pci_realtime.forecast_registry.evidence import excerpt
from pci_realtime.forecast_registry.engine import utc_now_iso
from pci_realtime.forecast_registry.policy import PROVISION_DETAILS
from pci_realtime.forecast_registry.store import SupabaseRestClient
from pci_realtime.scoring.scorer import SCHEMA_B_COLUMNS
from pci_realtime.service_errors import (
    BadRequest,
    RateLimited,
    ServiceError,
    SupabaseUnavailable,
    UpstreamTimeout,
    UpstreamUnavailable,
)


_READ_UNAVAILABLE = (
    "Registry reads require SUPABASE_URL plus a publishable or service-role key."
)
_WRITE_UNAVAILABLE = (
    "Evidence intake requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
)


def status() -> dict[str, Any]:
    """Return registry reachability without raising."""
    read_client = _read_client()
    write_client = _write_client()
    write_credentials_configured = write_client is not None
    agent_intake_configured = (
        _agent_intake_configured(write_client) if write_client is not None else False
    )
    if read_client is None:
        return {
            "reachable": False,
            "registry_configured": False,
            "write_credentials_configured": write_credentials_configured,
            "agent_intake_configured": agent_intake_configured,
            "write_configured": False,
            "source": "baseline",
        }
    try:
        rows = _select(read_client, "v_current_pci")
    except ServiceError as exc:
        return {
            "reachable": False,
            "registry_configured": True,
            "write_credentials_configured": write_credentials_configured,
            "agent_intake_configured": agent_intake_configured,
            "write_configured": False,
            "error": {"code": exc.code, "message": exc.message},
        }
    return {
        "reachable": True,
        "registry_configured": True,
        "write_credentials_configured": write_credentials_configured,
        "agent_intake_configured": agent_intake_configured,
        "write_configured": write_credentials_configured and agent_intake_configured,
        "source": "registry",
        "tracked_policies": len(rows),
    }


def list_policies() -> dict[str, Any]:
    items = []
    for code in TRACKED_PROVISIONS:
        details = PROVISION_DETAILS[code]
        baseline = BASELINE_PCI[code]
        items.append(
            {
                "code": code,
                "name": details["name"],
                "type": details["type"],
                "primary_channel": details["primary_channel"],
                "baseline_pci": baseline["pci"],
            }
        )
    return {"policies": items, "count": len(items)}


def current_pci(code: str | None = None) -> dict[str, Any]:
    if code is not None:
        code = normalize_provision(code)
    client = _read_client()
    if client is None:
        if code:
            return _baseline_row(code)
        return {"policies": [_baseline_row(item) for item in TRACKED_PROVISIONS]}
    rows = _select(client, "v_current_pci")
    if code:
        match = next((row for row in rows if str(row.get("code")) == code), None)
        return {**(match or _baseline_row(code)), "source": "registry"}
    return {"policies": rows, "source": "registry"}


def policy_dossier(code: str) -> dict[str, Any]:
    code = normalize_provision(code)
    client = _require_read_client()
    current = current_pci(code)
    events = _select(client, "v_policy_events", params={"provision": f"eq.{code}"})
    evidence = _select(client, "v_evidence_items", params={"provision": f"eq.{code}"})
    submissions = _safe_select(
        client,
        "v_agent_evidence_submissions",
        params={"provision": f"eq.{code}"},
    )
    return {
        "policy": current,
        "events": events,
        "evidence": evidence,
        "submissions": submissions,
    }


def list_policy_source_candidates(
    *,
    review_state: str = "queued",
    limit: int = 50,
    client: SupabaseRestClient | None = None,
) -> dict[str, Any]:
    client = _require_write_client(client)
    rows = _select(
        client,
        "policy_source_candidates",
        params={
            "review_state": f"eq.{review_state}",
            "order": "discovered_at.desc",
            "limit": str(limit),
        },
    )
    return {"candidates": [_public_policy_candidate(row) for row in rows]}


def review_policy_source_candidate(
    candidate_id: str,
    *,
    review_state: str,
    reviewer_note: str | None = None,
    client: SupabaseRestClient | None = None,
) -> dict[str, Any]:
    client = _require_write_client(client)
    state = review_state.strip().lower()
    if state not in {"approved", "needs_primary_source", "duplicate", "rejected"}:
        raise BadRequest(
            "review_state must be approved, needs_primary_source, duplicate, or rejected."
        )
    row = _load_policy_source_candidate(client, candidate_id)
    if state == "approved" and row.get("promotability") == "ledger_candidate":
        raise BadRequest(
            "Ledger candidates must be approved through promote_policy_source_candidate."
        )
    updated = {
        **row,
        "review_state": state,
        "reviewer_note": reviewer_note,
        "reviewed_at": utc_now_iso(),
    }
    _upsert_agent_rows(client, "policy_source_candidates", [updated], "candidate_id")
    return {"status": state, "candidate": _public_policy_candidate(updated)}


def promote_policy_source_candidate(
    candidate_id: str,
    *,
    client: SupabaseRestClient | None = None,
    scorer: PolicyScorer | None = None,
) -> dict[str, Any]:
    client = _require_write_client(client)
    row = _load_policy_source_candidate(client, candidate_id)
    _validate_promotable_policy_candidate(row)
    quote = str(row.get("citation_quote") or "").strip()
    if not quote:
        raise BadRequest("Promotion requires an exact citation_quote.")
    source_url = row.get("resolved_primary_url") or row.get("canonical_url")

    result = submit_policy_evidence(
        provision=str(row["provision"]),
        source={
            "url": source_url,
            "title": row.get("title"),
            "source_name": row.get("source_name"),
            "published_at": row.get("published_at"),
        },
        citation={
            "quote": quote,
            "section": row.get("citation_section"),
            "url": source_url,
        },
        claim=str(row.get("claim") or ""),
        idempotency_key=str(row.get("idempotency_key") or ""),
        agent_name="policy-discovery",
        question=str(row.get("why_it_matters") or row.get("decision_relevance") or ""),
        client=client,
        scorer=scorer,
    )
    updated = {
        **row,
        "review_state": "approved",
        "reviewed_at": utc_now_iso(),
        "promoted_submission_id": _promotion_submission_id(result),
        "promotion_result": result,
    }
    _upsert_agent_rows(client, "policy_source_candidates", [updated], "candidate_id")
    return {
        "status": "approved",
        "candidate": _public_policy_candidate(updated),
        "promotion": result,
    }


def get_evidence_trace(
    provision: str,
    evidence_id: str | None = None,
) -> dict[str, Any]:
    code = normalize_provision(provision)
    client = _require_read_client()
    params = {"provision": f"eq.{code}"}
    if evidence_id:
        params["evidence_id"] = f"eq.{evidence_id}"
    evidence = _select(client, "v_evidence_items", params=params)
    links = _select(client, "v_source_links")
    events = _select(client, "v_policy_events", params={"provision": f"eq.{code}"})
    evidence_ids = {str(row.get("evidence_id")) for row in evidence}
    return {
        "provision": code,
        "evidence": evidence,
        "links": [row for row in links if str(row.get("evidence_id")) in evidence_ids],
        "events": events,
    }


def submit_policy_evidence(
    *,
    provision: str,
    source: Mapping[str, Any],
    citation: Mapping[str, Any],
    claim: str,
    idempotency_key: str,
    agent_run_id: str | None = None,
    agent_name: str | None = None,
    question: str | None = None,
    client: SupabaseRestClient | None = None,
    scorer: PolicyScorer | None = None,
) -> dict[str, Any]:
    client = client or _write_client()
    if client is None:
        raise SupabaseUnavailable(_WRITE_UNAVAILABLE)

    key_hash = idempotency_key_hash(idempotency_key)
    existing = _safe_select(
        client,
        "evidence_submissions",
        params={"idempotency_key_hash": f"eq.{key_hash}"},
    )
    if existing:
        return {
            "status": "duplicate",
            "submission": _public_submission(existing[0]),
        }

    result = build_agent_evidence_rows(
        provision=provision,
        source=source,
        citation=citation,
        claim=claim,
        idempotency_key=idempotency_key,
        agent_run_id=agent_run_id,
        agent_name=agent_name,
        question=question,
        scorer=scorer,
        historical_scored=_load_scored_deltas(client),
    )
    write_agent_intake_rows(result, client=client)
    return result.payload()


def ingest_source_url(
    *,
    provision: str,
    url: str,
    rationale: str,
    idempotency_key: str,
    agent_run_id: str | None = None,
    agent_name: str | None = None,
    question: str | None = None,
    client: SupabaseRestClient | None = None,
    scorer: PolicyScorer | None = None,
) -> dict[str, Any]:
    canonical_url = canonicalize_url(url)
    try:
        response = httpx.get(canonical_url, timeout=30, follow_redirects=True)
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise UpstreamTimeout(f"Timed out fetching {canonical_url}.") from exc
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            raise RateLimited(f"Rate limited fetching {canonical_url}.") from exc
        raise UpstreamUnavailable(
            f"Source returned HTTP {exc.response.status_code}."
        ) from exc
    except httpx.HTTPError as exc:
        raise UpstreamUnavailable(f"Could not fetch {canonical_url}.") from exc

    soup = BeautifulSoup(response.text, "html.parser")
    title = _page_title(soup, canonical_url)
    text = " ".join(soup.get_text(" ").split())
    quote = excerpt(text, max_chars=900)
    if not quote:
        raise BadRequest("Fetched source did not contain citeable text.")
    return submit_policy_evidence(
        provision=provision,
        source={
            "url": canonical_url,
            "title": title,
            "source_name": response.url.host if hasattr(response.url, "host") else None,
        },
        citation={"quote": quote, "url": canonical_url},
        claim=rationale,
        idempotency_key=idempotency_key,
        agent_run_id=agent_run_id,
        agent_name=agent_name,
        question=question,
        client=client,
        scorer=scorer,
    )


def write_agent_intake_rows(
    result: AgentEvidenceBuildResult,
    *,
    client: SupabaseRestClient,
) -> None:
    rows = result.rows_by_table
    _upsert_agent_rows(client, "agent_runs", rows["agent_runs"], "agent_run_id")
    _upsert_agent_rows(
        client,
        "source_documents",
        rows["source_documents"],
        "source_doc_id",
    )
    _upsert_agent_rows(
        client,
        "evidence_items",
        rows["evidence_items"],
        "evidence_id",
    )
    _upsert_agent_rows(
        client,
        "scored_deltas",
        rows["scored_deltas"],
        "week,doc_id,provision",
    )
    _upsert_agent_rows(
        client,
        "policy_events",
        rows["policy_events"],
        "event_id",
    )
    _upsert_agent_rows(
        client,
        "pci_weekly",
        rows["pci_weekly"],
        "provision,week",
    )
    _upsert_agent_rows(client, "source_links", rows["source_links"], "link_id")
    _upsert_agent_rows(
        client,
        "evidence_submissions",
        rows["evidence_submissions"],
        "submission_id",
    )


def _upsert_agent_rows(
    client: SupabaseRestClient,
    table: str,
    rows: list[dict[str, Any]],
    on_conflict: str,
) -> None:
    try:
        client.upsert_rows(table, rows, on_conflict=on_conflict)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404 and table in {
            "agent_runs",
            "evidence_submissions",
        }:
            raise SupabaseUnavailable(
                "Agent evidence intake migration is not applied. Apply "
                "supabase/migrations/005_agent_evidence_intake.sql before using "
                "MCP write tools."
            ) from exc
        raise UpstreamUnavailable(
            f"Registry write to {table} returned HTTP {exc.response.status_code}."
        ) from exc
    except httpx.TimeoutException as exc:
        raise UpstreamTimeout(f"Timed out writing {table}.") from exc
    except httpx.HTTPError as exc:
        raise UpstreamUnavailable(f"Could not write registry table {table}.") from exc


def _read_client() -> SupabaseRestClient | None:
    import os

    url = os.getenv("SUPABASE_URL")
    key = (
        os.getenv("SUPABASE_PUBLISHABLE_KEY")
        or os.getenv("SUPABASE_ANON_KEY")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SECRET_KEY")
    )
    if not url or not key:
        return None
    return SupabaseRestClient(url=url.rstrip("/"), service_role_key=key)


def _write_client() -> SupabaseRestClient | None:
    return SupabaseRestClient.from_env()


def _require_read_client() -> SupabaseRestClient:
    client = _read_client()
    if client is None:
        raise SupabaseUnavailable(_READ_UNAVAILABLE)
    return client


def _require_write_client(
    client: SupabaseRestClient | None = None,
) -> SupabaseRestClient:
    client = client or _write_client()
    if client is None:
        raise SupabaseUnavailable(_WRITE_UNAVAILABLE)
    return client


def _agent_intake_configured(client: SupabaseRestClient) -> bool:
    try:
        client.select_rows(
            "v_agent_evidence_submissions",
            columns="submission_id",
            params={"limit": "1"},
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return False
        return False
    except httpx.HTTPError:
        return False
    except (TypeError, ValueError):
        return False
    return True


def _select(
    client: SupabaseRestClient,
    view: str,
    params: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    try:
        return client.select_rows(view, params=params or {})
    except httpx.TimeoutException as exc:
        raise UpstreamTimeout(f"Timed out reading {view}.") from exc
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        if status_code == 429:
            raise RateLimited("Registry rate limit hit; retry shortly.") from exc
        raise UpstreamUnavailable(
            f"Registry returned HTTP {status_code} for {view}."
        ) from exc
    except httpx.HTTPError as exc:
        raise UpstreamUnavailable(f"Could not reach registry for {view}.") from exc
    except (TypeError, ValueError) as exc:
        raise UpstreamUnavailable(
            f"Unexpected response shape from registry for {view}."
        ) from exc


def _safe_select(
    client: SupabaseRestClient,
    table: str,
    params: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    try:
        return _select(client, table, params=params)
    except UpstreamUnavailable:
        return []


def _load_scored_deltas(client: SupabaseRestClient) -> pd.DataFrame:
    rows = _safe_select(
        client,
        "scored_deltas",
        params={},
    )
    if not rows:
        return pd.DataFrame(columns=[*SCHEMA_B_COLUMNS, "week"])
    return pd.DataFrame(rows)


def _load_policy_source_candidate(
    client: SupabaseRestClient,
    candidate_id: str,
) -> dict[str, Any]:
    rows = _select(
        client,
        "policy_source_candidates",
        params={"candidate_id": f"eq.{candidate_id}", "limit": "1"},
    )
    if not rows:
        raise BadRequest(f"Unknown policy source candidate: {candidate_id}")
    return rows[0]


def _validate_promotable_policy_candidate(row: Mapping[str, Any]) -> None:
    if row.get("source_class") != "official":
        raise BadRequest(
            "Only official primary-source candidates can be promoted to ledger evidence."
        )
    if row.get("promotability") != "ledger_candidate":
        raise BadRequest(
            "Only ledger_candidate rows can be promoted to ledger evidence."
        )
    if row.get("review_state") in {"duplicate", "rejected"}:
        raise BadRequest(
            f"Candidate is already {row.get('review_state')} and cannot be promoted."
        )


def _promotion_submission_id(result: Mapping[str, Any]) -> Any:
    if result.get("submission_id"):
        return result.get("submission_id")
    submission = result.get("submission")
    if isinstance(submission, Mapping):
        return submission.get("submission_id")
    return None


def _baseline_row(code: str) -> dict[str, Any]:
    baseline = BASELINE_PCI[code]
    details = PROVISION_DETAILS[code]
    return {
        "code": code,
        "name": details["name"],
        "pci": baseline["pci"],
        "specificity": baseline["specificity"],
        "durability": baseline["durability"],
        "enforceability": baseline["enforceability"],
        "baseline_pci": baseline["pci"],
        "source": "baseline",
    }


def _public_submission(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "submission_id": row.get("submission_id"),
        "agent_run_id": row.get("agent_run_id"),
        "provision": row.get("provision"),
        "status": row.get("status"),
        "source_doc_id": row.get("source_doc_id"),
        "evidence_id": row.get("evidence_id"),
        "event_id": row.get("event_id"),
        "claim_hash": row.get("claim_hash"),
        "submitted_at": row.get("submitted_at"),
        "promoted_at": row.get("promoted_at"),
    }


def _public_policy_candidate(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": row.get("candidate_id"),
        "run_id": row.get("run_id"),
        "discovered_at": row.get("discovered_at"),
        "provision": row.get("provision"),
        "source_class": row.get("source_class"),
        "review_state": row.get("review_state"),
        "promotability": row.get("promotability"),
        "source_name": row.get("source_name"),
        "source_type": row.get("source_type"),
        "canonical_url": row.get("canonical_url"),
        "resolved_primary_url": row.get("resolved_primary_url"),
        "title": row.get("title"),
        "published_at": row.get("published_at"),
        "citation_quote": row.get("citation_quote"),
        "citation_section": row.get("citation_section"),
        "claim": row.get("claim"),
        "decision_relevance": row.get("decision_relevance"),
        "why_it_matters": row.get("why_it_matters"),
        "confidence": row.get("confidence"),
        "duplicate_of": row.get("duplicate_of"),
        "related_evidence_ids": row.get("related_evidence_ids") or [],
        "reviewed_at": row.get("reviewed_at"),
        "promoted_submission_id": row.get("promoted_submission_id"),
        "promotion_result": row.get("promotion_result") or {},
        "raw_public_metadata": row.get("raw_public_metadata") or {},
    }


def _page_title(soup: BeautifulSoup, url: str) -> str:
    if soup.title and soup.title.string:
        return " ".join(soup.title.string.split())
    return url
