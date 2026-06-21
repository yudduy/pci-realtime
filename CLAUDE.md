# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

`AGENT.md` is the canonical, exhaustive agent reference (full file map, env vars, Supabase schema, trading rules). Read it for depth. This file is the compressed orientation: what to run, the big-picture architecture, and the invariants you must not break.

## What this is

A Supabase-backed registry for the **Policy Credibility Index (PCI)** — institutional-design quality (specificity, durability, enforceability, each 1–5) for six IRA tax/loan provisions: `45X 45V 45Q 30D 50144 50141`. The system ingests **official public policy documents**, LLM-scores per-document PCI deltas, builds a sticky weekly PCI series, matches provisions to **public prediction markets** (Kalshi/Polymarket, read-only), and records forecasts, gated trade proposals, and outcomes. A read-only Next.js app (`apps/web`) renders Supabase public *views*.

Two things are intentionally out of scope and must stay that way: PCI is **not** a news/sentiment index (general news scraping is excluded from index updates), and the app **never** executes trades or exposes private execution payloads.

## Commands

Backend is Python via `uv`; web is npm under `apps/web`. Run checks manually before shipping (no CI in this repo).

```bash
# install
uv sync --extra dev
npm --prefix apps/web ci

# backend checks
uv run --extra dev pytest -q
uv run --extra dev ruff check src/pci_realtime tests
uv run --extra dev ruff format --check src/pci_realtime tests

# single test / focused run
uv run --extra dev pytest -q tests/test_builder.py
uv run --extra dev pytest -q tests/test_builder.py::test_name

# web checks
npm --prefix apps/web run typecheck
npm --prefix apps/web run lint
npm --prefix apps/web run test:e2e          # Playwright against a mock Supabase server
```

Pipelines (entry points are Python modules under `pci_realtime.pipeline`):

```bash
# seed paper anchors into Supabase (always dry-run first)
uv run --extra dev python -m pci_realtime.pipeline.seed_supabase --dry-run

# full weekly loop: ingest -> score -> build PCI -> market scan -> forecasts/proposals -> write
uv run --extra dev python -m pci_realtime.pipeline.weekly_live \
  --start-date 2026-05-18 --end-date 2026-05-24 --confirm-cost --fetch-markets --fetch-polymarket
# add: --dry-run --output-path data/debug/weekly_live_payload.json  (inspect, no writes)

# standalone public market discovery + absence audit
uv run --extra dev python -m pci_realtime.pipeline.market_discovery --dry-run

# refresh open forecasts, market results, settlements, public context
uv run --extra dev python -m pci_realtime.pipeline.daily_refresh --supabase
```

`./scripts/run_registry.sh` runs the whole loop locally and serves the web app on `:8510`. The `pci` console script (`pci_realtime.cli`) is a thin read/submit client over the registry service.

## Architecture

**Two pipelines own the loop.** `weekly_live` owns the full forward path (ingest → score → build → discover → forecast → propose → write). `daily_refresh` owns the backward path (refresh market results, record settlements, refresh public context + source health). Nothing else should write registry rows.

**The data flows through three file-level schema contracts** — keep them and their consumers in lockstep:

| Schema | Defined in | Shape | Path |
|---|---|---|---|
| A — raw official docs | `ingest/base.py:SCHEMA_A_COLUMNS` | doc_id, date, source, title, body, provisions_mentioned… | `data/raw/<source>/<source>_<YYYY-WW>.parquet` |
| B — scored deltas | `scoring/scorer.py:SCHEMA_B_COLUMNS` | per doc×provision dimension deltas in `[-2,+2]` | `data/processed/scored/scored_<YYYY-WW>.parquet` |
| C — weekly PCI series | `pci/builder.py:SCHEMA_C_COLUMNS` | provision, week, pci, dims, n_docs, delta | `data/processed/pci_weekly.parquet` |

