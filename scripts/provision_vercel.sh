#!/usr/bin/env bash
set -euo pipefail

PROJECT_NAME="${VERCEL_PROJECT_NAME:-pci-forecast-registry}"
SCOPE_ARGS=()
if [[ -n "${VERCEL_SCOPE:-}" ]]; then
  SCOPE_ARGS=(--scope "$VERCEL_SCOPE")
fi

if ! vercel whoami >/dev/null 2>&1; then
  echo "Vercel CLI is not authenticated. Run: vercel login" >&2
  exit 1
fi

vercel link --cwd apps/web --yes --project "$PROJECT_NAME" "${SCOPE_ARGS[@]}"

cat >&2 <<'EOF'
Set these Vercel env vars with `vercel env add --cwd apps/web`:
  SUPABASE_URL
  SUPABASE_PUBLISHABLE_KEY

Then deploy:
  vercel deploy --cwd apps/web --prod
EOF
