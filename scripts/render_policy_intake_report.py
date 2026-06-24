from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


REVIEW_ORDER = {
    "queued": 0,
    "needs_primary_source": 1,
    "duplicate": 2,
    "approved": 3,
    "rejected": 4,
}


def render_report(payload: Mapping[str, Any], *, max_candidates: int = 20) -> str:
    rows = _mapping(payload.get("rows"))
    counts = _mapping(payload.get("counts"))
    pipeline_runs = _list(rows.get("pipeline_runs"))
    candidates = sorted(
        _list(rows.get("policy_source_candidates")),
        key=_candidate_sort_key,
    )
    source_health = sorted(_list(rows.get("source_health")), key=_source_sort_key)
    run = _mapping(pipeline_runs[0]) if pipeline_runs else {}
    metadata = _mapping(run.get("metadata"))
    window_start = metadata.get("window_start") or "unknown"
    window_end = metadata.get("window_end") or "unknown"
    run_id = payload.get("run_id") or run.get("run_id") or "unknown"

    lines = [
        "# Policy Intake Report",
        "",
        f"- Run ID: `{run_id}`",
        f"- Window: `{window_start}` through `{window_end}`",
        f"- Pipeline rows: `{counts.get('pipeline_runs', 0)}`",
        f"- Source candidates: `{counts.get('policy_source_candidates', 0)}`",
        f"- Source-health rows: `{counts.get('source_health', 0)}`",
        "- Report basis: `policy_discovery` payload; live Supabase upsert may reconcile candidates as duplicates.",
        "",
    ]
    lines.extend(_render_candidates(candidates[:max_candidates]))
    lines.extend(_render_source_health(source_health))
    lines.extend(_render_notes(source_health))
    return "\n".join(lines).rstrip() + "\n"


def _render_candidates(candidates: Sequence[Mapping[str, Any]]) -> list[str]:
    lines = ["## What Surfaced", ""]
    if not candidates:
        lines.extend(
            [
                "No policy source candidates surfaced in this run.",
                "",
                "Action: keep watching source health and rerun on the next schedule.",
                "",
            ]
        )
        return lines

    for candidate in candidates:
        provision = candidate.get("provision") or "unknown"
        title = _clean(candidate.get("title") or "Untitled source")
        source_name = _clean(candidate.get("source_name") or "unknown source")
        source_class = candidate.get("source_class") or "unknown"
        review_state = candidate.get("review_state") or "unknown"
        promotability = candidate.get("promotability") or "unknown"
        confidence = candidate.get("confidence")
        published_at = candidate.get("published_at") or "unknown date"
        url = (
            candidate.get("canonical_url")
            or candidate.get("resolved_primary_url")
            or ""
        )
        claim = _clean(candidate.get("claim") or "")
        quote = _clean(candidate.get("citation_quote") or "")
        relevance = _clean(candidate.get("decision_relevance") or "")
        why = _clean(candidate.get("why_it_matters") or "")

        lines.extend(
            [
                f"### {provision}: {title}",
                "",
                f"- Review state: `{review_state}`",
                f"- Promotability: `{promotability}`",
                f"- Source: {source_name} (`{source_class}`), published `{published_at}`",
            ]
        )
        if confidence is not None:
            lines.append(f"- Confidence: `{confidence}`")
        if url:
            lines.append(f"- URL: {url}")
        if claim:
            lines.append(f"- Claim: {claim}")
        if quote:
            lines.append(f'- Source proof: "{_truncate(quote, 500)}"')
        if relevance:
            lines.append(f"- Policy-design read: {relevance}")
        if why:
            lines.append(f"- Why it matters: {why}")
        lines.append(f"- Action: {_candidate_action(candidate)}")
        lines.append("")
    return lines


def _render_source_health(source_health: Sequence[Mapping[str, Any]]) -> list[str]:
    lines = ["## Source Health", ""]
    if not source_health:
        lines.extend(["No source-health rows were produced.", ""])
        return lines

    problem_rows = [
        row
        for row in source_health
        if row.get("status") in {"disabled", "failed", "stale"}
    ]
    success_rows = [row for row in source_health if row.get("status") == "success"]

    if success_rows:
        lines.append("Fresh or reachable sources:")
        for row in success_rows:
            source = row.get("source") or "unknown"
            count = row.get("row_count", 0)
            success_at = row.get("last_success_at") or row.get("last_attempt_at") or ""
            lines.append(
                f"- `{source}`: success, `{count}` rows, last success `{success_at}`"
            )
        lines.append("")

    if problem_rows:
        lines.append("Gaps and blockers:")
        for row in problem_rows:
            source = row.get("source") or "unknown"
            status = row.get("status") or "unknown"
            error_class = row.get("last_error_class") or "no_error_class"
            summary = _clean(row.get("last_error_summary") or "")
            detail = f": {summary}" if summary else ""
            lines.append(f"- `{source}`: `{status}` / `{error_class}`{detail}")
        lines.append("")
    return lines


def _render_notes(source_health: Sequence[Mapping[str, Any]]) -> list[str]:
    notes: list[str] = []
    for row in source_health:
        details = _mapping(row.get("details"))
        for note in _list(details.get("notes")):
            if isinstance(note, str) and note.strip():
                notes.append(note.strip())
    if not notes:
        return []
    lines = ["## Watch Items", ""]
    for note in notes:
        lines.append(f"- {_clean(note)}")
    lines.append("")
    return lines


def _candidate_action(candidate: Mapping[str, Any]) -> str:
    state = candidate.get("review_state")
    promotability = candidate.get("promotability")
    if state == "queued" and promotability == "ledger_candidate":
        return "review quote against the primary source, then promote only if verification passes."
    if state == "queued":
        return (
            "review as context; do not promote into the ledger without a primary quote."
        )
    if state == "needs_primary_source":
        return "find or attach the official primary source before any promotion."
    if state == "duplicate":
        return "no new review item; compare against the existing candidate only if the prior record looks stale."
    if state == "approved":
        return "already reviewed; keep as approved context unless a reviewer promotes separately."
    if state == "rejected":
        return "no action unless a reviewer reopens it."
    return "triage manually."


def _candidate_sort_key(candidate: Mapping[str, Any]) -> tuple[int, str, str]:
    return (
        REVIEW_ORDER.get(str(candidate.get("review_state")), 99),
        str(candidate.get("provision") or ""),
        str(candidate.get("title") or ""),
    )


def _source_sort_key(row: Mapping[str, Any]) -> tuple[int, str]:
    status = row.get("status")
    priority = 0 if status in {"failed", "disabled", "stale"} else 1
    return priority, str(row.get("source") or "")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _clean(value: Any) -> str:
    return " ".join(str(value).split())


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "..."


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render a staff-facing policy intake report from a discovery payload."
    )
    parser.add_argument("--payload", required=True)
    parser.add_argument("--output-path")
    parser.add_argument("--max-candidates", type=int, default=20)
    args = parser.parse_args()

    payload = json.loads(Path(args.payload).read_text())
    report = render_report(payload, max_candidates=args.max_candidates)
    if args.output_path:
        Path(args.output_path).write_text(report)
    else:
        print(report, end="")


if __name__ == "__main__":
    main()
