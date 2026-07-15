#!/usr/bin/env bash
set -euo pipefail

PROJECT_NAME="${VERCEL_PROJECT_NAME:-pcindex}"
PRODUCTION_DOMAIN="${PRODUCTION_DOMAIN:-pcindex.vercel.app}"
SCOPE_ARGS=()
if [[ -n "${VERCEL_SCOPE:-}" ]]; then
  SCOPE_ARGS=(--scope "$VERCEL_SCOPE")
fi

if ! vercel whoami >/dev/null 2>&1; then
  echo "Vercel CLI is not authenticated. Run: vercel login" >&2
  exit 1
fi

vercel link --yes --project "$PROJECT_NAME" "${SCOPE_ARGS[@]}"
printf '{"rootDirectory":"apps/web","nodeVersion":"22.x"}' \
  | vercel api "/v9/projects/$PROJECT_NAME" \
    --method PATCH \
    --input - \
    --silent \
    "${SCOPE_ARGS[@]}"

cat >&2 <<EOF
Set these Vercel env vars from the repo root:
  SUPABASE_URL
  SUPABASE_PUBLISHABLE_KEY

Then deploy:
  vercel deploy --prod

Then make the production alias canonical:
  vercel alias set <deployment-url> $PRODUCTION_DOMAIN
EOF
