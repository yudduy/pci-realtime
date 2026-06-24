#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-8510}"
HOST="${HOST:-0.0.0.0}"
REQUIRE_PRODUCTION_KEYS="${REQUIRE_PRODUCTION_KEYS:-true}"

if [[ -f .env ]]; then
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" != *=* ]] && continue
    key="${line%%=*}"
    value="${line#*=}"
    key="${key//[[:space:]]/}"
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    if [[ "$value" =~ ^\"(.*)\"$ ]]; then
      value="${BASH_REMATCH[1]}"
    elif [[ "$value" =~ ^\'(.*)\'$ ]]; then
      value="${BASH_REMATCH[1]}"
    fi
    export "$key=$value"
  done < .env
fi

DEFAULT_DATES="$(python3 - <<'PY'
from datetime import date, timedelta

today = date.today()
this_monday = today - timedelta(days=today.weekday())
start = this_monday - timedelta(days=7)
end = this_monday - timedelta(days=1)
print(f"{start.isoformat()} {end.isoformat()}")
PY
)"
DEFAULT_START_DATE="${DEFAULT_DATES%% *}"
DEFAULT_END_DATE="${DEFAULT_DATES##* }"
START_DATE="${START_DATE:-$DEFAULT_START_DATE}"
END_DATE="${END_DATE:-$DEFAULT_END_DATE}"

if [[ "$REQUIRE_PRODUCTION_KEYS" == "true" ]]; then
  for name in OPENAI_API_KEY PROPUBLICA_CONGRESS_API_KEY; do
    if [[ -z "${!name:-}" ]]; then
      echo "$name is required for the full production registry loop." >&2
      exit 1
    fi
  done
fi

if ! supabase status >/dev/null 2>&1; then
  supabase start
fi

STATUS_ENV="$(supabase status -o env 2>/dev/null || true)"
API_URL="$(printf '%s\n' "$STATUS_ENV" | awk -F= '/^API_URL=/{gsub("\"", "", $2); print $2}')"
PUBLISHABLE_KEY="$(printf '%s\n' "$STATUS_ENV" | awk -F= '/^PUBLISHABLE_KEY=/{gsub("\"", "", $2); print $2}')"
SECRET_KEY="$(printf '%s\n' "$STATUS_ENV" | awk -F= '/^SECRET_KEY=/{gsub("\"", "", $2); print $2}')"

if [[ -z "$API_URL" || -z "$PUBLISHABLE_KEY" || -z "$SECRET_KEY" ]]; then
  echo "Could not read Supabase credentials from 'supabase status -o env'." >&2
  exit 1
fi

SUPABASE_URL="$API_URL" \
SUPABASE_SERVICE_ROLE_KEY="$SECRET_KEY" \
  uv run --extra dev python -m pci_realtime.pipeline.seed_supabase

SUPABASE_URL="$API_URL" \
SUPABASE_SERVICE_ROLE_KEY="$SECRET_KEY" \
  uv run --extra dev python -m pci_realtime.pipeline.weekly_live \
    --start-date "$START_DATE" \
    --end-date "$END_DATE" \
    --confirm-cost

SUPABASE_URL="$API_URL" \
SUPABASE_PUBLISHABLE_KEY="$PUBLISHABLE_KEY" \
  npm --prefix apps/web run build

SUPABASE_URL="$API_URL" \
SUPABASE_PUBLISHABLE_KEY="$PUBLISHABLE_KEY" \
  npm --prefix apps/web run start -- --hostname "$HOST" --port "$PORT"
