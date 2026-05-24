# CLAUDE.md — PCI Real-Time Monitor

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Real-Time Policy Credibility Index (PCI) Monitor** — A pipeline that continuously updates the Policy Credibility Index for major IRA climate provisions by ingesting federal policy documents, scoring them with LLMs, and writing a Supabase-backed forecast/trading registry.

- **Parent project:** PNAS submission "Industrial Policy Reshapes Venture Capital Allocation and Growth Trajectories in Climate Technologies" (Cao, Eesley, Jain, Moorjani)
- **This repo:** A standalone extension that converts the paper's two-snapshot PCI into a continuously updated time series
- **Authorship of the methods paper:** Duy (first), Austin (second), Yikai Cao (third / PI), Chuck Eesley (fourth)
- **Status:** Phases 0-3 are complete through the weekly PCI builder; the active product path is the Supabase forecast registry.
- **Target output:** A second paper (methods article, *Nature Energy* or *Research Policy*) + a Supabase-backed PCI forecast/trading registry.
- **GitHub remote:** `github.com/yikaicao/pci-realtime` (private until methods paper is on arXiv)

**Read this before working in the repo:**
- `../../RA Task/RA_PCI_RealTime_Monitor_Guide.md` — full project plan, phased milestones, scope
- `docs/phase0_scoring_spec.md` — Duy's locked scoring rubric (read this first)
- `docs/interfaces.md` — three schemas locking Austin↔Duy hand-off points
- `../../Draft/PNAS.../Mechanism/Credibility.tex` — original PCI definition
- `../../Draft/PNAS.../SI_Appendix.tex` §G — scoring protocol (1–5 scale on specificity / durability / enforceability)

## Repository Structure

```
pci-realtime/
├── src/
│   └── pci_realtime/                # installable package (see pyproject.toml)
│       ├── config.py                # provisions, paths, defaults (Duy)
│       ├── ingest/                  # ─── Austin owns ────────────────────
│       │   ├── federal_register.py  # ✅ working (Duy, Phase 1)
│       │   ├── treasury.py          # TODO Austin — IRS / Treasury guidance scraper
│       │   ├── congress.py          # TODO Austin — ProPublica / GovInfo
│       │   ├── omb.py               # TODO Austin — OMB memos (low priority)
│       │   └── base.py              # TODO Austin — BaseIngestor shared interface
│       ├── filter/                  # relevance filter — Duy
│       ├── scoring/                 # ─── Duy owns ──────────────────────
│       │   ├── screener.py          # Stage 1 provider-configured model
│       │   ├── scorer.py            # Stage 2 provider-configured scoring model
│       │   ├── prompts.py           # versioned prompt templates
│       │   └── cache.py             # hash-based LLM call cache
│       ├── pci/                     # ─── Austin owns ────────────────────
│       │   └── builder.py           # weekly update rule
│       ├── forecast_registry/       # forecasts, Kalshi, trading gates, Supabase store
│       ├── pipeline/                # seed, weekly live run, daily refresh
│       └── dashboard/               # deferred placeholder
├── data/
│   ├── raw/                         # ingested docs, parquet by source/week (gitignored)
│   ├── processed/                   # scored docs + pci_weekly.parquet (gitignored)
│   ├── cache/                       # LLM response cache (gitignored)
│   ├── fixtures/                    # ✅ committed
│   │   ├── federal_register_known_documents.csv  # Duy's 11-doc golden set
│   │   └── calibration_set_v1.csv   # Austin extends, Yikai scores ΔPCI
│   └── baseline/                    # ✅ committed — immutable PCI anchors from the paper
├── tests/                           # pytest (Duy's test_federal_register.py exists)
├── notebooks/                       # exploratory only
├── docs/
│   ├── phase0_scoring_spec.md       # ✅ Duy's locked scoring rubric (read first)
│   ├── interfaces.md                # ✅ three schemas — Austin↔Duy hand-off contracts
│   └── cost_log.md                  # running LLM spend tally
├── .github/
│   └── workflows/
│       ├── ci.yml                   # ✅ pytest on push and PR
│       └── weekly_update.yml        # GitHub Actions cron (Mondays 12:00 UTC) — Austin
├── pyproject.toml                   # ✅ installable package
├── .env.example                     # ✅ API key placeholders
├── README.md                        # public-facing
└── CLAUDE.md                        # this file
```

## Environment & Setup

**Use the existing `cleantech` conda env** — do not create a new one. Add project-specific packages via `pip install` inside that env.

