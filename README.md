# Policy Credibility Registry

Supabase-backed registry for the Policy Credibility Index (PCI) from the IRA venture-capital research project. The system turns official federal policy documents into weekly PCI updates, matches those updates to clean public prediction markets, and records forecasts, gated trade proposals, and resolved outcomes.

The public web app is a research companion and read-only registry surface. It does not place orders, invent forecasts, or expose private execution payloads.

## Product Loop

```text
official policy documents
  -> provision relevance filter
  -> PCI delta scoring
  -> weekly PCI series
  -> market discovery
  -> forecast registry
  -> gated trade proposal
  -> outcome tracking
```

`weekly_live` owns the full weekly path: ingest official sources, score PCI deltas, build PCI, fetch public market data, create forecasts, gate trade proposals, and publish registry rows. `daily_refresh` reads open forecasts, refreshes market results, records settlements, refreshes public context sources, and stores performance metadata.

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
│   ├── forecast_registry/
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

Run the weekly registry loop with official source ingest, LLM scoring, broad market discovery, gated proposals, and Supabase writes:

```bash
python -m pci_realtime.pipeline.weekly_live \
  --start-date 2026-05-18 \
  --end-date 2026-05-24 \
  --confirm-cost \
  --fetch-markets \
  --fetch-polymarket
```

The weekly loop defaults to `--evidence-mode audit`. Audit mode caches official-source HTTP responses under `data/cache/source_requests`, chunks ingested source documents, runs provision-aware deterministic retrieval, and stores shadow evidence rows plus `pipeline_runs.metadata.evidence_engine`. It does not change PCI scores. Use `--evidence-mode off` to disable the audit layer for one-off debugging.

Run only the public market discovery/audit loop:

```bash
python -m pci_realtime.pipeline.market_discovery --dry-run \
  --output-path data/debug/market_discovery_payload.json
python -m pci_realtime.pipeline.market_discovery
```

The discovery loop paginates public Kalshi and Polymarket surfaces, stores eligible market snapshots, and records near-miss candidates with rejection reasons. Use `--include-all-candidates` only for bounded absence audits because it persists every scanned public market row.
The scheduled default scans 5,000 open Kalshi markets plus 1,000 active Polymarket events; raise `--polymarket-limit` for one-off deeper absence audits.

Refresh market outcomes and performance metadata from Supabase:

```bash
python -m pci_realtime.pipeline.daily_refresh --supabase
```

Start the Supabase-backed registry and web app from one command:

```bash
./scripts/run_registry.sh
```

The command sources `.env`, defaults to the previous complete Monday-Sunday week, runs every backend stage, refreshes outcomes, builds the web app, and serves it on port `8510` at host `0.0.0.0`. Override with `START_DATE`, `END_DATE`, `PORT`, or `HOST`.

## Web App

`apps/web` contains the read-only companion and dashboard:

| Route | Purpose |
|---|---|
| `/` | Live policy-market tracker landing with cited official-source updates |
| `/dashboard` | Polymarket-style registry for PCI, markets, forecasts, proposals, events, and outcomes |

The UI reads from Supabase public views:

| View | UI Surface |
|---|---|
| `v_current_pci` | provision cards and PCI scores |
| `v_open_forecasts` | active forecast cards |
| `v_market_snapshots` | read-only market scan cards |
| `v_market_discovery_candidates` | latest eligible and near-miss market candidates |
| `v_trade_proposals` | gated proposal summaries |
| `v_policy_events` | official policy event feed |
| `v_resolved_forecasts` | track record |
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

The product-facing contract is the registry tables: `provisions`, `pci_weekly`, `policy_events`, `market_snapshots`, `market_discovery_candidates`, `forecasts`, `trade_proposals`, `forecast_outcomes`, `pipeline_runs`, `source_documents`, `document_chunks`, `evidence_items`, `source_links`, and `source_health`. `source_request_cache` is private service-role state for replay and rate-limit auditing.

## Capability Status

| Capability | Status |
|---|---|
| Paper anchors and OBBBA stress anchors | implemented |
| Federal Register, Treasury, IRS, and OMB ingest | implemented |
| Congress.gov primary legislative ingest | implemented, ProPublica fallback optional |
| Regulations.gov, RegInfo/OIRA, and USAspending ingest | wired into the default weekly command |
| GovInfo, EIA, FRED, CourtListener, and Polymarket clients | scaffolded for public context and market discovery |
| LLM scoring and caching | implemented |
| Weekly PCI builder | implemented |
| Forecast registry, public market reads, and gated proposals | implemented |
| Normalized source documents, evidence items, trace links, and source health | implemented |
| Public Supabase views | implemented |
| Cloud scheduler | GitHub Actions workflows for weekly production and daily refresh |
| Secured webhook runner | Supabase Edge Functions proxy to an external Python runner when configured |

## Cloud Provisioning

Canonical public URL: <https://pcindex.vercel.app>.

CLI checks:

```bash
vercel whoami
supabase projects list
gh auth status
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

The Vercel app reads the public Supabase views from the browser, so the landing page and registry stay current while the backend updates the data on its weekly and daily schedules.

Set these GitHub repository secrets for the production workflows:

```bash
gh secret set SUPABASE_URL
gh secret set SUPABASE_SERVICE_ROLE_KEY
gh secret set OPENAI_API_KEY
gh secret set CONGRESS_GOV_API_KEY
gh secret set REGULATIONS_GOV_API_KEY
gh secret set GOVINFO_API_KEY
gh secret set FRED_API_KEY
gh secret set PROPUBLICA_CONGRESS_API_KEY
gh secret set NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
```

Optional repository variables:

```bash
gh variable set FEDERAL_REGISTER_USER_AGENT --body "pci-realtime-production/0.1"
gh variable set PCI_SCREENING_MODEL --body "gpt-5.4-nano"
gh variable set PCI_SCORING_MODEL --body "gpt-5.4-mini"
gh variable set PCI_AUDIT_MODEL --body "gpt-5.5"
```

`.github/workflows/production-registry-pipeline.yml` runs the complete weekly loop every Monday. `.github/workflows/production-market-discovery.yml` scans public market venues every six hours. `.github/workflows/production-registry-refresh.yml` refreshes market settlements and metrics daily.
`.github/workflows/production-smoke.yml` checks `https://pcindex.vercel.app` and the public Supabase views every six hours.

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
