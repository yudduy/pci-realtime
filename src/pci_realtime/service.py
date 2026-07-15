"""Agent-facing service interface for PCIndex reads and evidence intake."""

from __future__ import annotations

import math
import re
from datetime import date, datetime, timezone
from typing import Any, Mapping
from urllib.parse import quote

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
from pci_realtime.config import (
    BASELINE_PCI,
    PROVISION_DETAILS,
    TRACKED_PROVISIONS,
    UNCOVERED_VERTICALS,
    VERTICALS,
)
from pci_realtime.registry.evidence import excerpt
from pci_realtime.registry.store import SupabaseRestClient
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


def list_verticals() -> dict[str, Any]:
    client = _read_client()
    if client is None:
        rows = [_baseline_vertical_row(vertical_id) for vertical_id in VERTICALS]
        return {
            "verticals": rows,
            "uncovered": list(UNCOVERED_VERTICALS),
            "source": "baseline",
        }

    rows = _select(
        client,
        "v_vertical_pci",
        params={"order": "display_order.asc"},
    )
    return {
        "verticals": sorted(rows, key=_vertical_display_order),
        "uncovered": list(UNCOVERED_VERTICALS),
        "source": "registry",
    }


def vertical_status(vertical_id: str) -> dict[str, Any]:
    vertical_id = _normalize_vertical(vertical_id)
    provision_codes = list(VERTICALS[vertical_id]["provisions"])
    client = _read_client()
    if client is None:
        return {
            "vertical": _baseline_vertical_row(vertical_id),
            "provisions": [_baseline_row(code) for code in provision_codes],
            "source": "baseline",
        }

    vertical_rows = _select(
        client,
        "v_vertical_pci",
        params={"id": f"eq.{vertical_id}"},
    )
    vertical = next(
        (row for row in vertical_rows if str(row.get("id")) == vertical_id),
        _baseline_vertical_row(vertical_id),
    )
    current_rows = _select(
        client,
        "v_current_pci",
        params={"code": f"in.({','.join(provision_codes)})"},
    )
    current_by_code = {str(row.get("code")): row for row in current_rows}
    return {
        "vertical": vertical,
        "provisions": [
            current_by_code.get(code, _baseline_row(code)) for code in provision_codes
        ],
        "source": "registry",
    }