```bash
# Activate (required before all commands)
conda activate cleantech
cd "/Users/yikaicao/Documents/Stanford/Project/Climate-tech/Code/pci-realtime"

# Install this project's extra dependencies
pip install -e .

# Required env vars (in .env)
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
PROPUBLICA_CONGRESS_API_KEY=...   # free, register at propublica.org
```

**Do not commit `.env`.** `.env.example` is checked in with placeholder values.

## Core Commands

The package installs as `pci_realtime`; module paths use that namespace.

```bash
# Ingest — pull new federal policy documents for a date range
python -m pci_realtime.ingest.federal_register --start 2024-01-01 --end 2024-12-31
python -m pci_realtime.ingest.treasury --start 2024-01-01 --end 2024-12-31
python -m pci_realtime.ingest.congress --start 2024-01-01 --end 2024-12-31

# Score — run the two-stage LLM pipeline on ingested docs
python -m pci_realtime.scoring.scorer --week 2024-W50

# Build / rebuild the PCI time series from scored docs
python -m pci_realtime.pci.builder --rebuild

# Run the backend product loop locally in dry-run mode
python -m pci_realtime.pipeline.weekly_live \
  --start-date 2025-06-02 \
  --end-date 2025-06-08 \
  --skip-ingest \
  --skip-score \
  --dry-run \
  --output-path data/debug/weekly_live_payload.json

# Tests
pytest tests/                        # full suite
pytest tests/ -k "ingest"            # run only ingest tests
pytest tests/ --cov=pci_realtime     # with coverage
```

## Two-RA tracks (who owns what)

This project runs as two parallel tracks with locked hand-off interfaces (see `docs/interfaces.md`).

### Track A — Duy (methodology / scoring / evidence)

| Phase | Module | Deliverable |
|---|---|---|
| 0 ✅ | `docs/phase0_scoring_spec.md` | Locked scoring rubric (already done) |
| 1 ✅ | `ingest/federal_register.py` | Federal Register ingestor (already done) |
| 2 ✅ | `scoring/` | Stage-1 screener + Stage-2 scorer + prompt versioning + hash cache |
| 4 | paper evidence layer | OBBBA anchor logic, aggregate CPU/VC evidence, and forecast-registry interpretation |
| 6 | external draft | Methods paper Sections 2–4 + application empirics |

### Track B — Austin (infrastructure / registry)

| Phase | Module | Deliverable |
|---|---|---|
| 0 (now) | `data/fixtures/calibration_set_v1.csv` | Extend Duy's 11-doc fixture to ~20 federal-policy events; Yikai fills ΔPCI scores |
| 1+ ✅ | `ingest/{base,treasury,congress,omb}.py` | Treasury, Congress, OMB scaffolds and shared `BaseIngestor` interface |
| 3 ✅ | `pci/builder.py` | Weekly update rule and sticky PCI stock |
| 5 | `forecast_registry/` + `pipeline/` | Supabase registry, Kalshi market scan, forecast ledger, gated trade proposals |
| 5 | Supabase Edge Functions / cron | trigger weekly pipeline and daily refresh |

### Track Y — Yikai (PI)

- Manual ΔPCI scoring of the 20-doc calibration set (one-time, ~2 hr)
- Code review on all PRs
- Weekly 1:1 (Mon, 30 min each); bi-weekly joint sync (Fri, 60 min)
- Cost / scope signoff for any LLM run > $50
- Methods-paper Intro + Discussion drafts (Weeks 7–8)

## Architecture: The 6 IRA Provisions

**These are the only provisions in scope.** Do not add others without discussing with Yikai.

| Section | Name | Baseline PCI (Aug 2022) |
|---|---|---|
| 45X | Advanced Manufacturing Production Credit | 4.67 |
| 45V | Clean Hydrogen Production Credit | 4.33 |
| 45Q | Carbon Capture Credit | 4.33 |
| 30D | Clean Vehicle Credit | 4.00 |
| 50144 | Energy Infrastructure Reinvestment (LPO) | 3.33 |
| 50141 | Loan Programs Office Funding | 3.00 |

**Scoring dimensions (each 1–5):**
- **Specificity** — rule-based eligibility vs. discretionary allocation
- **Durability** — multi-year statutory horizon vs. annual reauthorization
- **Enforceability** — clear agency assignment vs. discretionary implementation

**PCI = mean of the three dimensions.** All three weighted equally by design.

