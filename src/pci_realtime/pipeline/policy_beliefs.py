from __future__ import annotations

import argparse
import json
import re
import uuid
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from pci_realtime.agent_intake import normalize_provision
from pci_realtime.config import BASELINE_PCI, TRACKED_PROVISIONS
from pci_realtime.forecast_registry.evidence import stable_hash
from pci_realtime.forecast_registry.engine import clamp_probability, utc_now_iso
from pci_realtime.forecast_registry.policy import PROVISION_DETAILS
from pci_realtime.forecast_registry.store import (
    SupabaseRestClient,
    json_clean,
    write_json,
)


UPDATER_VERSION = "policy-beliefs-v1"
DEFAULT_THESIS_TYPES = (
    "legal_durability",
    "implementation_timing",
    "budget_exposure",
    "administrative_capacity",
)
THESIS_LABELS = {
    "legal_durability": "Legal and statutory durability",
    "implementation_timing": "Agency implementation timing",
    "budget_exposure": "Budget and appropriations exposure",
    "administrative_capacity": "Administrative capacity",
}


def posterior_from_likelihood(
    prior_probability: float, likelihood_ratio: float
) -> float:
    prior = clamp_probability(prior_probability)
    ratio = max(0.01, float(likelihood_ratio))
    prior_odds = prior / (1.0 - prior)
    posterior_odds = prior_odds * ratio
    return round(clamp_probability(posterior_odds / (1.0 + posterior_odds)), 4)


def seed_policy_theses(
    *,
    provisions: Sequence[str] = TRACKED_PROVISIONS,
    generated_at: str | None = None,
) -> list[dict[str, Any]]:
    timestamp = generated_at or utc_now_iso()
    rows: list[dict[str, Any]] = []
    for provision in provisions:
        code = normalize_provision(provision)
        details = PROVISION_DETAILS[code]
        baseline_probability = _baseline_probability(code)
        for thesis_type in DEFAULT_THESIS_TYPES:
            rows.append(
                {
                    "thesis_id": f"thesis:{code}:{thesis_type}",
                    "provision": code,
                    "thesis_type": thesis_type,
                    "question": _thesis_question(code, thesis_type),
                    "prior_probability": baseline_probability,
                    "current_probability": baseline_probability,
                    "confidence": 0.45,
                    "status": "active",
                    "created_at": timestamp,
                    "updated_at": timestamp,
                    "raw_public_metadata": {
                        "policy_name": details["name"],
                        "label": THESIS_LABELS[thesis_type],
                    },
                    "raw_private_metadata": {},
                }
            )
    return rows


def build_policy_belief_rows(
    *,
    since: date,
    through: date | None = None,
    run_id: str | None = None,
    provisions: Sequence[str] = TRACKED_PROVISIONS,
    theses: Iterable[Mapping[str, Any]] | None = None,
    evidence_items: Iterable[Mapping[str, Any]] = (),
    context_candidates: Iterable[Mapping[str, Any]] = (),
    market_snapshots: Iterable[Mapping[str, Any]] = (),
    source_health: Iterable[Mapping[str, Any]] = (),
) -> dict[str, list[dict[str, Any]]]:
    through = through or date.today()
    run_id = run_id or str(uuid.uuid4())
    thesis_rows = list(theses or seed_policy_theses(provisions=provisions))
    active_theses = [
        dict(row)
        for row in thesis_rows
        if row.get("status", "active") == "active"
        and row.get("provision") in {normalize_provision(code) for code in provisions}
    ]
    verified_evidence = [
        dict(row)
        for row in evidence_items
        if _is_verified_policy_evidence(row)
        and _date_in_window(_row_date(row), since=since, through=through)
    ]
    reviewed_context = [
        dict(row)
        for row in context_candidates
        if row.get("review_state") == "approved"
        and row.get("promotability") == "context_only"
        and _date_in_window(_row_date(row), since=since, through=through)
    ]
    markets = [dict(row) for row in market_snapshots]
    updates = build_belief_updates(
        theses=active_theses,
        evidence_items=verified_evidence,
        market_snapshots=markets,
        run_id=run_id,
    )
    refreshed_theses = apply_updates_to_theses(active_theses, updates)
    briefs = build_policy_brief_rows(
        provisions=provisions,
        since=since,
        through=through,
        evidence_items=verified_evidence,
        context_candidates=reviewed_context,
        belief_updates=updates,
        source_health=source_health,
    )
    return {
        "pipeline_runs": [
            {
                "run_id": run_id,
                "run_type": "policy_beliefs",
                "status": "success",
                "source": "policy_beliefs.py",
                "metadata": {
                    "window_start": since.isoformat(),
                    "window_end": through.isoformat(),
                    "provisions": [normalize_provision(code) for code in provisions],
                    "verified_evidence": len(verified_evidence),
                    "reviewed_context": len(reviewed_context),
                    "belief_updates": len(updates),
                    "policy_briefs": len(briefs),
                    "updater_version": UPDATER_VERSION,
                },
            }
        ],
        "policy_theses": refreshed_theses,
        "belief_updates": updates,
        "policy_briefs": briefs,
    }


