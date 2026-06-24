#!/usr/bin/env zsh
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"

SCRIPT_DIR="${0:A:h}"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_ROOT="$REPO_ROOT/data/private/codex-daemon"
RUN_TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="$LOG_ROOT/$RUN_TS"
PROMPT_FILE="$RUN_DIR/prompt.md"
SUMMARY_FILE="$RUN_DIR/summary.md"
EVENT_LOG="$RUN_DIR/events.jsonl"
DISCOVERY_PAYLOAD="$RUN_DIR/policy_discovery_payload.json"
REPORT_FILE="$RUN_DIR/policy_intake_report.md"
STATUS_FILE="$RUN_DIR/status.json"

mkdir -p "$RUN_DIR"
cd "$REPO_ROOT"

if [[ -f "$REPO_ROOT/.env" ]]; then
  set -a
  source "$REPO_ROOT/.env"
  set +a
fi

SINCE_DAYS="${PCI_CODEX_DAEMON_SINCE_DAYS:-2}"
SINCE_DATE="${PCI_CODEX_DAEMON_SINCE_DATE:-$(
  PCI_CODEX_DAEMON_SINCE_DAYS="$SINCE_DAYS" python3 - <<'PY'
import os
from datetime import date, timedelta

days = int(os.environ["PCI_CODEX_DAEMON_SINCE_DAYS"])
print((date.today() - timedelta(days=days)).isoformat())
PY
)}"

cat >"$PROMPT_FILE" <<PROMPT
Run the PCI policy-intelligence intake sweep.

Operational constraints:
- Do not edit repository files.
- Do not stage, commit, push, approve, reject, or promote candidates.
- Do not write forecasts, trade proposals, market-edge data, or ledger evidence.
- Writes are allowed only through the existing policy_discovery path, and only to append pipeline_runs, source_health, and queued policy_source_candidates.
- If required credentials or migrations are missing, stop after dry-run and report the blocker.

Use this date window:
- since: $SINCE_DATE

Use this dry-run output path:
- $DISCOVERY_PAYLOAD

Use this staff report output path:
- $REPORT_FILE

Expected flow:
1. Inspect \`git status --short\` and the current intake guidance in README.md or AGENT.md.
2. Run:
   \`uv run --extra dev python -m pci_realtime.pipeline.policy_discovery --since $SINCE_DATE --dry-run --output-path $DISCOVERY_PAYLOAD\`
3. Render the staff-facing intake report:
   \`uv run --extra dev python scripts/render_policy_intake_report.py --payload $DISCOVERY_PAYLOAD --output-path $REPORT_FILE\`
4. If dry-run succeeds and Supabase/OpenAI writes are configured, run:
   \`uv run --extra dev python -m pci_realtime.pipeline.policy_discovery --since $SINCE_DATE\`
5. Report real intake details, not just counts: concrete titles, URLs, claims, source quotes, source-health failures/staleness, disabled sources, and review actions.
PROMPT

export RUN_TS RUN_DIR SINCE_DATE PROMPT_FILE SUMMARY_FILE EVENT_LOG DISCOVERY_PAYLOAD REPORT_FILE STATUS_FILE
python3 - <<'PY'
import json
import os
from datetime import datetime, timezone

status_path = os.environ["STATUS_FILE"]
payload = {
    "state": "started",
    "started_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "run_timestamp": os.environ["RUN_TS"],
    "run_dir": os.environ["RUN_DIR"],
    "since_date": os.environ["SINCE_DATE"],
    "artifacts": {
        "prompt": os.environ["PROMPT_FILE"],
        "summary": os.environ["SUMMARY_FILE"],
        "events": os.environ["EVENT_LOG"],
        "policy_discovery_payload": os.environ["DISCOVERY_PAYLOAD"],
        "policy_intake_report": os.environ["REPORT_FILE"],
    },
}
with open(status_path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, indent=2, sort_keys=True)
    fh.write("\n")
PY

if [[ "${PCI_CODEX_DAEMON_SMOKE:-}" == "1" ]]; then
  python3 - <<'PY'
import json
import os
from datetime import datetime, timezone

status_path = os.environ["STATUS_FILE"]
with open(status_path, encoding="utf-8") as fh:
    payload = json.load(fh)
payload.update(
    {
        "state": "smoke",
        "completed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "codex_exit_code": 0,
        "report_exit_code": None,
    }
)
with open(status_path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, indent=2, sort_keys=True)
    fh.write("\n")
PY
  printf 'smoke ok: prompt=%s summary=%s events=%s report=%s\n' \
    "$PROMPT_FILE" "$SUMMARY_FILE" "$EVENT_LOG" "$REPORT_FILE"
  exit 0
fi

set +e
codex --ask-for-approval never exec \
  --ephemeral \
  --json \
  --sandbox danger-full-access \
  -c shell_environment_policy.inherit=all \
  -C "$REPO_ROOT" \
  --output-last-message "$SUMMARY_FILE" \
  - <"$PROMPT_FILE" >"$EVENT_LOG" 2>&1
CODEX_STATUS=$?
set -e

REPORT_STATUS=""
if [[ -f "$DISCOVERY_PAYLOAD" ]]; then
  if uv run --extra dev python scripts/render_policy_intake_report.py \
    --payload "$DISCOVERY_PAYLOAD" \
    --output-path "$REPORT_FILE"; then
    REPORT_STATUS=0
    {
      printf '\n\n## Deterministic Staff Intake Report\n\n'
      cat "$REPORT_FILE"
    } >>"$SUMMARY_FILE"
  else
    REPORT_STATUS=1
  fi
fi

export CODEX_STATUS REPORT_STATUS
python3 - <<'PY'
import json
import os
from datetime import datetime, timezone

status_path = os.environ["STATUS_FILE"]
with open(status_path, encoding="utf-8") as fh:
    payload = json.load(fh)
report_status = os.environ.get("REPORT_STATUS")
payload.update(
    {
        "state": "completed" if os.environ["CODEX_STATUS"] == "0" else "failed",
        "completed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "codex_exit_code": int(os.environ["CODEX_STATUS"]),
        "report_exit_code": int(report_status) if report_status else None,
    }
)
with open(status_path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, indent=2, sort_keys=True)
    fh.write("\n")
PY

exit "$CODEX_STATUS"