def list_changes(
    since: str | None = None,
    vertical: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """List cited policy changes using the public delivery contract."""
    normalized_since = _normalize_since(since)
    normalized_vertical = _normalize_vertical(vertical) if vertical else None
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
        raise BadRequest("Limit must be an integer between 1 and 200.")

    client = _require_read_client()
    events = _select(
        client,
        "v_policy_events",
        params={"order": "week_start.desc,created_at.desc"},
    )
    evidence = _select(
        client,
        "v_evidence_items",
        params={"order": "created_at.desc"},
    )
    links = _select(
        client,
        "v_source_links",
        params={"order": "created_at.desc"},
    )

    records = [
        record
        for event in events
        if (record := _change_record(event, evidence=evidence, links=links)) is not None
    ]
    if normalized_since:
        records = [record for record in records if record["date"] >= normalized_since]
    if normalized_vertical:
        records = [
            record for record in records if normalized_vertical in record["verticals"]
        ]
    records.sort(key=lambda record: str(record["id"]))
    records.sort(key=lambda record: str(record["date"]), reverse=True)
    records = records[:limit]

    return {
        "as_of": datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
        "count": len(records),
        "changes": records,
    }


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


def _baseline_vertical_row(vertical_id: str) -> dict[str, Any]:
    vertical = VERTICALS[vertical_id]
    provisions = vertical["provisions"]
    total_weight = sum(float(weight) for weight in provisions.values())
    baseline_pci = round(
        sum(
            float(BASELINE_PCI[code]["pci"]) * float(weight)
            for code, weight in provisions.items()
        )
        / total_weight,
        2,
    )
    return {
        "id": vertical_id,
        "name": vertical["name"],
        "coverage_note": vertical["coverage_note"],
        "display_order": vertical["display_order"],
        "vertical_pci": baseline_pci,
        "baseline_pci": baseline_pci,
        "weekly_delta": 0.0,
        "as_of_week_start": None,
        "last_change_week_start": None,
        "provisions": list(provisions),
    }


def _vertical_display_order(row: Mapping[str, Any]) -> int:
    try:
        return int(row.get("display_order", 0))
    except (TypeError, ValueError):
        return 0


def _normalize_vertical(vertical_id: str) -> str:
    normalized = str(vertical_id or "").strip().lower()
    if normalized not in VERTICALS:
        tracked = ", ".join(VERTICALS)
        raise BadRequest(f"Unknown vertical {vertical_id!r}. Tracked: {tracked}.")
    return normalized


def _normalize_since(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", normalized):
        raise BadRequest("Since must be a valid date in YYYY-MM-DD format.")
    try:
        date.fromisoformat(normalized)
    except ValueError as exc:
        raise BadRequest("Since must be a valid date in YYYY-MM-DD format.") from exc
    return normalized


def _change_record(
    event: Mapping[str, Any],
    *,
    evidence: list[dict[str, Any]],
    links: list[dict[str, Any]],
) -> dict[str, Any] | None:
    event_date = _date_only(
        event.get("week_start") or event.get("scored_at") or event.get("created_at")
    )
    if event_date is None:
        return None

    provisions = _event_provisions(event)
    verticals = [
        vertical_id
        for vertical_id, config in VERTICALS.items()
        if any(code in config["provisions"] for code in provisions)
    ]
    dimensions = _change_dimensions(event)
    method = {
        key: value
        for key in ("schema_version", "method_version", "prompt_version")
        if (value := _clean_text(event.get(key))) is not None
    }

    return {
        "id": str(event.get("event_id") or ""),
        "date": event_date,
        "verticals": verticals,
        "provisions": provisions,
        "title": _clean_text(event.get("title")) or "Official policy update",
        "summary": (
            _clean_text(event.get("summary"))
            or _clean_text(event.get("claim"))
            or _clean_text(event.get("rationale"))
            or ""
        ),
        "pci_delta": _finite_number(event.get("pci_delta")),
        "dimensions": dimensions,
        "citation": _event_citation(event, evidence=evidence, links=links),
        "method": method or None,
    }


def _event_provisions(event: Mapping[str, Any]) -> list[str]:
    raw = event.get("provisions")
    values = raw if isinstance(raw, (list, tuple)) else [event.get("provision")]
    provisions: list[str] = []
    for value in values:
        code = _clean_text(value)
        if code and code not in provisions:
            provisions.append(code)
    return provisions


def _change_dimensions(
    event: Mapping[str, Any],
) -> dict[str, float | int | None] | None:
    source = (
        event.get("dimensions")
        or event.get("dimension_scores")
        or event.get("dimension_deltas")
    )
    if not isinstance(source, Mapping):
        return None
    dimensions = {
        name: _finite_number(source.get(name))
        for name in ("specificity", "durability", "enforceability")
    }
    return (
        dimensions if any(value is not None for value in dimensions.values()) else None
    )


def _event_citation(
    event: Mapping[str, Any],
    *,
    evidence: list[dict[str, Any]],
    links: list[dict[str, Any]],
) -> dict[str, Any]:
    event_id = str(event.get("event_id") or "")
    evidence_ids = {
        str(link.get("evidence_id"))
        for link in links
        if link.get("target_table") == "policy_events"
        and str(link.get("target_id")) == event_id
    }
    linked = [item for item in evidence if str(item.get("evidence_id")) in evidence_ids]
    selected = linked[0] if linked else None
    url = None
    for item in linked:
        candidate = _citation_href(
            item.get("canonical_url") or item.get("url") or event.get("url"),
            item,
        )
        if candidate:
            selected = item
            url = candidate
            break
    url = url or _clean_text(event.get("url"))

    return {
        "url": url,
        "quote": _clean_text(
            (selected or {}).get("citation_quote") or (selected or {}).get("snippet")
        ),
        "source_name": _clean_text(
            (selected or {}).get("source_name")
            or (selected or {}).get("agency")
            or (selected or {}).get("source")
            or event.get("agency")
            or event.get("doc_source")
        ),
        "published_at": _clean_text((selected or {}).get("published_at")),
    }


def _citation_href(base_url: Any, item: Mapping[str, Any]) -> str | None:
    base = _clean_text(base_url)
    if not base or not re.match(r"^https?://", base, flags=re.IGNORECASE):
        return None

    explicit_fragment = _clean_text(item.get("citation_url_fragment"))
    if explicit_fragment:
        return _append_fragment(base, explicit_fragment)

    citation_quote = _clean_text(item.get("citation_quote"))
    if not citation_quote:
        return base
    compact_quote = " ".join(citation_quote.split())[:280].strip()
    fragment_name = "search" if re.search(r"\.pdf(?:[?#]|$)", base, re.I) else ":~:text"
    return _append_fragment(base, f"{fragment_name}={quote(compact_quote, safe='')}")


def _append_fragment(base_url: str, fragment: str) -> str:
    if re.match(r"^https?://", fragment, flags=re.IGNORECASE):
        return fragment
    clean_fragment = fragment[1:] if fragment.startswith("#") else fragment
    return f"{base_url.split('#', maxsplit=1)[0]}#{clean_fragment}"


def _date_only(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = _clean_text(value)
    if not text:
        return None
    direct = text[:10]
    try:
        return date.fromisoformat(direct).isoformat()
    except ValueError:
        try:
            return (
                datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
            )
        except ValueError:
            return None


def _finite_number(value: Any) -> float | int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if math.isfinite(value) else None


def _clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


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


def _page_title(soup: BeautifulSoup, url: str) -> str:
    if soup.title and soup.title.string:
        return " ".join(soup.title.string.split())
    return url
