from __future__ import annotations

import argparse
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd
from pydantic import BaseModel, Field, field_validator

from pci_realtime.agent_intake import (
    canonicalize_url,
    idempotency_key_hash,
    normalize_provision,
)
from pci_realtime.config import TRACKED_PROVISIONS
from pci_realtime.forecast_registry.evidence import (
    SOURCE_DISPLAY_NAMES,
    excerpt,
    source_health_row,
    stable_hash,
)
from pci_realtime.forecast_registry.policy import PROVISION_DETAILS
from pci_realtime.forecast_registry.store import (
    SupabaseRestClient,
    json_clean,
    write_json,
)
from pci_realtime.ingest.congress import CongressIngestor, PROPUBLICA_KEY_ENV
from pci_realtime.ingest.federal_register import FederalRegisterIngestor
from pci_realtime.ingest.omb import OmbIngestor
from pci_realtime.ingest.public_sources import (
    CONGRESS_GOV_KEY_ENV,
    REGULATIONS_GOV_KEY_ENV,
    RegInfoIngestor,
    RegulationsGovIngestor,
    USASpendingIngestor,
)
from pci_realtime.ingest.treasury import TreasuryIngestor


LOGGER = logging.getLogger(__name__)
SCHEMA_VERSION = "policy-discovery-v1"
PROMPT_VERSION = "policy-discovery-triage-v1"
DEFAULT_DISCOVERY_MODEL = os.getenv("PCI_POLICY_DISCOVERY_MODEL", "gpt-5.4-mini")
DEFAULT_INGEST_SOURCES = (
    "federal_register",
    "treasury",
    "irs",
    "omb",
    "congress",
    "regulations_gov",
    "reginfo",
    "usaspending",
)
KEYED_INGEST_SOURCES = {"regulations_gov": REGULATIONS_GOV_KEY_ENV}
CORE_POLICY_SOURCES = {"federal_register", "congress", "regulations_gov", "reginfo"}
SOURCE_CLASSES = {"official", "news", "analysis", "mixed"}
REVIEW_STATES = {"queued", "needs_primary_source", "approved", "duplicate", "rejected"}
PROMOTABILITY = {"ledger_candidate", "context_only"}
SOURCE_CLASS_ALIASES = {
    "official_source": "official",
    "primary": "official",
    "primary_source": "official",
    "government": "official",
    "media": "news",
    "press": "news",
    "commentary": "analysis",
    "research": "analysis",
}
REVIEW_STATE_ALIASES = {
    "pending": "queued",
    "review": "queued",
    "review_needed": "queued",
}
PROMOTABILITY_ALIASES = {
    "primary": "ledger_candidate",
    "primary_source": "ledger_candidate",
    "evidence": "ledger_candidate",
    "official_evidence": "ledger_candidate",
    "high": "context_only",
    "medium": "context_only",
    "low": "context_only",
    "lead": "context_only",
    "watch": "context_only",
    "context": "context_only",
    "none": "context_only",
}


class PolicyDiscoveryLead(BaseModel):
    provision: str = Field(description="One tracked PCI policy unit code.")
    source_title: str = Field(description="Public source or lead title.")
    source_name: str = Field(
        description="Publisher, outlet, agency, or authoring source."
    )
    url: str = Field(description="Public URL for the lead or source.")
    published_at: str | None = None
    citation_quote: str | None = None
    citation_section: str | None = None
    claim: str
    source_class: str = Field(
        default="mixed",
        description="One of: official, news, analysis, mixed.",
    )
    review_state: str = Field(
        default="queued",
        description="One of: queued, needs_primary_source, duplicate, rejected.",
    )
    promotability: str = Field(
        default="context_only",
        description="One of: ledger_candidate, context_only. Do not use high/medium/low.",
    )
    decision_relevance: str | None = None
    why_it_matters: str | None = None
    confidence: float = Field(default=0.5, ge=0, le=1)
    search_query: str | None = None
    resolved_primary_url: str | None = None

    @field_validator("provision")
    @classmethod
    def valid_provision(cls, value: str) -> str:
        return normalize_provision(value)

    @field_validator("source_class", mode="before")
    @classmethod
    def valid_source_class(cls, value: Any) -> str:
        return _normalize_choice(
            value,
            aliases=SOURCE_CLASS_ALIASES,
            allowed=SOURCE_CLASSES,
            field="source_class",
        )

    @field_validator("review_state", mode="before")
    @classmethod
    def valid_review_state(cls, value: Any) -> str:
        return _normalize_choice(
            value,
            aliases=REVIEW_STATE_ALIASES,
            allowed=REVIEW_STATES,
            field="review_state",
        )

    @field_validator("promotability", mode="before")
    @classmethod
    def valid_promotability(cls, value: Any) -> str:
        return _normalize_choice(
            value,
            aliases=PROMOTABILITY_ALIASES,
            allowed=PROMOTABILITY,
            field="promotability",
        )