def build_belief_updates(
    *,
    theses: Iterable[Mapping[str, Any]],
    evidence_items: Iterable[Mapping[str, Any]],
    market_snapshots: Iterable[Mapping[str, Any]] = (),
    run_id: str | None = None,
) -> list[dict[str, Any]]:
    thesis_by_key = {
        (str(row["provision"]), str(row["thesis_type"])): dict(row) for row in theses
    }
    current = {
        str(row["thesis_id"]): float(row.get("current_probability") or 0.5)
        for row in thesis_by_key.values()
    }
    updates: list[dict[str, Any]] = []
    for item in sorted(evidence_items, key=lambda row: str(_row_date(row) or "")):
        code = normalize_provision(str(item.get("provision") or ""))
        thesis_types = _affected_thesis_types(item)
        for thesis_type in thesis_types:
            thesis = thesis_by_key.get((code, thesis_type))
            if not thesis:
                continue
            thesis_id = str(thesis["thesis_id"])
            prior = current[thesis_id]
            signal = _evidence_signal(item)
            posterior = posterior_from_likelihood(prior, signal["likelihood_ratio"])
            update = _belief_update_row(
                thesis=thesis,
                evidence=item,
                prior_probability=prior,
                posterior_probability=posterior,
                signal=signal,
                markets=_markets_for_provision(market_snapshots, code),
                run_id=run_id,
            )
            updates.append(update)
            current[thesis_id] = posterior
    return updates


