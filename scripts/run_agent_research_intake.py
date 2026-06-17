from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from pci_realtime import service
from pci_realtime.agent_research import (
    DEFAULT_AGENT_RESEARCH_MODEL,
    OFFICIAL_SOURCE_DOMAINS,
    candidate_to_submission,
    research_evidence_with_web_search,
    research_result_payload,
)
from pci_realtime.config import TRACKED_PROVISIONS
from pci_realtime.env import load_local_env
from pci_realtime.service_errors import ServiceError, SupabaseUnavailable


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def default_since() -> date:
    return date.today() - timedelta(days=14)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Use OpenAI web search to collect official PCIndex evidence and "
            "optionally submit it through governed Agent COI intake."
        )
    )
    parser.add_argument("--since", type=parse_date, default=default_since())
    parser.add_argument(
        "--provision",
        action="append",
        choices=TRACKED_PROVISIONS,
        help="Tracked provision to research. Repeatable; defaults to all.",
    )
    parser.add_argument(
        "--max-candidates-per-provision",
        type=int,
        default=2,
    )
    parser.add_argument("--model", default=DEFAULT_AGENT_RESEARCH_MODEL)
    parser.add_argument(
        "--allowed-domain",
        action="append",
        help="Official source domain allowed for web search. Repeatable.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Submit accepted candidates through Agent COI intake.",
    )
    parser.add_argument("--output-path")
    return parser


def main() -> None:
    load_local_env()
    args = build_parser().parse_args()
    provisions = tuple(args.provision or TRACKED_PROVISIONS)
    domains = tuple(args.allowed_domain or OFFICIAL_SOURCE_DOMAINS)
    result = research_evidence_with_web_search(
        since=args.since,
        provisions=provisions,
        max_candidates_per_provision=args.max_candidates_per_provision,
        model=args.model,
        allowed_domains=domains,
    )
    payload: dict[str, Any] = {
        "mode": "write" if args.write else "dry_run",
        "research": research_result_payload(result),
        "submissions": [],
    }

    if args.write:
        status = service.status()
        if not status.get("write_configured"):
            raise SupabaseUnavailable(
                "Agent COI writes are not configured. Apply "
                "supabase/migrations/005_agent_evidence_intake.sql, then rerun."
            )
        for candidate in result.candidates:
            submission = candidate_to_submission(candidate)
            try:
                payload["submissions"].append(
                    service.submit_policy_evidence(
                        **submission,
                        agent_name="pcindex-agent-research",
                        question=(
                            "What official policy evidence has changed since "
                            f"{args.since.isoformat()}?"
                        ),
                    )
                )
            except ServiceError as exc:
                payload["submissions"].append(
                    {
                        "status": "error",
                        "provision": candidate.provision,
                        "url": candidate.url,
                        "error": {"code": exc.code, "message": exc.message},
                    }
                )

    text = json.dumps(payload, indent=2, default=str)
    if args.output_path:
        path = Path(args.output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