class PolicyDiscoveryResearchResult(BaseModel):
    generated_for: str
    leads: list[PolicyDiscoveryLead]
    notes: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class PolicyDiscoveryResult:
    run_id: str
    counts: dict[str, int]
    rows_by_table: dict[str, list[dict[str, Any]]]


def build_policy_discovery_prompt(
    *,
    since: date,
    through: date,
    provisions: Sequence[str] = TRACKED_PROVISIONS,
    max_leads_per_provision: int = 2,
) -> str:
    lines = [
        "Find recent policy intelligence leads for PCIndex.",
        f"Window: {since.isoformat()} through {through.isoformat()}.",
        "Prefer primary official sources. News and analysis are leads only.",
        "Do not say a news story is ledger evidence unless it resolves to a public primary source.",
        "Separate source class from review action: official/news/analysis/mixed, then queued/needs_primary_source/duplicate/rejected.",
        "For promotability, use only ledger_candidate or context_only. Do not use high, medium, low, important, or priority.",
        f"Return at most {max_leads_per_provision} leads per provision.",
        "",
        "Tracked policy units:",
    ]
    for code in provisions:
        normalized = normalize_provision(code)
        details = PROVISION_DETAILS[normalized]
        lines.append(
            f"- {normalized}: {details['name']} ({details['primary_channel']})"
        )
    return "\n".join(lines)


def broad_web_search_tools() -> list[dict[str, Any]]:
    return [{"type": "web_search", "search_context_size": "medium"}]


def research_policy_leads_with_web_search(
    *,
    since: date,
    through: date | None = None,
    provisions: Sequence[str] = TRACKED_PROVISIONS,
    max_leads_per_provision: int = 2,
    model: str = DEFAULT_DISCOVERY_MODEL,
    client: Any | None = None,
) -> PolicyDiscoveryResearchResult:
    if client is None:
        from openai import OpenAI

        client = OpenAI()
    through = through or date.today()
    response = client.responses.parse(
        model=model,
        instructions=(
            "You are a policy intelligence scout. Use web search to find recent "
            "official sources, news leads, and analysis context, but never promote "
            "news into evidence. Return structured leads only."
        ),
        input=build_policy_discovery_prompt(
            since=since,
            through=through,
            provisions=provisions,
            max_leads_per_provision=max_leads_per_provision,
        ),
        tools=broad_web_search_tools(),
        text_format=PolicyDiscoveryResearchResult,
        max_output_tokens=8000,
    )
    parsed = getattr(response, "output_parsed", None)
    if parsed is None:
        parsed = PolicyDiscoveryResearchResult.model_validate_json(response.output_text)
    return normalize_research_result(parsed)


def normalize_research_result(
    result: PolicyDiscoveryResearchResult,
) -> PolicyDiscoveryResearchResult:
    seen: set[tuple[str, str, str]] = set()
    leads: list[PolicyDiscoveryLead] = []
    for lead in result.leads:
        canonical_url = canonicalize_url(lead.url)
        normalized = lead.model_copy(
            update={
                "provision": normalize_provision(lead.provision),
                "url": canonical_url,
                "resolved_primary_url": canonicalize_url(lead.resolved_primary_url)
                if lead.resolved_primary_url
                else None,
                "source_title": _clean_text(lead.source_title),
                "source_name": _clean_text(lead.source_name),
                "citation_quote": _clean_text(lead.citation_quote),
                "citation_section": _clean_text(lead.citation_section),
                "claim": _clean_text(lead.claim),
                "decision_relevance": _clean_text(lead.decision_relevance),
                "why_it_matters": _clean_text(lead.why_it_matters),
                "search_query": _clean_text(lead.search_query),
            }
        )
        key = (
            normalized.provision,
            normalized.url,
            stable_hash(normalized.claim, normalized.citation_quote),
        )
        if key in seen:
            continue
        seen.add(key)
        leads.append(normalized)
    return PolicyDiscoveryResearchResult(
        generated_for=result.generated_for,
        leads=leads,
        notes=list(result.notes),
    )


