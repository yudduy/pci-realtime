from __future__ import annotations

import argparse
import os

from pci_realtime.registry.evidence import source_health_row, utc_now_iso
from pci_realtime.registry.store import SupabaseRestClient


RUN_TYPES = {"weekly": "weekly", "daily": "daily_refresh"}


def report_failure(run_type: str, *, client: SupabaseRestClient | None = None) -> None:
    client = client or SupabaseRestClient.from_env()
    if client is None:
        print("skipped: no supabase credentials")
        return

    now = utc_now_iso()
    server_url = os.environ.get("GITHUB_SERVER_URL")
    repository = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID")
    run_url = (
        f"{server_url.rstrip('/')}/{repository}/actions/runs/{run_id}"
        if server_url and repository and run_id
        else None
    )
    pipeline_run = {
        "run_type": RUN_TYPES[run_type],
        "status": "failed",
        "source": "github-actions",
        "completed_at": now,
        "metadata": {
            "github_run_id": os.environ.get("GITHUB_RUN_ID"),
            "github_run_url": run_url,
        },
    }
    health = source_health_row(
        source="pipeline",
        status="failed",
        last_attempt_at=now,
        error_class="GitHubActionsFailure",
        error_summary=run_url,
        details={"notes": run_url},
    )

    errors = []
    try:
        client.insert_rows("pipeline_runs", [pipeline_run])
    except Exception as exc:  # noqa: BLE001 - this reporter must fail open.
        errors.append(f"pipeline_runs: {exc}")
    try:
        client.upsert_rows("source_health", [health], on_conflict="source")
    except Exception as exc:  # noqa: BLE001 - this reporter must fail open.
        errors.append(f"source_health: {exc}")

    if errors:
        print(f"warning: failure report incomplete ({'; '.join(errors)})")
    else:
        print(f"recorded pipeline failure: {run_url or 'GitHub Actions run'}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Record a GitHub Actions failure.")
    parser.add_argument("--run-type", required=True, choices=RUN_TYPES)
    args = parser.parse_args()
    try:
        report_failure(args.run_type)
    except Exception as exc:  # noqa: BLE001 - never mask the pipeline failure.
        print(f"warning: failure reporter skipped ({exc})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