The PCI update is **sticky**: `PCI[p,t] = clip(PCI[p,t-1] + Σ_doc(mean of the three deltas), 1, 5)`. Unchanged unless a scored doc moves it. Baseline anchors are immutable repo data in `data/baseline/pci_baseline.csv` (starts `2022-W33`).

**Module map** (directory altitude — see `AGENT.md` for per-file detail):
- `src/pci_realtime/ingest/` — one client per official source (Federal Register, Treasury/IRS, Congress, OMB, plus `public_sources.py` for Regulations.gov, RegInfo/OIRA, USAspending, GovInfo, EIA, FRED, CourtListener). All normalize to Schema A.
- `src/pci_realtime/scoring/` — `screener.py` (relevant/irrelevant/ambiguous) → `scorer.py` (dimension deltas, cost-ceilinged) → Schema B. `cache.py` keys by stable JSON; `prompts.py` holds schemas; `calibrate.py` gates on verified human-scored rows.
- `src/pci_realtime/pci/builder.py` — Schema B → sticky Schema C.
- `src/pci_realtime/forecast_registry/` — `policy.py`/`discovery.py` (market matching, resolution-clarity), `kalshi.py`/`polymarket.py` (public reads + execution gates), `engine.py` (events→signals→matches→forecasts→proposals→outcomes), `evidence.py` (source docs/items/links/health), `store.py` (Supabase REST + **public-payload safety checks** + write ordering).
- `apps/web` — Next 16 / React 19, App Router. `lib/data.ts` fetches public views with publishable keys only; `lib/market-model.ts` merges rows into UI `PolicyMarket` objects. Routes: `/`, `/dashboard`, `/about`, plus hosted `/mcp`, `/connect`, `/llms.txt`.
- `supabase/migrations/` — core tables + `v_*` public views. `supabase/functions/` Edge triggers only *proxy* to an external Python runner; they do not run the pipeline.

A schema change is a **four-file change**: migration ↔ `store.py`/`evidence.py` row adapters ↔ `apps/web/lib` TypeScript types ↔ tests. `tests/test_supabase_contract.py` asserts the privacy filters exist.

## Invariants (do not weaken)

- **Trading is fail-closed.** Live Kalshi execution requires *all of*: `PCI_ENABLE_LIVE_TRADING=true`, risk checks passed, proposal id in an approval file, Kalshi credentials present, and an explicit `--send`. Never relax a gate or surface signed request payloads.
- **Public views are privacy-filtered.** Forecast/proposal views require `private_info_used=false`, `policy_relevant=true`, `resolution_clear=true`; `v_market_snapshots` filters to `policy_relevant=true`. Never emit into public payloads: API key names, `sk-*`/`KALSHI_PRIVATE_KEY` secrets, `raw_response`, private firm identifiers, local `/Users/` paths, or signed trade data. The string `supabase` must not appear in rendered public pages (e2e checks this).
- **No synthetic forecasts.** A baseline-only run with no eligible signal/market produces zero forecasts and zero proposals. Tests rely on this.
- **Cost ceiling.** Live scoring whose estimate exceeds `PCI_LLM_RUN_COST_CEILING_USD` must pass `--confirm-cost`.
- **Core-source failure raises.** `weekly_live` degrades non-core source failures to source-health rows, but raises if all core sources (Federal Register, Congress, Regulations.gov, RegInfo/OIRA) fail.
- Don't edit `data/baseline/` or `data/fixtures/` unless explicitly asked, with tests/docs updated. Don't read or print `.env`/`.env.local`. `data/{raw,processed,cache,debug,private}`, `.next`, `.venv` are generated state.

## Conventions

Python 3.10+, snake_case, Ruff-formatted, typed small functions that preserve schema contracts. Web is TypeScript/React: kebab-case component files under `components/`, PascalCase exports, helpers in `apps/web/lib/`. Commits use concise imperative subjects with optional scopes (`web:`, `scoring:`). Browser code uses only publishable/anon Supabase keys; Python registry writes use the service-role key.