def build_policy_discovery_rows(
    *,
    since: date,
    through: date | None = None,
    run_id: str | None = None,
    provisions: Sequence[str] = TRACKED_PROVISIONS,
    ingest_sources: Sequence[str] = DEFAULT_INGEST_SOURCES,
    include_official_ingest: bool = True,
    include_web_search: bool = True,
    max_leads_per_provision: int = 2,
    official_documents: Iterable[Mapping[str, Any]] | None = None,
    web_result: PolicyDiscoveryResearchResult | None = None,
    existing_context: Iterable[Mapping[str, Any]] | None = None,
    research_client: Any | None = None,
) -> dict[str, list[dict[str, Any]]]:
    through = through or date.today()
    run_id = run_id or str(uuid.uuid4())
    started = time.monotonic()
    health_rows: list[dict[str, Any]] = []
    official_docs = list(official_documents or [])
    source_errors: dict[str, str] = {}

    if include_official_ingest and official_documents is None:
        official_docs, health_rows = collect_official_documents(
            since=since,
            through=through,
            sources=tuple(ingest_sources),
        )

    leads = leads_from_official_documents(official_docs, provisions=provisions)
    if include_web_search:
        provider_started = time.monotonic()
        try:
            result = web_result or research_policy_leads_with_web_search(
                since=since,
                through=through,
                provisions=provisions,
                max_leads_per_provision=max_leads_per_provision,
                client=research_client,
            )
            leads.extend(result.leads)
            health_rows.append(
                source_health_row(
                    source="openai_web_search",
                    status="success",
                    row_count=len(result.leads),
                    latency_ms=round((time.monotonic() - provider_started) * 1000),
                    details={"notes": result.notes, "prompt_version": PROMPT_VERSION},
                )
            )
        except Exception as exc:  # noqa: BLE001 - discovery should degrade.
            source_errors["openai_web_search"] = f"{type(exc).__name__}: {exc}"
            health_rows.append(
                source_health_row(
                    source="openai_web_search",
                    status="failed",
                    latency_ms=round((time.monotonic() - provider_started) * 1000),
                    error_class=type(exc).__name__,
                    error_summary=str(exc),
                )
            )

    context = list(existing_context or [])
    candidates = candidate_rows_from_leads(
        leads,
        run_id=run_id,
        existing_context=context,
    )
    metadata = {
        "window_start": since.isoformat(),
        "window_end": through.isoformat(),
        "provisions": [normalize_provision(code) for code in provisions],
        "official_documents": len(official_docs),
        "web_leads": sum(1 for lead in leads if lead.search_query),
        "policy_source_candidates": len(candidates),
        "source_errors": source_errors,
        "elapsed_ms": round((time.monotonic() - started) * 1000),
        "retrieval": {
            "mode": "structured_full_text_context",
            "embedding_index": "deferred",
        },
    }
    requested = int(include_official_ingest) + int(include_web_search)
    failures = sum(1 for row in health_rows if row.get("status") == "failed")
    status = "success" if not requested or failures < requested else "failed"
    return {
        "pipeline_runs": [
            {
                "run_id": run_id,
                "run_type": "policy_discovery",
                "status": status,
                "source": "policy_discovery.py",
                "metadata": metadata,
            }
        ],
        "policy_source_candidates": candidates,
        "source_health": health_rows,
    }