**Weekly update rule:**
```
PCI[p, t] = PCI[p, t-1] + Σ (deltas affecting provision p in week t) / 3
```
Sticky by default (no decay toward baseline). Capped at [1.0, 5.0].

## Data Flow

```
Federal Register API ─┐
Congress API ─────────┼─► pci_realtime/ingest/*.py ─► data/raw/<source>/<source>_YYYY-WW.parquet
Treasury scraper ─────┘                              (Austin owns ingestion)
                                              │
                                              ▼
                       pci_realtime/scoring/screener.py (default: openai / gpt-5-mini)
                                              │
                              relevant? ──No──► dropped       (Duy owns scoring)
                                 │ Yes
                                 ▼
                       pci_realtime/scoring/scorer.py (default: openai / gpt-5-mini)
                                              │
                                              ▼
                          data/processed/scored/scored_YYYY-WW.parquet
                                              │
                                              ▼
                            pci_realtime/pci/builder.py        (Austin owns index)
                                              │
                                              ▼
                     data/processed/pci_weekly.parquet
                                              │
                                              ▼
                          pci_realtime/pipeline/weekly_live.py
                                              │
                                              ▼
        Supabase tables/views: provisions, pci_weekly, policy_events, markets,
        forecasts, trade_proposals, outcomes, pipeline_runs
```

The three hand-off points (parquet schemas) are locked in `docs/interfaces.md`. Either RA changing them needs a PR + the other RA's review + Yikai signoff.

## Working with LLMs in This Repo

**Always cache.** Every LLM call must go through `pci_realtime/scoring/cache.py`, which hashes `(model, prompt_version, input_text)` and stores responses. Re-runs are free; experiments don't burn money.

**Two-stage cost control:**
- Stage 1 (screening) defaults to `openai` / `gpt-5-mini`.
- Stage 2 (scoring) defaults to `openai` / `gpt-5-mini`, with provider/model overrides via `PCI_SCORING_PROVIDER` and `PCI_SCORING_MODEL`.
- Anthropic is available as an alternate or audit provider through `PCI_AUDIT_PROVIDER=anthropic` and `PCI_AUDIT_MODEL=claude-sonnet-4-6`.
- Budget: ~$20/month steady-state. If a planned run will exceed $50, flag it in `docs/cost_log.md` and ping Yikai before running.

**Log every call.** Prompt version, model, source document ids, cost estimate, and timestamp should be retained through the scoring cache and cost log. Never commit API keys or raw private data.

**Prompt versioning.** Prompts live in `pci_realtime/scoring/prompts.py` as named constants with a `VERSION` field. Never mutate a prompt in place — bump the version and keep the old one. All cached responses are keyed to prompt version.

**Temperature.** Use `temperature=0.3` for scoring (low noise, not zero — we want to measure variance). Run each scoring call 5× during calibration to measure inter-run variance; in production, 1× is fine after calibration passes.

**Skill:** The `claude-api` skill is relevant when working on `pci_realtime/scoring/*`. Invoke it when adding prompt caching, migrating models, or debugging SDK calls.

## Git & Collaboration

- **Branch naming:** `<owner>/<phase>-<short>` (e.g., `austin/phase-3-index`, `duy/phase-2-scoring`, `yikai/calibration-set`). Squash-merge to keep history linear.
- **Small commits, clear messages.** Prefix with scope: `ingest:`, `scoring:`, `pci:`, `registry:`, `docs:`.
- **Never commit:** `.env`, `data/raw/`, `data/processed/`, `data/cache/`, `data/debug/`, API keys, signed trade requests, `__pycache__/`, PitchBook firm-level data.
- **Always commit:** source code, tests, Supabase migrations/functions, `docs/cost_log.md`, `data/baseline/` immutable anchors, and `data/fixtures/` calibration fixtures.
- **PRs need:** passing `pytest`, updated `README.md` if user-facing changes, cost log updated if new LLM spend.
- **All PRs reviewed by Yikai before merge to main.**

## Current TODO

1. Re-authenticate GitHub CLI, push `main`, and connect Vercel to the repository.
2. Provision Supabase cloud, apply `supabase/migrations/001_core_registry.sql`, and seed paper anchors.
3. Add `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` to Vercel; the web app should render the Polymarket-style registry UI from Supabase public views.
4. Add a real scheduler: GitHub Actions cron or Supabase cron should call the weekly and daily triggers.
5. Wire Supabase Edge Function triggers to a secured Python weekly/daily backend runner.
6. Add Treasury/IRS, Congress, and OMB ingestors to the default weekly loop after one Federal Register smoke run.
7. Run one cost-reviewed official-source weekly pipeline before any full backfill.
8. Expand Kalshi query coverage only for objective policy markets mapped to `45X`, `45V`, `45Q`, `30D`, `50141`, or `50144`.

