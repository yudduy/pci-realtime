# Policy Credibility Registry

Supabase-backed registry for the Policy Credibility Index (PCI) from the IRA venture-capital research project. The system turns official federal policy documents into weekly PCI updates, matches those updates to clean public prediction markets, and records forecasts, gated trade proposals, and resolved outcomes.

The public web app is a research companion and read-only registry surface. It does not place orders, invent forecasts, or expose private execution payloads.

## Product Loop

```text
official policy documents
  -> provision relevance filter
  -> PCI delta scoring
  -> weekly PCI series
  -> outcome tracking
```

`weekly_live` owns the full weekly path: ingest official sources, score PCI deltas, build PCI, and publish cited ledger rows. `daily_refresh` refreshes public context sources, source documents, evidence, and source-health rows.

Trading stays backend-only. Live execution is disabled unless `PCI_ENABLE_LIVE_TRADING=true`, Kalshi credentials are present, and a proposal id appears in an approval file.

## Research Context

The companion paper defines PCI as institutional design quality, scored from 1 to 5 across three dimensions:

| Dimension | High Score Means |
|---|---|
| Specificity | Eligibility rules are clear and reduce discretion |
| Durability | The commitment survives across the investment horizon |
| Enforceability | Implementation has an assigned agency process |

The baseline PCI snapshot starts at IRA enactment on 2022-08-16:

| Code | Provision | Baseline PCI |
|---|---|---:|
| `45X` | Factory production credits | 4.67 |
| `45V` | Clean hydrogen credits | 4.33 |
| `45Q` | Carbon capture credits | 4.33 |
| `30D` | EV purchase credits | 4.00 |
| `50144` | Energy reinvestment loans | 3.33 |
| `50141` | Loan office funding | 3.00 |

The OBBBA stress snapshot used by the paper is encoded as provision-level anchors in the registry seed data.

## PCI Method

Each relevant official document can change specificity, durability, and enforceability by dimension-level deltas in `[-2, +2]`. The weekly index is sticky unless a scored document changes it:

```text
PCI[p, t] = clip(
  PCI[p, t-1] + sum_doc((specificity_delta + durability_delta + enforceability_delta) / 3),
  1.0,
  5.0
)
```

PCI is not investor sentiment and not a news index. General news scraping is intentionally out of scope for index updates. Public market data is read only for market matching and outcome tracking; trading remains backend-gated.

## Repository Layout

```text
pci-realtime/
├── README.md
├── LICENSE
├── pyproject.toml
├── uv.lock
├── src/pci_realtime/
│   ├── config.py
│   ├── ingest/
│   ├── filter/
│   ├── scoring/
│   ├── pci/
│   ├── registry/
│   └── pipeline/
├── apps/web/
├── supabase/
├── scripts/
├── tests/
└── data/
    ├── baseline/
    └── fixtures/
```

`data/raw`, `data/processed`, `data/cache`, `data/private`, `data/debug`, and generated web build outputs are ignored runtime state.

## Setup

```bash
pip install -e ".[dev]"
npm --prefix apps/web ci
cp .env.example .env
```

Fill in the API keys and registry values needed for the command you plan to run. Federal Register, Treasury, IRS, OMB, RegInfo, USAspending, EIA demo reads, and CourtListener public search can run without paid vendors. Congress uses `CONGRESS_GOV_API_KEY` first and `PROPUBLICA_CONGRESS_API_KEY` only as a fallback. Regulations.gov and FRED require their own free API keys.

Run the backend tests and linters:

```bash
uv run --extra dev pytest -q
uv run --extra dev ruff check src/pci_realtime tests
uv run --extra dev ruff format --check src/pci_realtime tests
```

Run the web checks:

```bash
npm --prefix apps/web run typecheck
npm --prefix apps/web run lint
npm --prefix apps/web run test:e2e
```

## Registry Commands

Seed Supabase with the paper anchors:

```bash
python -m pci_realtime.pipeline.seed_supabase --dry-run
python -m pci_realtime.pipeline.seed_supabase
```

Run the weekly registry loop with official source ingest, LLM scoring, PCI updates, cited evidence, and Supabase writes:

```bash
python -m pci_realtime.pipeline.weekly_live \
  --start-date 2026-05-18 \
  --end-date 2026-05-24 \
  --confirm-cost
```

Refresh public context and source-health rows in Supabase:

```bash
python -m pci_realtime.pipeline.daily_refresh
```

## Agent MCP Evidence Intake

The public web app serves a human setup page at `/connect`, a hosted read-only
MCP endpoint at `/mcp`, and an agent documentation index at `/llms.txt`.