def collect_official_documents(
    *,
    since: date,
    through: date,
    sources: Sequence[str] = DEFAULT_INGEST_SOURCES,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    docs: list[dict[str, Any]] = []
    health_rows: list[dict[str, Any]] = []
    successful_core_sources: set[str] = set()
    for source in sources:
        if (
            source == "congress"
            and not os.getenv(CONGRESS_GOV_KEY_ENV)
            and not os.getenv(PROPUBLICA_KEY_ENV)
        ):
            health_rows.append(
                source_health_row(
                    source=source,
                    status="disabled",
                    row_count=0,
                    error_class="MissingApiKey",
                    error_summary=(
                        f"{CONGRESS_GOV_KEY_ENV} is not configured; "
                        f"{PROPUBLICA_KEY_ENV} fallback is also missing"
                    ),
                )
            )
            continue
        key_env = KEYED_INGEST_SOURCES.get(source)
        if key_env and not os.getenv(key_env):
            health_rows.append(
                source_health_row(
                    source=source,
                    status="disabled",
                    row_count=0,
                    error_class="MissingApiKey",
                    error_summary=f"{key_env} is not configured",
                )
            )
            continue
        started = time.monotonic()
        try:
            frame = _collect_source(source, since=since, through=through)
            rows = [json_clean(row) for row in frame.to_dict("records")]
            docs.extend(rows)
            health_rows.append(
                source_health_row(
                    source=source,
                    status="success",
                    row_count=len(rows),
                    latency_ms=round((time.monotonic() - started) * 1000),
                    details={
                        "window_start": since.isoformat(),
                        "window_end": through.isoformat(),
                    },
                )
            )
            if source in CORE_POLICY_SOURCES:
                successful_core_sources.add(source)
        except ValueError:
            raise
        except Exception as exc:  # noqa: BLE001 - source failures should degrade.
            LOGGER.warning("Source %s failed and will be skipped: %s", source, exc)
            health_rows.append(
                source_health_row(
                    source=source,
                    status="failed",
                    latency_ms=round((time.monotonic() - started) * 1000),
                    error_class=type(exc).__name__,
                    error_summary=str(exc),
                )
            )
    requested_core = CORE_POLICY_SOURCES.intersection(sources)
    failed_core = [
        row.get("source")
        for row in health_rows
        if row.get("source") in requested_core and row.get("status") == "failed"
    ]
    if requested_core and failed_core and not successful_core_sources:
        msg = f"All core official policy sources failed: {sorted(requested_core)}"
        raise RuntimeError(msg)
    return docs, health_rows


def leads_from_official_documents(
    docs: Iterable[Mapping[str, Any]],
    *,
    provisions: Sequence[str] = TRACKED_PROVISIONS,
) -> list[PolicyDiscoveryLead]:
    allowed = {normalize_provision(code) for code in provisions}
    leads: list[PolicyDiscoveryLead] = []
    for doc in docs:
        doc_provisions = [
            normalize_provision(code)
            for code in (doc.get("provisions_mentioned") or [])
            if str(code).upper() in allowed
        ]
        for code in doc_provisions:
            title = _clean_text(doc.get("title")) or str(
                doc.get("doc_id") or "Official source"
            )
            source = str(doc.get("source") or "official_source")
            body = _clean_text(doc.get("body"))
            quote = excerpt(body or title, max_chars=900)
            leads.append(
                PolicyDiscoveryLead(
                    provision=code,
                    source_title=title,
                    source_name=SOURCE_DISPLAY_NAMES.get(
                        source, source.replace("_", " ").title()
                    ),
                    url=str(doc.get("url") or ""),
                    published_at=str(doc.get("date") or "") or None,
                    citation_quote=quote,
                    claim=f"Official source may affect {code}: {title}",
                    source_class="official",
                    review_state="queued",
                    promotability="ledger_candidate",
                    decision_relevance="implementation_watch",
                    why_it_matters=f"Review this official source for decision impact on {code}.",
                    confidence=0.75,
                    resolved_primary_url=str(doc.get("url") or "") or None,
                )
            )
    return leads


def candidate_rows_from_leads(
    leads: Iterable[PolicyDiscoveryLead],
    *,
    run_id: str,
    existing_context: Iterable[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    context_rows = list(existing_context)
    existing_urls = _canonical_context_urls(context_rows)
    seen: set[tuple[str, str, str]] = set()
    rows: list[dict[str, Any]] = []
    for lead in leads:
        canonical_url = canonicalize_url(lead.url)
        quote = _clean_text(lead.citation_quote)
        claim = _clean_text(lead.claim)
        key = (lead.provision, canonical_url, stable_hash(claim, quote))
        if key in seen:
            continue
        seen.add(key)
        review_state, duplicate_of = _candidate_review_state(
            lead,
            canonical_url=canonical_url,
            existing_urls=existing_urls,
        )
        idempotency_key = policy_candidate_idempotency_key(
            provision=lead.provision,
            canonical_url=canonical_url,
            claim=claim,
            quote=quote,
        )
        duplicate_matches = [
            item
            for item in context_rows
            if _safe_canonical_url(item.get("canonical_url") or item.get("url"))
            == canonical_url
        ]
        related = _unique_context(
            [*duplicate_matches, *retrieve_related_context(lead, context_rows)]
        )
        row = {
            "candidate_id": policy_candidate_id(
                lead.provision, canonical_url, claim, quote
            ),
            "run_id": run_id,
            "schema_version": SCHEMA_VERSION,
            "provision": lead.provision,
            "source_class": lead.source_class,
            "review_state": review_state,
            "promotability": lead.promotability,
            "source_name": lead.source_name,
            "source_type": "policy_discovery_lead",
            "canonical_url": canonical_url,
            "resolved_primary_url": _resolved_primary_url(lead, canonical_url),
            "title": lead.source_title,
            "published_at": lead.published_at,
            "citation_quote": quote,
            "citation_section": lead.citation_section,
            "claim": claim,
            "decision_relevance": lead.decision_relevance,
            "why_it_matters": lead.why_it_matters,
            "confidence": lead.confidence,
            "search_query": lead.search_query,
            "model_name": DEFAULT_DISCOVERY_MODEL if lead.search_query else None,
            "prompt_version": PROMPT_VERSION if lead.search_query else None,
            "idempotency_key": idempotency_key,
            "duplicate_of": duplicate_of,
            "related_evidence_ids": [
                str(item.get("evidence_id"))
                for item in related
                if item.get("evidence_id")
            ],
            "raw_public_metadata": {
                "source_class": lead.source_class,
                "promotability": lead.promotability,
                "context_titles": _context_titles(related),
            },
            "raw_private_metadata": {
                "idempotency_key_hash": idempotency_key_hash(idempotency_key),
                "retrieval_mode": "structured_full_text_context",
            },
        }
        rows.append(json_clean(row))
    return rows


def retrieve_related_context(
    lead: PolicyDiscoveryLead,
    context_rows: Iterable[Mapping[str, Any]],
    *,
    limit: int = 5,
) -> list[Mapping[str, Any]]:
    tokens = set(
        _keyword_tokens(
            " ".join([lead.source_title, lead.claim, lead.citation_quote or ""])
        )
    )
    matches: list[tuple[int, Mapping[str, Any]]] = []
    for row in context_rows:
        if row.get("provision") not in {None, lead.provision}:
            continue
        haystack = " ".join(
            str(row.get(key) or "")
            for key in (
                "source_title",
                "title",
                "snippet",
                "citation_quote",
                "canonical_url",
                "url",
            )
        )
        score = len(tokens.intersection(_keyword_tokens(haystack)))
        if score:
            matches.append((score, row))
    return [
        row
        for _, row in sorted(matches, key=lambda item: item[0], reverse=True)[:limit]
    ]


def _normalize_choice(
    value: Any,
    *,
    aliases: Mapping[str, str],
    allowed: set[str],
    field: str,
) -> str:
    raw = str(value or "").strip().lower()
    normalized = aliases.get(raw, raw)
    if normalized not in allowed:
        raise ValueError(f"{field} must be one of {sorted(allowed)}")
    return normalized


def _candidate_review_state(
    lead: PolicyDiscoveryLead,
    *,
    canonical_url: str,
    existing_urls: set[str],
) -> tuple[str, str | None]:
    if canonical_url in existing_urls:
        return "duplicate", canonical_url
    if lead.source_class != "official" and lead.promotability == "ledger_candidate":
        return "needs_primary_source", None
    return lead.review_state, None


def _canonical_context_urls(rows: Iterable[Mapping[str, Any]]) -> set[str]:
    return {
        url
        for row in rows
        if (url := _safe_canonical_url(row.get("canonical_url") or row.get("url")))
    }


def _resolved_primary_url(lead: PolicyDiscoveryLead, canonical_url: str) -> str | None:
    if lead.resolved_primary_url:
        return canonicalize_url(lead.resolved_primary_url)
    if lead.source_class == "official":
        return canonical_url
    return None


def _context_titles(rows: Sequence[Mapping[str, Any]]) -> list[Any]:
    return [row.get("source_title") or row.get("title") for row in rows[:3]]


def _unique_context(rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    seen: set[str] = set()
    unique: list[Mapping[str, Any]] = []
    for row in rows:
        key = str(
            row.get("evidence_id")
            or row.get("canonical_url")
            or row.get("url")
            or id(row)
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def _safe_canonical_url(value: Any) -> str | None:
    if not value:
        return None
    try:
        return canonicalize_url(str(value))
    except Exception:  # noqa: BLE001 - malformed context rows should not break discovery.
        return None


def load_existing_context(
    client: SupabaseRestClient, provisions: Sequence[str]
) -> list[dict[str, Any]]:
    context: list[dict[str, Any]] = []
    for code in provisions:
        try:
            context.extend(
                client.select_rows(
                    "v_evidence_items",
                    params={"provision": f"eq.{normalize_provision(code)}"},
                )
            )
        except Exception as exc:  # noqa: BLE001 - context improves triage but is not required.
            LOGGER.warning("Could not load related evidence for %s: %s", code, exc)
    return context


def write_policy_discovery_rows(
    rows_by_table: dict[str, list[dict[str, Any]]],
    *,
    client: SupabaseRestClient,
) -> None:
    client.insert_rows("pipeline_runs", rows_by_table["pipeline_runs"])
    client.upsert_rows(
        "policy_source_candidates",
        rows_by_table["policy_source_candidates"],
        on_conflict="candidate_id",
    )
    client.upsert_rows(
        "source_health",
        rows_by_table["source_health"],
        on_conflict="source",
    )


def run_policy_discovery(
    *,
    since: date,
    through: date | None = None,
    ingest_sources: Sequence[str] = DEFAULT_INGEST_SOURCES,
    include_official_ingest: bool = True,
    include_web_search: bool = True,
    max_leads_per_provision: int = 2,
    dry_run: bool = False,
    output_path: Path | None = None,
    client: SupabaseRestClient | None = None,
) -> PolicyDiscoveryResult:
    run_id = str(uuid.uuid4())
    supabase = client or (None if dry_run else SupabaseRestClient.from_env())
    existing_context = (
        load_existing_context(supabase, TRACKED_PROVISIONS) if supabase else []
    )
    rows_by_table = build_policy_discovery_rows(
        since=since,
        through=through,
        run_id=run_id,
        ingest_sources=ingest_sources,
        include_official_ingest=include_official_ingest,
        include_web_search=include_web_search,
        max_leads_per_provision=max_leads_per_provision,
        existing_context=existing_context,
    )
    counts = {table: len(rows) for table, rows in rows_by_table.items()}
    if output_path is not None:
        write_json(
            output_path, {"run_id": run_id, "counts": counts, "rows": rows_by_table}
        )
    if not dry_run:
        if supabase is None:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required"
            )
        write_policy_discovery_rows(rows_by_table, client=supabase)
    return PolicyDiscoveryResult(
        run_id=run_id, counts=counts, rows_by_table=rows_by_table
    )


def policy_candidate_id(
    provision: str, canonical_url: str, claim: str, quote: str | None
) -> str:
    digest = stable_hash(
        "policy-source-candidate", provision, canonical_url, claim, quote
    )
    return f"policy-source:{digest[:24]}"


def policy_candidate_idempotency_key(
    *,
    provision: str,
    canonical_url: str,
    claim: str,
    quote: str | None,
) -> str:
    digest = stable_hash(canonical_url, claim, quote)[:24]
    return f"policy-discovery:{provision}:{digest}"


def build_policy_briefs(
    *,
    provisions: Sequence[str] = TRACKED_PROVISIONS,
    evidence_items: Iterable[Mapping[str, Any]] = (),
    context_candidates: Iterable[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    evidence = list(evidence_items)
    context = [
        row
        for row in context_candidates
        if row.get("review_state") == "approved"
        and row.get("promotability") == "context_only"
    ]
    briefs: list[dict[str, Any]] = []
    for code in provisions:
        normalized = normalize_provision(code)
        items = [row for row in evidence if row.get("provision") == normalized]
        leads = [row for row in context if row.get("provision") == normalized]
        briefs.append(
            {
                "provision": normalized,
                "name": PROVISION_DETAILS[normalized]["name"],
                "confirmed_evidence": sorted(items, key=_row_date, reverse=True),
                "reviewed_context_leads": sorted(leads, key=_row_date, reverse=True),
                "summary": _brief_summary(normalized, items, leads),
            }
        )
    return briefs


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run daily policy source discovery.")
    parser.add_argument("--since", help="Start date in YYYY-MM-DD format.")
    parser.add_argument(
        "--through", help="End date in YYYY-MM-DD format. Defaults to today."
    )
    parser.add_argument(
        "--ingest-source", action="append", choices=DEFAULT_INGEST_SOURCES
    )
    parser.add_argument("--no-official-ingest", action="store_true")
    parser.add_argument("--no-web-search", action="store_true")
    parser.add_argument("--max-leads-per-provision", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-path")
    parser.add_argument("--list-pending", action="store_true")
    parser.add_argument("--approve-id")
    parser.add_argument("--approve-context-id")
    parser.add_argument("--reject-id")
    parser.add_argument("--reviewer-note")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    from pci_realtime import service
    from pci_realtime.ingest.base import parse_date

    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.list_pending:
        _print_json(service.list_policy_source_candidates(review_state="queued"))
        return
    if args.approve_id:
        _print_json(service.promote_policy_source_candidate(args.approve_id))
        return
    if args.approve_context_id:
        _print_json(
            service.review_policy_source_candidate(
                args.approve_context_id,
                review_state="approved",
                reviewer_note=args.reviewer_note,
            )
        )
        return
    if args.reject_id:
        _print_json(
            service.review_policy_source_candidate(
                args.reject_id,
                review_state="rejected",
                reviewer_note=args.reviewer_note,
            )
        )
        return
    if not args.since:
        parser.error("--since is required unless using a review command")
    result = run_policy_discovery(
        since=parse_date(args.since),
        through=parse_date(args.through) if args.through else None,
        ingest_sources=tuple(args.ingest_source or DEFAULT_INGEST_SOURCES),
        include_official_ingest=not args.no_official_ingest,
        include_web_search=not args.no_web_search,
        max_leads_per_provision=args.max_leads_per_provision,
        dry_run=args.dry_run,
        output_path=Path(args.output_path) if args.output_path else None,
    )
    _print_json({"run_id": result.run_id, "counts": result.counts})


def _collect_source(source: str, *, since: date, through: date) -> pd.DataFrame:
    if source == "federal_register":
        return FederalRegisterIngestor().collect_documents(since, through)
    if source == "treasury":
        return TreasuryIngestor(source="treasury").collect_documents(since, through)
    if source == "irs":
        return TreasuryIngestor(source="irs").collect_documents(since, through)
    if source == "omb":
        return OmbIngestor().collect_documents(since, through)
    if source == "congress":
        return CongressIngestor().collect_documents(since, through)
    if source == "regulations_gov":
        return RegulationsGovIngestor().collect_documents(since, through)
    if source == "reginfo":
        return RegInfoIngestor().collect_documents(since, through)
    if source == "usaspending":
        return USASpendingIngestor().collect_documents(since, through)
    msg = f"Unsupported ingest source: {source}"
    raise ValueError(msg)


def _keyword_tokens(text: str) -> set[str]:
    return {
        token
        for token in "".join(ch if ch.isalnum() else " " for ch in text.lower()).split()
        if len(token) > 3
    }


def _print_json(payload: Any) -> None:
    print(json.dumps(json_clean(payload), sort_keys=True, default=str))


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _row_date(row: Mapping[str, Any]) -> str:
    return str(
        row.get("published_at")
        or row.get("created_at")
        or row.get("discovered_at")
        or ""
    )


def _brief_summary(
    provision: str,
    evidence: Sequence[Mapping[str, Any]],
    leads: Sequence[Mapping[str, Any]],
) -> str:
    if evidence:
        return f"{provision} has {len(evidence)} confirmed cited evidence item(s) in the ledger."
    if leads:
        return f"{provision} has {len(leads)} reviewed context lead(s) and no new confirmed evidence."
    return f"{provision} has no reviewed updates in the current brief window."


if __name__ == "__main__":  # pragma: no cover
    main()