## Registry Gates

Before a forecast or trade proposal becomes public, the backend must satisfy the product gates in `forecast_registry/engine.py`:

1. **Paper-grounded signal.** A signal must come from a scored official policy event affecting one of the six tracked IRA provisions.
2. **Clean market match.** A Kalshi market must be policy relevant, directly mapped to the provision/channel, and have clear resolution text.
3. **Conservative forecast.** The market prior remains dominant; the PCI rule adjustment is bounded; LLM output is optional and low-weight.
4. **Trading gate.** A proposal requires edge, spread, liquidity, confidence, exposure, public-info, and human-approval gates. Live orders require `PCI_ENABLE_LIVE_TRADING=true`, credentials, and an approval file.

Do not add synthetic forecasts to make demos look full. Empty forecast ledgers are acceptable until real official-source events match clean markets.

The registry does not scrape general news for PCI updates. PCI updates come from
official policy sources. As of this commit, `weekly_live.py` runs Federal Register
ingest by default; Treasury/IRS, Congress, and OMB ingestors exist but are not yet
part of the default weekly run. Kalshi market data is fetched separately with
`--fetch-markets`.

## Parent Project Dependencies

This repo reads from but never writes to:

| Path | Purpose |
|---|---|
| `../../Draft/PNAS.../Mechanism/Credibility.tex` | Reference PCI definition + baseline + OBBBA scores |
| `../../Draft/PNAS.../SI_Appendix.tex` §G | Scoring protocol |
| `../../Data/PanelData/climatetech_panel_2020_2025q2_final.parquet` | Private paper evidence; never committed here |
| `../../Code/outputs/cpu_revision_duy/` | Aggregate CPU evidence; public outputs only |

If any of those paths move, update this file and `pci_realtime/config.py`.

## Style & Conventions

- **Python 3.11.** Type hints everywhere except notebooks. Run `ruff check src/pci_realtime` and `ruff format src/pci_realtime` before committing.
- **Pandas vs. Polars:** use Polars for >1M-row operations, Pandas otherwise. Both are installed.
- **Dates:** ISO-week format (`YYYY-WW`) for all weekly partitions; `YYYY-MM-DD` otherwise. Never use locale-dependent date strings.
- **Logging:** stdlib `logging` with a module-level logger. No `print` in production code.
- **Config:** YAML in `config/` for query lists and user-tunable settings. Paper anchors live in committed baseline data and `forecast_registry/policy.py`.
- **Never invent data.** If a document's provision classification is ambiguous, the screener returns `ambiguous` and the scorer skips it. Don't guess.

## Testing

- **Every ingestor** must have (1) a unit test with a mocked API response and (2) an integration test hitting the real API with a known 1-day window that returns a known document.
- **Every scoring prompt** must have a regression test: for a fixed input, the mocked LLM returns a known output, and the scorer parses it into the expected schema.
- **The index builder** must round-trip: given a sequence of deltas, produce a time series; given the time series, recover the deltas (minus clipping).

Run tests before every PR:
```bash
pytest tests/ -v
```

## When You're Stuck

- **Scope questions** (should this provision be in? should we score this doc?) → ask Yikai via Telegram, don't guess.
- **LLM cost concerns** → stop and update `docs/cost_log.md` with an estimate before running anything over $10.
- **Prompt engineering** → read Phase 2 of `RA_PCI_RealTime_Monitor_Guide.md` first; then `claude-api` skill.
- **Registry design** → keep the Supabase views as the frontend contract; do not create a second static-data source of truth.
- **Forecast/trade gate failing** → don't loosen the risk checks to force output. Debug the signal, market mapping, or market eligibility.

## Non-Goals (Do Not Do These)

- Extend scope to non-IRA policies (CHIPS, BIL, EU) — save for a follow-up paper.
- Build a "live" sub-daily updater. Weekly is fine.
- Replace the baseline PCI with a re-estimation. Those anchors come from the paper and are immutable.
- Train a custom model. We use frontier LLMs as annotators; that's the methodology.
- Publish private order payloads, private firm data, or synthetic forecasts.
- Create autonomous live trading. Human approval is mandatory.

---

*Last updated: May 2026. If this file drifts from reality, update it.*