The JSON fixture in `data/fixtures/agent_evidence_seed.json` is only a bootstrap
seed. The intended live path is for a research agent to call the PCIndex MCP
server, submit a public citation, and let the service dedupe, score, trace, and
write the registry rows.

### Hosted read-only MCP (no setup)

The hosted endpoint exposes read-only tools (`status`, `list_policies`,
`current_pci`, `policy_dossier`, `get_evidence_trace`). Add it in one line:

```bash
# Claude Code
claude mcp add -s user -t http pcindex https://pcindex.vercel.app/mcp
# Codex CLI
codex mcp add pcindex --url https://pcindex.vercel.app/mcp
```

Generic hosted config:

```json
{ "mcpServers": { "pcindex": { "serverUrl": "https://pcindex.vercel.app/mcp" } } }
```

### Local write-capable MCP (trusted operators)

Hosted `/mcp` exposes read-only tools for status, policy lists, current PCI,
dossiers, and evidence traces. Before using local MCP writes, apply
`supabase/migrations/005_agent_evidence_intake.sql` to the hosted Supabase
project. The write tools require server-side credentials:

```bash
export SUPABASE_URL="https://<project>.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="<service-role-key>"
export OPENAI_API_KEY="<scoring-key>"
```

If migration `005` has not been applied yet, use
`scripts/provision_agent_evidence.py --core-registry` only as a temporary
compatibility bridge. It writes the public registry rows but does not preserve
the governed `agent_runs` and `evidence_submissions` audit trail.

Run the MCP server over stdio:

```bash
uv run --extra dev python -m pci_realtime.mcp_server
```

Example MCP client configuration:

```json
{
  "mcpServers": {
    "pcindex": {
      "command": "uv",
      "args": ["run", "--extra", "dev", "python", "-m", "pci_realtime.mcp_server"],
      "cwd": "/path/to/pci-realtime",
      "env": {
        "SUPABASE_URL": "${SUPABASE_URL}",
        "SUPABASE_SERVICE_ROLE_KEY": "${SUPABASE_SERVICE_ROLE_KEY}",
        "OPENAI_API_KEY": "${OPENAI_API_KEY}"
      }
    }
  }
}
```

Local stdio is the default transport. For a hosted or internal HTTP deployment,
run the same server with Streamable HTTP:

```bash
PCINDEX_MCP_TRANSPORT=streamable-http \
PCINDEX_MCP_MOUNT_PATH=/mcp \
uv run --extra dev python -m pci_realtime.mcp_server
```

Expected agent loop:

1. Call `status` and stop if `write_configured` is false.
2. Call `list_policies` and map evidence only to the six tracked codes.
3. Search official sources, then call `submit_policy_evidence` with a public URL,
   source title, short quote anchor, claim, and deterministic idempotency key.
4. Call `get_evidence_trace` to verify the evidence, source link, and event row.
5. Call `policy_dossier` or `current_pci` to confirm the score surface updated.

Example tool payload:

```json
{
  "provision": "45V",
  "source": {
    "url": "https://www.irs.gov/credits-deductions/clean-hydrogen-production-credit",
    "title": "Clean hydrogen production credit",
    "source_name": "Internal Revenue Service",
    "published_at": "2025-12-31"
  },
  "citation": {
    "quote": "provides a production credit for each kilogram of qualified clean hydrogen",
    "section": "Overview"
  },
  "claim": "IRS current guidance confirms the section 45V credit remains tied to qualified clean hydrogen production, emissions intensity, and wage/apprenticeship compliance.",
  "idempotency_key": "irs-clean-hydrogen-credit-page-2025-12-31",
  "agent_name": "policy-research-agent",
  "question": "Does current IRS guidance change the 45V credibility state?"
}
```

Use `ingest_source_url` only when the agent cannot reliably extract a citation
anchor itself. Prefer `submit_policy_evidence` because it forces the agent to
name the exact quote that supports the claim.

Run the daily research scout in dry-run mode:

```bash
uv run --extra dev python scripts/run_agent_research_intake.py \
  --since 2026-06-01 \
  --output-path data/debug/agent_research_intake.json
```

The scout uses OpenAI web search over official-source domains, returns
structured source candidates, and writes only when `--write` is passed and
`status.write_configured` is true. If `status.agent_intake_configured` is false,
apply migration `005` before expecting governed agent-submission rows.

Start the Supabase-backed registry and web app from one command:

```bash
./scripts/run_registry.sh
```

