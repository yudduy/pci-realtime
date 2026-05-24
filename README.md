# PCI Real-Time Monitor

Real-time **Policy Credibility Index** (PCI) monitor for key Inflation Reduction Act (IRA) climate provisions. Ingests official federal policy documents, scores their effect on policy credibility with LLMs, and writes a Supabase-backed forecast and gated trading registry.

> **Status:** Active build, Phases 0-3 complete through the PCI time-series builder. See `CLAUDE.md` for the full status board and two-RA track ownership.

## Why this exists

The companion PNAS paper (Cao, Eesley, Jain, Moorjani 2026) introduces a Policy Credibility Index (PCI) that scores six focal IRA provisions on **specificity** (rule-based eligibility vs. discretionary), **durability** (multi-year statutory horizon vs. annual reauthorization), and **enforceability** (clear agency assignment vs. discretionary implementation). The paper computes PCI as two static snapshots (Aug 2022 enactment + 2025 OBBBA shock). This repo turns those snapshots into a continuously updated weekly series.

The output supports a follow-up methods paper targeting *Nature Energy*.

## Six focal provisions

| Code | Provision | Aug 2022 baseline PCI |
|---|---|---:|
| `45X` | Advanced Manufacturing Production Credit | 4.67 |
| `45V` | Clean Hydrogen Production Credit | 4.33 |
| `45Q` | Carbon Oxide Sequestration Credit | 4.33 |
| `30D` | Clean Vehicle Credit | 4.00 |
| `50144` | Energy Infrastructure Reinvestment (LPO) | 3.33 |
| `50141` | Loan Programs Office Funding | 3.00 |

Baseline anchors live (immutable) in `data/baseline/pci_baseline.csv`.

## Team

| Role | Person | Owns |
|---|---|---|
| PI | Yikai Cao (Stanford) | scope, manual ΔPCI scoring of calibration set, code review, paper Intro + Discussion |
| First author / methodology | **Duy** | LLM scoring module (`src/pci_realtime/scoring/`), validation analysis, paper Sections 2–4 |
| Second author / infrastructure | **Austin** | additional ingestors (`src/pci_realtime/ingest/`), time-series builder (`src/pci_realtime/pci/`), deployment plumbing |
| Senior coauthor | Charles Eesley (Stanford) | strategic direction, paper edits |

Track-level deliverables and the 8-week timeline live in `CLAUDE.md` §Two-RA tracks.

## Repository layout

```text
pci-realtime/
├── src/pci_realtime/        # installable package (`pip install -e .`)
│   ├── config.py            # provision list, paths, defaults
│   ├── ingest/              # Austin owns — federal_register.py exists
│   ├── filter/              # Duy owns
│   ├── scoring/             # Duy owns — Stage 1 screener + Stage 2 scorer + cache
│   ├── pci/                 # Austin owns — weekly PCI builder
│   ├── forecast_registry/   # policy constants, forecast engine, Kalshi, Supabase store
│   ├── pipeline/            # seed, weekly live run, daily refresh entrypoints
│   └── dashboard/           # placeholder; not the active product path
├── supabase/                # Postgres migrations + orchestration Edge Functions
├── data/
│   ├── raw/                 # ingested docs (gitignored)
│   ├── processed/           # scored docs + pci_weekly.parquet (gitignored)
│   ├── cache/               # LLM response cache (gitignored)
│   ├── baseline/            # immutable PCI anchors from the paper (committed)
│   └── fixtures/            # 11-doc Federal Register golden set + 20-doc calibration set (committed)
├── tests/
├── docs/
│   ├── phase0_scoring_spec.md     # Duy's locked scoring rubric (read first)
│   └── interfaces.md              # locked Austin↔Duy hand-off schemas
├── notebooks/
├── pyproject.toml
├── .env.example
└── CLAUDE.md                # full project guide for AI assistants and humans
```

## Quick start

