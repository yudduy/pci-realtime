#!/usr/bin/env bash
set -euo pipefail

PROJECT_NAME="${SUPABASE_PROJECT_NAME:-pci-realtime}"
REGION="${SUPABASE_REGION:-us-west-1}"

if ! supabase projects list >/dev/null 2>&1; then
  echo "Supabase CLI is not authenticated. Run: supabase login" >&2
  exit 1
fi

if [[ -z "${SUPABASE_PROJECT_REF:-}" ]]; then
  if [[ -z "${SUPABASE_ORG_ID:-}" || -z "${SUPABASE_DB_PASSWORD:-}" ]]; then
    cat >&2 <<'EOF'
Set SUPABASE_PROJECT_REF to link an existing project, or set both:
  SUPABASE_ORG_ID
  SUPABASE_DB_PASSWORD

Then rerun this script.
EOF
    exit 1
  fi
  supabase projects create "$PROJECT_NAME" \
    --org-id "$SUPABASE_ORG_ID" \
    --db-password "$SUPABASE_DB_PASSWORD" \
    --region "$REGION"
  echo "Set SUPABASE_PROJECT_REF to the new project ref, then rerun." >&2
  exit 0
fi

supabase link --project-ref "$SUPABASE_PROJECT_REF"
supabase db push
supabase functions deploy trigger-weekly-pipeline
supabase functions deploy trigger-daily-refresh

cat >&2 <<'EOF'
Set pipeline secrets next:
  supabase secrets set PYTHON_PIPELINE_WEBHOOK_URL=...
  supabase secrets set PYTHON_PIPELINE_WEBHOOK_SECRET=...
EOF