def apply_updates_to_theses(
    theses: Iterable[Mapping[str, Any]],
    updates: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    latest_by_thesis: dict[str, Mapping[str, Any]] = {}
    for update in updates:
        latest_by_thesis[str(update["thesis_id"])] = update
    rows: list[dict[str, Any]] = []
    timestamp = utc_now_iso()
    for thesis in theses:
        row = dict(thesis)
        update = latest_by_thesis.get(str(row["thesis_id"]))
        if update:
            row["current_probability"] = update["posterior_probability"]
            row["updated_at"] = update.get("created_at") or timestamp
        rows.append(json_clean(row))
    return rows


def build_policy_brief_rows(
    *,
    provisions: Sequence[str],
    since: date,
    through: date,
    evidence_items: Iterable[Mapping[str, Any]],
    context_candidates: Iterable[Mapping[str, Any]],
    belief_updates: Iterable[Mapping[str, Any]],
    source_health: Iterable[Mapping[str, Any]] = (),
    brief_type: str = "daily",
) -> list[dict[str, Any]]:
    generated = utc_now_iso()
    evidence = [dict(row) for row in evidence_items]
    context = [dict(row) for row in context_candidates]
    updates = [dict(row) for row in belief_updates]
    health = [dict(row) for row in source_health]
    rows: list[dict[str, Any]] = []
    for provision in provisions:
        code = normalize_provision(provision)
        provision_evidence = [row for row in evidence if row.get("provision") == code]
        provision_context = [row for row in context if row.get("provision") == code]
        provision_updates = [row for row in updates if row.get("provision") == code]
        title = f"{code} policy intelligence brief"
        rows.append(
            json_clean(
                {
                    "brief_id": _brief_id(
                        provision=code,
                        brief_type=brief_type,
                        since=since,
                        through=through,
                    ),
                    "provision": code,
                    "brief_type": brief_type,
                    "period_start": since.isoformat(),
                    "period_end": through.isoformat(),
                    "generated_at": generated,
                    "title": title,
                    "summary": _brief_summary(
                        code, provision_evidence, provision_context, provision_updates
                    ),
                    "what_changed": _what_changed(
                        provision_evidence, provision_updates
                    ),
                    "why_it_matters": _why_it_matters(code, provision_updates),
                    "decision_relevance": _decision_relevance(code, provision_context),
                    "watch_items": _watch_items(code, provision_updates, health),
                    "evidence_ids": [
                        str(row.get("evidence_id"))
                        for row in provision_evidence
                        if row.get("evidence_id")
                    ],
                    "candidate_ids": [
                        str(row.get("candidate_id"))
                        for row in provision_context
                        if row.get("candidate_id")
                    ],
                    "thesis_update_ids": [
                        str(row.get("update_id"))
                        for row in provision_updates
                        if row.get("update_id")
                    ],
                    "source_health_summary": _source_health_summary(health),
                    "raw_public_metadata": {
                        "verified_evidence_count": len(provision_evidence),
                        "reviewed_context_count": len(provision_context),
                        "belief_update_count": len(provision_updates),
                    },
                    "raw_private_metadata": {},
                }
            )
        )
    return rows


def write_policy_belief_rows(
    rows_by_table: dict[str, list[dict[str, Any]]],
    *,
    client: SupabaseRestClient,
) -> None:
    client.insert_rows("pipeline_runs", rows_by_table["pipeline_runs"])
    client.upsert_rows(
        "policy_theses",
        rows_by_table["policy_theses"],
        on_conflict="thesis_id",
    )
    client.upsert_rows(
        "belief_updates",
        rows_by_table["belief_updates"],
        on_conflict="update_id",
    )
    client.upsert_rows(
        "policy_briefs",
        rows_by_table["policy_briefs"],
        on_conflict="brief_id",
    )


def run_policy_beliefs(
    *,
    since: date,
    through: date | None = None,
    dry_run: bool = False,
    output_path: Path | None = None,
    client: SupabaseRestClient | None = None,
) -> dict[str, Any]:
    supabase = client or (None if dry_run else SupabaseRestClient.from_env())
    loaded = load_policy_belief_inputs(supabase) if supabase else {}
    rows_by_table = build_policy_belief_rows(
        since=since,
        through=through,
        theses=loaded.get("policy_theses"),
        evidence_items=loaded.get("evidence_items", []),
        context_candidates=loaded.get("policy_source_candidates", []),
        market_snapshots=loaded.get("market_snapshots", []),
        source_health=loaded.get("source_health", []),
    )
    if output_path:
        write_json(output_path, rows_by_table)
    if not dry_run:
        if supabase is None:
            supabase = SupabaseRestClient.from_env()
        write_policy_belief_rows(rows_by_table, client=supabase)
    return {
        "run_id": rows_by_table["pipeline_runs"][0]["run_id"],
        "counts": {table: len(rows) for table, rows in rows_by_table.items()},
        "rows_by_table": rows_by_table,
    }


def load_policy_belief_inputs(
    client: SupabaseRestClient | None,
) -> dict[str, list[dict[str, Any]]]:
    if client is None:
        return {}
    return {
        "policy_theses": _safe_select(client, "v_policy_theses"),
        "evidence_items": _safe_select(client, "v_policy_evidence_items"),
        "policy_source_candidates": _safe_select(client, "v_policy_source_candidates"),
        "market_snapshots": _safe_select(client, "v_market_snapshots"),
        "source_health": _safe_select(client, "v_source_health"),
    }


def _belief_update_row(
    *,
    thesis: Mapping[str, Any],
    evidence: Mapping[str, Any],
    prior_probability: float,
    posterior_probability: float,
    signal: Mapping[str, Any],
    markets: Sequence[Mapping[str, Any]],
    run_id: str | None,
) -> dict[str, Any]:
    created_at = utc_now_iso()
    market_ids = [
        str(row.get("snapshot_id"))
        for row in markets
        if row.get("snapshot_id") and _looks_like_uuid(str(row.get("snapshot_id")))
    ]
    market_metadata = _market_public_metadata(markets)
    replay_hash = _replay_hash(
        thesis_id=str(thesis["thesis_id"]),
        evidence=evidence,
        prior_probability=prior_probability,
        likelihood_ratio=float(signal["likelihood_ratio"]),
        market_snapshot_ids=market_ids,
        market_metadata=market_metadata,
    )
    return json_clean(
        {
            "update_id": f"belief:{stable_hash(replay_hash)[:32]}",
            "thesis_id": thesis["thesis_id"],
            "provision": thesis["provision"],
            "run_id": run_id,
            "prior_probability": round(prior_probability, 4),
            "likelihood_ratio": round(float(signal["likelihood_ratio"]), 4),
            "posterior_probability": posterior_probability,
            "direction": signal["direction"],
            "magnitude": signal["magnitude"],
            "reliability": signal["reliability"],
            "novelty": signal["novelty"],
            "affected_evidence_ids": [str(evidence.get("evidence_id"))],
            "affected_candidate_ids": [],
            "market_snapshot_ids": market_ids,
            "rationale": _update_rationale(thesis, evidence, signal, markets),
            "counterargument": _counterargument(signal),
            "decision_implication": _update_decision_implication(thesis, signal),
            "model_name": None,
            "prompt_version": None,
            "updater_version": UPDATER_VERSION,
            "replay_hash": replay_hash,
            "adjudication_state": "approved",
            "created_at": created_at,
            "raw_public_metadata": market_metadata,
            "raw_private_metadata": {},
        }
    )


def _source_health_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    statuses: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status") or "unknown")
        statuses[status] = statuses.get(status, 0) + 1
    return {"statuses": statuses}


def _brief_summary(
    provision: str,
    evidence: Sequence[Mapping[str, Any]],
    context: Sequence[Mapping[str, Any]],
    updates: Sequence[Mapping[str, Any]],
) -> str:
    if updates:
        return (
            f"{provision} has {len(updates)} verified belief update(s) backed by "
            f"{len(evidence)} cited evidence item(s)."
        )
    if evidence or context:
        return (
            f"{provision} has reviewed source activity, but no deterministic thesis "
            "move in this window."
        )
    return f"{provision} has no reviewed policy-intelligence updates in this window."


def _what_changed(
    evidence: Sequence[Mapping[str, Any]],
    updates: Sequence[Mapping[str, Any]],
) -> str:
    if updates:
        strongest = updates[0]
        return str(
            strongest.get("rationale") or "A verified source changed a tracked thesis."
        )
    if evidence:
        title = evidence[0].get("source_title") or evidence[0].get("snippet")
        return f"Verified evidence was added: {title}."
    return "No verified ledger evidence changed in this window."


def _why_it_matters(provision: str, updates: Sequence[Mapping[str, Any]]) -> str:
    if updates:
        return str(updates[0].get("decision_implication") or "")
    return (
        f"Staff should treat {provision} as unchanged unless new verified primary "
        "evidence appears."
    )


def _decision_relevance(
    provision: str,
    context: Sequence[Mapping[str, Any]],
) -> str:
    if context:
        return str(
            context[0].get("decision_relevance")
            or context[0].get("why_it_matters")
            or "Reviewed context lead is available for staff follow-up."
        )
    return f"No new {provision} staff action is suggested by reviewed evidence alone."


def _watch_items(
    provision: str,
    updates: Sequence[Mapping[str, Any]],
    source_health: Sequence[Mapping[str, Any]],
) -> list[str]:
    items = [f"Watch for new primary-source activity affecting {provision}."]
    if updates:
        items.insert(0, str(updates[0].get("counterargument") or items[0]))
    stale = [
        str(row.get("source"))
        for row in source_health
        if str(row.get("status") or "").lower() in {"failed", "stale"}
    ][:3]
    if stale:
        items.append("Refresh or inspect stale source feeds: " + ", ".join(stale) + ".")
    return items


def _evidence_signal(row: Mapping[str, Any]) -> dict[str, Any]:
    delta = _numeric_delta(row)
    reliability = "high" if row.get("quote_verified_against_source") else "medium"
    novelty = "new"
    magnitude = "low"
    if abs(delta) >= 0.5:
        magnitude = "high"
    elif abs(delta) >= 0.1:
        magnitude = "medium"
    direction = "neutral"
    if delta > 0:
        direction = "strengthens"
    elif delta < 0:
        direction = "weakens"
    factor = {"low": 0.04, "medium": 0.10, "high": 0.18}[magnitude]
    likelihood = 1.0
    if direction == "strengthens":
        likelihood = 1.0 + factor
    elif direction == "weakens":
        likelihood = 1.0 / (1.0 + factor)
    return {
        "delta": delta,
        "direction": direction,
        "magnitude": magnitude,
        "reliability": reliability,
        "novelty": novelty,
        "likelihood_ratio": likelihood,
    }


def _affected_thesis_types(row: Mapping[str, Any]) -> list[str]:
    text = " ".join(
        str(row.get(key) or "")
        for key in ("snippet", "normalized_signal", "source_title", "citation_quote")
    ).casefold()
    if any(
        word in text for word in ("budget", "appropriation", "rescission", "funding")
    ):
        return ["budget_exposure", "legal_durability"]
    if any(word in text for word in ("guidance", "rule", "criteria", "eligibility")):
        return ["implementation_timing", "legal_durability"]
    if any(word in text for word in ("backlog", "staff", "application", "capacity")):
        return ["administrative_capacity"]
    return ["implementation_timing"]


def _numeric_delta(row: Mapping[str, Any]) -> float:
    signal = str(row.get("normalized_signal") or "")
    match = re.search(r"([+-]?\d+(?:\.\d+)?)", signal)
    if match:
        return float(match.group(1))
    return 0.02 if row.get("quote_verified_against_source") else 0.0


def _is_verified_policy_evidence(row: Mapping[str, Any]) -> bool:
    if not row.get("provision"):
        return False
    if row.get("evidence_type") == "market_snapshot":
        return False
    return bool(row.get("quote_verified_against_source"))


def _markets_for_provision(
    market_snapshots: Iterable[Mapping[str, Any]],
    provision: str,
) -> list[Mapping[str, Any]]:
    code = normalize_provision(provision)
    matches = []
    for market in market_snapshots:
        haystack = " ".join(
            str(market.get(key) or "")
            for key in ("query_name", "title", "subtitle", "ticker", "event_ticker")
        ).upper()
        if code in haystack:
            matches.append(market)
    return matches[:3]


def _market_public_metadata(markets: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    probabilities = [
        float(row["market_probability"])
        for row in markets
        if row.get("market_probability") is not None
    ]
    if not probabilities:
        return {"market_probability": None, "market_count": 0}
    return {
        "market_probability": round(sum(probabilities) / len(probabilities), 4),
        "market_count": len(probabilities),
    }


def _update_rationale(
    thesis: Mapping[str, Any],
    evidence: Mapping[str, Any],
    signal: Mapping[str, Any],
    markets: Sequence[Mapping[str, Any]],
) -> str:
    title = (
        evidence.get("source_title") or evidence.get("snippet") or "Verified evidence"
    )
    market_note = ""
    market_meta = _market_public_metadata(markets)
    if market_meta["market_probability"] is not None:
        market_note = f" Market anchor: {market_meta['market_probability']:.0%}."
    return (
        f"{signal['direction']} {thesis['thesis_type']} thesis based on cited source: "
        f"{title}.{market_note}"
    )


def _counterargument(signal: Mapping[str, Any]) -> str:
    if signal["direction"] == "neutral":
        return "The evidence may be already reflected in the ledger and should not move the thesis further."
    return (
        "The source may be narrow, procedural, or already anticipated by stakeholders."
    )


def _update_decision_implication(
    thesis: Mapping[str, Any],
    signal: Mapping[str, Any],
) -> str:
    return (
        f"Use this as a {signal['magnitude']} {signal['reliability']} signal when "
        f"briefing {thesis['provision']} {thesis['thesis_type'].replace('_', ' ')}."
    )


def _replay_hash(
    *,
    thesis_id: str,
    evidence: Mapping[str, Any],
    prior_probability: float,
    likelihood_ratio: float,
    market_snapshot_ids: Sequence[str],
    market_metadata: Mapping[str, Any],
) -> str:
    payload = {
        "thesis_id": thesis_id,
        "evidence_id": evidence.get("evidence_id"),
        "claim_hash": evidence.get("claim_hash"),
        "quote_hash": evidence.get("quote_hash"),
        "normalized_signal": evidence.get("normalized_signal"),
        "prior_probability": round(prior_probability, 4),
        "likelihood_ratio": round(likelihood_ratio, 4),
        "market_snapshot_ids": sorted(market_snapshot_ids),
        "market_metadata": dict(sorted(market_metadata.items())),
        "updater_version": UPDATER_VERSION,
    }
    return stable_hash(json.dumps(payload, sort_keys=True, default=str))


def _baseline_probability(provision: str) -> float:
    baseline = float(BASELINE_PCI[provision]["pci"])
    return round(min(0.85, max(0.15, baseline / 5.0)), 4)


def _thesis_question(provision: str, thesis_type: str) -> str:
    name = PROVISION_DETAILS[provision]["name"]
    if thesis_type == "legal_durability":
        return f"Probability {name} remains materially intact through FY2027."
    if thesis_type == "implementation_timing":
        return f"Probability {name} implementation avoids material federal delay over the next two quarters."
    if thesis_type == "budget_exposure":
        return f"Probability {name} avoids material rescission, exhaustion, or funding interruption."
    return f"Probability responsible agencies can administer {name} without material backlog or enforcement gap."


def _brief_id(*, provision: str, brief_type: str, since: date, through: date) -> str:
    return (
        f"brief:{provision}:{brief_type}:"
        f"{stable_hash(since.isoformat(), through.isoformat())[:16]}"
    )


def _row_date(row: Mapping[str, Any]) -> str | None:
    for key in (
        "created_at",
        "published_at",
        "reviewed_at",
        "discovered_at",
        "generated_at",
    ):
        if row.get(key):
            return str(row[key])
    return None


def _date_in_window(value: str | None, *, since: date, through: date) -> bool:
    if not value:
        return True
    try:
        parsed = date.fromisoformat(str(value).replace("Z", "+00:00")[:10])
    except ValueError:
        return True
    return since <= parsed <= through


def _looks_like_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


def _safe_select(client: SupabaseRestClient, view: str) -> list[dict[str, Any]]:
    try:
        return client.select_rows(view)
    except Exception:  # noqa: BLE001 - belief runs can degrade on optional views.
        return []


def _print_json(payload: Mapping[str, Any]) -> None:
    print(json.dumps(json_clean(payload), indent=2, default=str))


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build policy thesis updates and briefs."
    )
    parser.add_argument("--since", required=True)
    parser.add_argument("--through")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-path")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    from pci_realtime.ingest.base import parse_date

    parser = build_arg_parser()
    args = parser.parse_args(argv)
    result = run_policy_beliefs(
        since=parse_date(args.since),
        through=parse_date(args.through) if args.through else None,
        dry_run=args.dry_run,
        output_path=Path(args.output_path) if args.output_path else None,
    )
    _print_json({"run_id": result["run_id"], "counts": result["counts"]})


if __name__ == "__main__":
    main()