```bash
# 1. Clone
git clone git@github.com:yikaicao/pci-realtime.git
cd pci-realtime

# 2. Install
pip install -e ".[dev]"

# 3. Set up secrets
cp .env.example .env
# fill in OPENAI_API_KEY, ANTHROPIC_API_KEY, PROPUBLICA_CONGRESS_API_KEY

# 4. Run tests
pytest

# 5. Pull a sample week from the Federal Register
python -m pci_realtime.ingest.federal_register \
  --start-date 2024-04-08 \
  --end-date 2024-04-14 \
  --output-dir data/raw/federal_register

# 6. Rebuild the weekly PCI series from scored deltas
python -m pci_realtime.pci.builder --rebuild

# 7. Seed Supabase with paper anchors
python -m pci_realtime.pipeline.seed_supabase --dry-run

# 8. Run the one weekly backend loop in dry-run mode
python -m pci_realtime.pipeline.weekly_live \
  --start-date 2025-06-02 \
  --end-date 2025-06-08 \
  --skip-ingest \
  --skip-score \
  --dry-run \
  --output-path data/debug/weekly_live_payload.json

# 9. Launch the Supabase-backed local demo
./scripts/demo_local.sh
```

## LLM configuration

The scorer uses LLMs as policy-document annotators, not as a news sentiment
engine. The default cascade is cost-optimized:

- screening: `openai` / `gpt-5-mini`
- primary scoring: `openai` / `gpt-5-mini`
- audit model placeholder: `anthropic` / `claude-sonnet-4-6`

Configure this through `.env`:

```bash
PCI_SCREENING_PROVIDER=openai
PCI_SCREENING_MODEL=gpt-5-mini
PCI_SCORING_PROVIDER=openai
PCI_SCORING_MODEL=gpt-5-mini
PCI_AUDIT_PROVIDER=anthropic
PCI_AUDIT_MODEL=claude-sonnet-4-6
```

The scoring CLI also accepts explicit provider/model overrides:

```bash
python -m pci_realtime.scoring.scorer \
  --week 2025-W23 \
  --screening-provider openai \
  --screening-model gpt-5-mini \
  --scoring-provider openai \
  --scoring-model gpt-5-mini
```

## Backend Product Loop

The active product path is one backend loop, not a static bundle or dashboard:

- paper-grounded six-provision PCI anchors
- OBBBA implied PCI anchors
- live weekly PCI values when scored official-source events exist
- forecast commitments after a real signal is matched to a real eligible Kalshi market
- gated trade proposals after forecasts pass risk checks
- resolved forecast metrics after outcomes are available

Seed Supabase locally or remotely with real paper anchors:

```bash
python -m pci_realtime.pipeline.seed_supabase --dry-run
python -m pci_realtime.pipeline.seed_supabase
```

The non-dry-run command requires `SUPABASE_URL` and
`SUPABASE_SERVICE_ROLE_KEY`.

Run the weekly loop against existing raw/scored inputs and a local Kalshi
fixture:

```bash
python -m pci_realtime.pipeline.weekly_live \
  --start-date 2025-06-02 \
  --end-date 2025-06-08 \
  --skip-ingest \
  --skip-score \
  --market-fixture-path path/to/kalshi_fixture.json \
  --dry-run \
  --output-path data/debug/weekly_live_payload.json
```

Run the live weekly loop with official Federal Register ingest, LLM scoring, and
Kalshi market discovery:

```bash
python -m pci_realtime.pipeline.weekly_live \
  --start-date 2025-06-02 \
  --end-date 2025-06-08 \
  --skip-bodies \
  --confirm-cost \
  --fetch-markets
```

Trading proposals are created only after forecast risk gates pass. Live Kalshi
execution is disabled unless `PCI_ENABLE_LIVE_TRADING=true`, Kalshi credentials
are present, and the proposal id is explicitly approved in an approval file.

## Web App

The lab-demo frontend lives in `apps/web`. It is a read-only Next.js workbench
that reads Supabase public views; it does not own paper anchors, forecasts, or
trade rows.

One command starts local Supabase if needed, seeds the paper anchors, runs a
policy-filtered Kalshi scan, and launches the app:

