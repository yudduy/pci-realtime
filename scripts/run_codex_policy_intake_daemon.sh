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

mkdir -p "$RUN_DIR"
cd "$REPO_ROOT"

if [[ -f "$REPO_ROOT/.env" ]]; then
  set -a
  source "$REPO_ROOT/.env"
  set +a
fi

SINCE_DATE="$(
  python3 - <<'PY'
from datetime import date, timedelta

print((date.today() - timedelta(days=2)).isoformat())
PY
)"

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

Expected flow:
1. Inspect \`git status --short\` and the current intake guidance in README.md or AGENT.md.
2. Run:
   \`uv run --extra dev python -m pci_realtime.pipeline.policy_discovery --since $SINCE_DATE --dry-run --output-path $DISCOVERY_PAYLOAD\`
3. If dry-run succeeds and Supabase/OpenAI writes are configured, run:
   \`uv run --extra dev python -m pci_realtime.pipeline.policy_discovery --since $SINCE_DATE\`
4. Report the commands used, whether Supabase writes were configured, row counts, source-health failures/staleness, and queued candidates needing human review.
PROMPT

if [[ "${PCI_CODEX_DAEMON_SMOKE:-}" == "1" ]]; then
  printf 'smoke ok: prompt=%s summary=%s events=%s\n' \
    "$PROMPT_FILE" "$SUMMARY_FILE" "$EVENT_LOG"
  exit 0
fi

codex --ask-for-approval never exec \
  --ephemeral \
  --json \
  --sandbox danger-full-access \
  -c shell_environment_policy.inherit=all \
  -C "$REPO_ROOT" \
  --output-last-message "$SUMMARY_FILE" \
  - <"$PROMPT_FILE" >"$EVENT_LOG" 2>&1