The command sources `.env`, defaults to the previous complete Monday-Sunday week, runs every backend stage, refreshes outcomes, builds the web app, and serves it on port `8510` at host `0.0.0.0`. Override with `START_DATE`, `END_DATE`, `PORT`, or `HOST`.

## Web App

`apps/web` contains the read-only companion and dashboard:

| Route | Purpose |
|---|---|
| `/` | Live policy terminal: PCI by provision with cited official-source updates |
| `/about` | Companion page for the PNAS paper — abstract, anchors, and BibTeX; links the manuscript (`/paper.pdf`) and SI Appendix (`/si-appendix.pdf`) |
| `/connect` | Hosted read-only MCP + local write connector setup |
| `/dashboard` | Deprecated; 301-redirects to `/` |

The UI reads from Supabase public views:

| View | UI Surface |
|---|---|
| `v_current_pci` | provision cards and PCI scores |
| `v_policy_events` | official policy event feed |
| `v_evidence_items` | citations and source-backed snippets |
| `v_source_links` | links from evidence to events, forecasts, and market rows |
| `v_source_health` | plain-language source freshness labels |

Private order payloads, raw model responses, API keys, firm data, signatures, and private file paths must never appear in public views.

## Data Contracts

The backend keeps three file-level contracts for tests and offline runs:

| Contract | Producer | Consumer | Path |
|---|---|---|---|
| Raw official documents | `pci_realtime.ingest.*` | scoring filter and scorer | `data/raw/<source>/<source>_<YYYY-WW>.parquet` |
| Scored PCI deltas | `pci_realtime.scoring.scorer` | weekly PCI builder | `data/processed/scored/scored_<YYYY-WW>.parquet` |
| Weekly PCI series | `pci_realtime.pci.builder` | registry loop and export jobs | `data/processed/pci_weekly.parquet` |

The product-facing contract is the registry tables: `provisions`, `pci_weekly`, `policy_events`, `pipeline_runs`, `source_documents`, `evidence_items`, `source_links`, and `source_health`.

## Capability Status

| Capability | Status |
|---|---|
| Paper anchors and OBBBA stress anchors | implemented |
| Federal Register, Treasury, IRS, and OMB ingest | implemented |
| Congress.gov primary legislative ingest | implemented, ProPublica fallback optional |
| Regulations.gov, RegInfo/OIRA, and USAspending ingest | wired into the default weekly command |
| GovInfo, EIA, FRED, and CourtListener clients | scaffolded for public context |
| LLM scoring and caching | implemented |
| Weekly PCI builder | implemented |
| Prediction-market layer | removed 2026-07 (never produced production forecasts) |
| Normalized source documents, evidence items, trace links, and source health | implemented |
| Public Supabase views | implemented |
| Cloud scheduler | not configured; run registry commands manually or attach an external scheduler |
| Secured webhook runner | Supabase Edge Functions proxy to an external Python runner when configured |

## Cloud Provisioning

Canonical public URL: <https://pcindex.vercel.app>.

CLI checks:

```bash
vercel whoami
supabase projects list
```

Provision Supabase after `supabase login`:

```bash
export SUPABASE_PROJECT_REF=<project-ref>
./scripts/provision_supabase.sh
```

For a new Supabase project, set `SUPABASE_ORG_ID` and `SUPABASE_DB_PASSWORD`; the script creates the project and prints the project ref to use on the next run.

Provision the public research-style site on Vercel:

```bash
cd apps/web
vercel link --project pci-forecast-registry
vercel env add NEXT_PUBLIC_SUPABASE_URL production
vercel env add NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY production
vercel --prod
vercel alias set <deployment-url> pcindex.vercel.app
```

The Vercel app reads the public Supabase views from the browser, so the landing page and registry stay current after the backend registry commands write fresh data.

This repository does not ship GitHub Actions CI/CD workflows. Run backend registry commands manually from a trusted local or server environment with the needed environment variables present.

Supabase Edge Function triggers are intentionally fail-closed. If they are used, set both the outbound webhook values and the inbound trigger secret:

```bash
supabase secrets set PYTHON_PIPELINE_WEBHOOK_URL
supabase secrets set PYTHON_PIPELINE_WEBHOOK_SECRET
supabase secrets set PYTHON_PIPELINE_TRIGGER_SECRET
```

GitHub CLI access currently needs re-authentication before pushing under `yudduy`.

## Release Rules

- Code is MIT licensed.
- Public outputs are PCI values, public market snapshots, forecasts, outcomes, proposal status summaries, and aggregate metrics.
- Licensed or private firm-level inputs never enter this repository.
- Backfills that may exceed the configured model-cost ceiling require `--confirm-cost`.