```bash
./scripts/demo_local.sh
```

The demo intentionally shows zero forecast commitments when no official PCI
event has matched a clean market. It does not invent rows to make the screen
look busy.

With the demo server running, smoke-test the live local surface:

```bash
npm --prefix apps/web run test:e2e:live
```

```bash
cd apps/web
npm ci
SUPABASE_URL=http://127.0.0.1:54321 \
SUPABASE_PUBLISHABLE_KEY=<local-or-cloud-publishable-key> \
  npm run dev
```

The UI is data-driven:

- provision cards come from `v_current_pci`
- forecast cards come from `v_open_forecasts`
- read-only market-scan cards come from `v_market_snapshots`
- gated proposal status comes from `v_trade_proposals`
- policy events and track record come from `v_policy_events` and `v_resolved_forecasts`

No synthetic forecasts, fake trades, private order payloads, or firm-level
financing rows are rendered in the public app.

## Cloud Provisioning

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

For a brand-new project, set `SUPABASE_ORG_ID` and `SUPABASE_DB_PASSWORD`
instead of `SUPABASE_PROJECT_REF`; the script will create the project and ask
you to rerun after you set the new ref.

Provision Vercel after `vercel login`:

```bash
export VERCEL_PROJECT_NAME=pci-forecast-registry
./scripts/provision_vercel.sh
vercel env add --cwd apps/web SUPABASE_URL production
vercel env add --cwd apps/web SUPABASE_PUBLISHABLE_KEY production
vercel deploy --cwd apps/web --prod
```

GitHub is currently blocked locally because `gh` has an invalid `yudduy`
token. Re-authenticate with `gh auth login -h github.com`; then create or push
the repo under `yudduy` before connecting it to Vercel.

## Hand-off contracts

The original parquet hand-off schemas are locked in `docs/interfaces.md`:

1. `ingest/` → `scoring/` — raw document parquet
2. `scoring/` → `pci/builder.py` — scored deltas parquet
3. `pci/` → registry/backend — weekly PCI time series parquet

The active product-facing contract is Supabase: the weekly backend writes
`provisions`, `pci_weekly`, `policy_events`, `market_snapshots`, `forecasts`,
`trade_proposals`, `forecast_outcomes`, and `pipeline_runs`; frontend clients
read only public views.

Either Austin or Duy can change a column ONLY via PR with both as reviewers and Yikai signoff.

## Phase status

| Phase | Status | Owner | Output |
|---|---|---|---|
| 0 — Scoring spec | ✅ done | Duy | `docs/phase0_scoring_spec.md` |
| 1 — Federal Register ingestion | ✅ done (POC week) | Duy | `src/pci_realtime/ingest/federal_register.py` |
| 1 ext — Treasury / Congress / OMB ingestors | ✅ done (scaffold) | Austin | `src/pci_realtime/ingest/{base,treasury,congress,omb}.py` |
| 2 — LLM scoring + calibration | ✅ MVP done | Duy | `src/pci_realtime/scoring/`, `docs/calibration_report.md` |
| 3 — Time series builder | ✅ done | Austin | `src/pci_realtime/pci/builder.py` |
| 4 — Paper evidence layer | ⏳ Week 6 | Duy | OBBBA anchors, aggregate CPU/VC evidence, forecast interpretation |
| 5 — Registry backend + cron | ⏳ Week 7 | Austin | Supabase-backed weekly/daily jobs, forecast ledger, gated proposals |
| 6 — Methods paper draft | ⏳ Week 8 | Duy + Yikai | external draft |

## Data and license

- **Code:** MIT.
- **Output data:** PCI time series, public market snapshots, forecasts, outcomes, and aggregate metrics are public.
- **Licensed inputs (PitchBook):** never enter this repo. Validation Check 2 reads them from the parent project's `Data/PanelData/` and only commits aggregated/de-identified outputs.

## Privacy

This is a private repo until the methods paper is on arXiv, then it flips to public for replication.
