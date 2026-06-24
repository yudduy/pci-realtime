from __future__ import annotations

import argparse
import json
import os
import plistlib
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_ROOT = REPO_ROOT / "data" / "private" / "codex-daemon"
LAUNCH_AGENT_LABEL = "com.pcindex.codex-policy-intake"
LAUNCH_AGENT_PATH = (
    Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"
)
REQUIRED_KEYS = ("OPENAI_API_KEY", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY")
OPTIONAL_SOURCE_KEYS = (
    "CONGRESS_GOV_API_KEY",
    "PROPUBLICA_CONGRESS_API_KEY",
    "REGULATIONS_GOV_API_KEY",
)
PROBLEM_SOURCE_STATES = {"disabled", "failed", "stale"}


def build_status(
    *,
    repo_root: Path = REPO_ROOT,
    log_root: Path = LOG_ROOT,
    launch_agent_path: Path = LAUNCH_AGENT_PATH,
    check_launchctl: bool = True,
    include_smoke: bool = False,
) -> dict[str, Any]:
    run_dir = latest_run_dir(log_root, include_smoke=include_smoke)
    status = read_json(run_dir / "status.json") if run_dir else {}
    payload = read_json(run_dir / "policy_discovery_payload.json") if run_dir else {}
    artifacts = artifact_status(run_dir, status)
    candidates = candidate_summary(payload)
    source_health = source_health_summary(payload)
    run_row = discovery_run(payload)
    run_metadata = mapping(run_row.get("metadata"))
    return {
        "scheduler": scheduler_status(
            launch_agent_path,
            check_launchctl=check_launchctl,
        ),
        "credentials": credential_status(repo_root),
        "latest_run": {
            "run_dir": str(run_dir) if run_dir else None,
            "state": run_state(status, payload),
            "started_at": status.get("started_at"),
            "completed_at": status.get("completed_at"),
            "since_date": status.get("since_date") or run_metadata.get("window_start"),
            "through_date": run_metadata.get("window_end"),
            "pipeline_status": run_row.get("status"),
            "codex_exit_code": status.get("codex_exit_code"),
            "report_exit_code": status.get("report_exit_code"),
            "artifacts": artifacts,
        },
        "discovery": {
            "run_id": payload.get("run_id"),
            "counts": mapping(payload.get("counts")),
            "candidates": candidates,
            "source_health": source_health,
        },
    }


def render_status(status: Mapping[str, Any]) -> str:
    scheduler = mapping(status.get("scheduler"))
    credentials = mapping(status.get("credentials"))
    latest_run = mapping(status.get("latest_run"))
    discovery = mapping(status.get("discovery"))
    candidates = mapping(discovery.get("candidates"))
    source_health = mapping(discovery.get("source_health"))

    lines = [
        "# Codex Policy Intake Daemon Status",
        "",
        "## Scheduler",
        f"- LaunchAgent: {present_path(scheduler.get('path'))}",
        f"- Installed: {yes_no(scheduler.get('installed'))}",
    ]
    schedule = scheduler.get("schedule")
    if schedule:
        lines.append(f"- Schedule: {schedule}")
    if scheduler.get("launchctl_loaded") is not None:
        lines.append(f"- Loaded: {yes_no(scheduler.get('launchctl_loaded'))}")
    if scheduler.get("launchctl_state"):
        lines.append(f"- launchctl state: `{scheduler.get('launchctl_state')}`")
    if scheduler.get("launchctl_runs") is not None:
        lines.append(f"- launchctl runs: `{scheduler.get('launchctl_runs')}`")

    lines.extend(
        [
            "",
            "## Credentials",
            f"- OpenAI web search: {configured(credentials.get('OPENAI_API_KEY'))}",
            (
                "- Supabase write credentials: "
                f"{configured(credentials.get('SUPABASE_URL') and credentials.get('SUPABASE_SERVICE_ROLE_KEY'))}"
            ),
            "- Congress.gov key: "
            f"{configured(credentials.get('CONGRESS_GOV_API_KEY'))}",
            "- ProPublica Congress key: "
            f"{configured(credentials.get('PROPUBLICA_CONGRESS_API_KEY'))}",
            "- Regulations.gov key: "
            f"{configured(credentials.get('REGULATIONS_GOV_API_KEY'))}",
            "",
            "## Latest Run",
            f"- Run directory: {present_path(latest_run.get('run_dir'))}",
            f"- State: `{latest_run.get('state') or 'unknown'}`",
            f"- Since date: `{latest_run.get('since_date') or 'unknown'}`",
            f"- Through date: `{latest_run.get('through_date') or 'unknown'}`",
            f"- Pipeline status: `{latest_run.get('pipeline_status') or 'unknown'}`",
            f"- Started: `{latest_run.get('started_at') or 'unknown'}`",
            f"- Completed: `{latest_run.get('completed_at') or 'unknown'}`",
            f"- Codex exit: `{exit_label(latest_run.get('codex_exit_code'))}`",
            f"- Report exit: `{exit_label(latest_run.get('report_exit_code'))}`",
            "",
            "## Discovery",
            f"- Run ID: `{discovery.get('run_id') or 'unknown'}`",
            f"- Candidates: `{candidates.get('total', 0)}`",
            f"- Candidate states: {counter_label(candidates.get('by_review_state'))}",
            f"- Source-health rows: `{source_health.get('total', 0)}`",
            f"- Source-health states: {counter_label(source_health.get('by_status'))}",
        ]
    )

    problem_sources = list(source_health.get("problem_sources") or [])
    if problem_sources:
        lines.extend(["", "## Source Gaps"])
        for row in problem_sources:
            row_map = mapping(row)
            summary = row_map.get("last_error_summary")
            suffix = f" - {summary}" if summary else ""
            lines.append(
                f"- `{row_map.get('source')}`: `{row_map.get('status')}`{suffix}"
            )

    latest_candidates = list(candidates.get("latest") or [])
    if latest_candidates:
        lines.extend(["", "## Latest Candidates"])
        for row in latest_candidates:
            row_map = mapping(row)
            url = row_map.get("canonical_url") or row_map.get("resolved_primary_url")
            suffix = f" ({url})" if url else ""
            lines.append(
                "- "
                f"`{row_map.get('review_state') or 'unknown'}` / "
                f"`{row_map.get('promotability') or 'unknown'}`: "
                f"{row_map.get('provision') or 'unknown'} - "
                f"{row_map.get('title') or 'Untitled source'}{suffix}"
            )

    artifacts = mapping(latest_run.get("artifacts"))
    if artifacts:
        lines.extend(["", "## Artifacts"])
        for name, value in artifacts.items():
            artifact = mapping(value)
            lines.append(
                f"- `{name}`: {present_path(artifact.get('path'))} "
                f"({artifact.get('status')})"
            )

    return "\n".join(lines).rstrip() + "\n"


def latest_run_dir(log_root: Path, *, include_smoke: bool = False) -> Path | None:
    if not log_root.exists():
        return None
    dirs = [path for path in log_root.iterdir() if path.is_dir()]
    if not dirs:
        return None
    candidates = (
        dirs if include_smoke else [path for path in dirs if is_operator_run(path)]
    )
    if not candidates:
        candidates = dirs
    return max(candidates, key=lambda path: (path.name, path.stat().st_mtime))


def is_operator_run(run_dir: Path) -> bool:
    return not is_smoke_run(run_dir) and (
        (run_dir / "status.json").exists()
        or (run_dir / "policy_discovery_payload.json").exists()
        or (run_dir / "summary.md").exists()
        or (run_dir / "events.jsonl").exists()
    )


def is_smoke_run(run_dir: Path) -> bool:
    return read_json(run_dir / "status.json").get("state") == "smoke"


def run_state(status: Mapping[str, Any], payload: Mapping[str, Any]) -> str:
    explicit = status.get("state")
    if explicit:
        return str(explicit)
    if payload.get("run_id") or rows_for(payload, "pipeline_runs"):
        return "completed_legacy"
    return "unknown"


def discovery_run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    runs = rows_for(payload, "pipeline_runs")
    return runs[0] if runs else {}


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as fh:
            value = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def artifact_status(run_dir: Path | None, status: Mapping[str, Any]) -> dict[str, Any]:
    if not run_dir:
        return {}
    configured = mapping(status.get("artifacts"))
    defaults = {
        "prompt": run_dir / "prompt.md",
        "summary": run_dir / "summary.md",
        "events": run_dir / "events.jsonl",
        "policy_discovery_payload": run_dir / "policy_discovery_payload.json",
        "policy_intake_report": run_dir / "policy_intake_report.md",
        "status": run_dir / "status.json",
    }
    artifacts: dict[str, Any] = {}
    for name, default_path in defaults.items():
        path = Path(str(configured.get(name) or default_path))
        exists = path.exists()
        artifacts[name] = {
            "path": str(path),
            "status": "present" if exists else "missing",
            "bytes": path.stat().st_size if exists else 0,
        }
    return artifacts


def candidate_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    rows = rows_for(payload, "policy_source_candidates")
    sorted_rows = sorted(rows, key=candidate_sort_key)
    return {
        "total": len(rows),
        "by_review_state": dict(
            Counter(str(row.get("review_state") or "unknown") for row in rows)
        ),
        "by_promotability": dict(
            Counter(str(row.get("promotability") or "unknown") for row in rows)
        ),
        "latest": [
            {
                "candidate_id": row.get("candidate_id"),
                "provision": row.get("provision"),
                "review_state": row.get("review_state"),
                "promotability": row.get("promotability"),
                "title": row.get("title"),
                "canonical_url": row.get("canonical_url"),
                "resolved_primary_url": row.get("resolved_primary_url"),
            }
            for row in sorted_rows[:5]
        ],
    }


def source_health_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    rows = rows_for(payload, "source_health")
    problem_sources = [
        {
            "source": row.get("source"),
            "status": row.get("status"),
            "last_error_class": row.get("last_error_class"),
            "last_error_summary": row.get("last_error_summary"),
        }
        for row in rows
        if row.get("status") in PROBLEM_SOURCE_STATES
    ]
    return {
        "total": len(rows),
        "by_status": dict(Counter(str(row.get("status") or "unknown") for row in rows)),
        "problem_sources": sorted(
            problem_sources,
            key=lambda row: str(row.get("source") or ""),
        ),
    }


def rows_for(payload: Mapping[str, Any], table: str) -> list[Mapping[str, Any]]:
    rows = mapping(payload.get("rows")).get(table)
    return (
        [row for row in rows if isinstance(row, Mapping)]
        if isinstance(rows, list)
        else []
    )


def candidate_sort_key(row: Mapping[str, Any]) -> tuple[int, str]:
    state_order = {
        "queued": 0,
        "needs_primary_source": 1,
        "duplicate": 2,
        "approved": 3,
        "rejected": 4,
    }
    return (
        state_order.get(str(row.get("review_state") or ""), 99),
        str(row.get("discovered_at") or row.get("published_at") or ""),
    )


def credential_status(repo_root: Path) -> dict[str, bool]:
    env = dotenv_values(repo_root / ".env")
    values = {**env, **os.environ}
    return {
        key: bool(values.get(key)) for key in (*REQUIRED_KEYS, *OPTIONAL_SOURCE_KEYS)
    }


def dotenv_values(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key:
            values[key] = value
    return values


def scheduler_status(
    launch_agent_path: Path,
    *,
    check_launchctl: bool,
) -> dict[str, Any]:
    installed = launch_agent_path.exists()
    status: dict[str, Any] = {
        "path": str(launch_agent_path),
        "installed": installed,
        "schedule": None,
        "launchctl_loaded": None,
        "launchctl_state": None,
        "launchctl_runs": None,
    }
    if installed:
        status["schedule"] = launch_agent_schedule(launch_agent_path)
    if installed and check_launchctl:
        status.update(launchctl_status())
    return status


def launch_agent_schedule(path: Path) -> str | None:
    try:
        with path.open("rb") as fh:
            payload = plistlib.load(fh)
    except (OSError, plistlib.InvalidFileException):
        return None
    interval = payload.get("StartCalendarInterval")
    if isinstance(interval, Mapping):
        hour = interval.get("Hour")
        minute = interval.get("Minute")
        if isinstance(hour, int) and isinstance(minute, int):
            return f"daily {hour:02d}:{minute:02d}"
    return None


def launchctl_status() -> dict[str, Any]:
    try:
        result = subprocess.run(
            ["launchctl", "print", f"gui/{os.getuid()}/{LAUNCH_AGENT_LABEL}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"launchctl_loaded": False}
    if result.returncode != 0:
        return {"launchctl_loaded": False}
    output = result.stdout
    return {
        "launchctl_loaded": True,
        "launchctl_state": regex_group(output, r"state = ([^\n]+)"),
        "launchctl_runs": int(value)
        if (value := regex_group(output, r"runs = (\d+)"))
        else None,
    }


def regex_group(value: str, pattern: str) -> str | None:
    match = re.search(pattern, value)
    return match.group(1).strip() if match else None


def mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def configured(value: Any) -> str:
    return "configured" if bool(value) else "missing"


def yes_no(value: Any) -> str:
    return "yes" if bool(value) else "no"


def exit_label(value: Any) -> str:
    return "unknown" if value is None else str(value)


def counter_label(value: Any) -> str:
    counter = mapping(value)
    if not counter:
        return "`none`"
    return ", ".join(f"`{key}`={counter[key]}" for key in sorted(counter))


def present_path(value: Any) -> str:
    return f"`{value}`" if value else "`none`"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Report read-only status for the local Codex policy-intake daemon."
    )
    parser.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON."
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--log-root", type=Path, default=LOG_ROOT)
    parser.add_argument("--launch-agent-path", type=Path, default=LAUNCH_AGENT_PATH)
    parser.add_argument(
        "--no-launchctl",
        action="store_true",
        help="Skip launchctl inspection and only read the LaunchAgent plist.",
    )
    parser.add_argument(
        "--include-smoke",
        action="store_true",
        help="Allow smoke-test run directories to count as the latest run.",
    )
    args = parser.parse_args()
    status = build_status(
        repo_root=args.repo_root,
        log_root=args.log_root,
        launch_agent_path=args.launch_agent_path,
        check_launchctl=not args.no_launchctl,
        include_smoke=args.include_smoke,
    )
    if args.json:
        print(json.dumps(status, indent=2, sort_keys=True))
    else:
        print(render_status(status), end="")


if __name__ == "__main__":
    main()
