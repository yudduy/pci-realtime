#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-8510}"
HOST="${HOST:-0.0.0.0}"

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
    --start-date 2025-06-02 \
    --end-date 2025-06-08 \
    --skip-ingest \
    --skip-score \
    --fetch-markets

SUPABASE_URL="$API_URL" \
SUPABASE_PUBLISHABLE_KEY="$PUBLISHABLE_KEY" \
  npm --prefix apps/web run build

SUPABASE_URL="$API_URL" \
SUPABASE_PUBLISHABLE_KEY="$PUBLISHABLE_KEY" \
  npm --prefix apps/web run start -- --hostname "$HOST" --port "$PORT"
