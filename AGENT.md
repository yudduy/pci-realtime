# AGENT.md

Repository orientation for agents working on `pci-realtime`.

Last repo survey: 2026-05-26.

## Purpose

This repo implements a Policy Credibility Index (PCI) registry for IRA-related climate policy provisions. It ingests official public policy documents, screens and scores document-level PCI deltas, builds a sticky weekly PCI time series, matches policy signals to public prediction markets, records forecasts and gated trade proposals, and exposes a read-only public web app backed by Supabase views.

The public app is a research companion. It must never place trades, expose private execution payloads, leak API keys, publish raw model responses, or include private firm-level data.

Canonical production URL: `https://pcindex.vercel.app`.

## Product Loop

The intended loop is:

```text
official policy documents
  -> relevance screening
  -> PCI delta scoring
  -> weekly PCI series
  -> market discovery
  -> forecast registry
  -> gated trade proposal
  -> outcome tracking
```

`pci_realtime.pipeline.weekly_live` owns the weekly end-to-end path. `pci_realtime.pipeline.daily_refresh` owns market/outcome refresh and public context refresh. Supabase Edge Functions only proxy to an external Python runner; they do not run the pandas/parquet/LLM pipeline themselves.

## Repo Layout

```text
.
|-- README.md
|-- AGENT.md
|-- pyproject.toml
|-- uv.lock
|-- src/pci_realtime/
|   |-- config.py
|   |-- ingest/
|   |-- scoring/
|   |-- pci/
|   |-- forecast_registry/
|   `-- pipeline/
|-- apps/web/
|   |-- app/
|   |-- components/
|   |-- lib/
|   `-- tests/
|-- supabase/
|   |-- migrations/
|   `-- functions/
|-- scripts/
|-- tests/
`-- data/
    |-- baseline/
    `-- fixtures/
```

Ignored runtime state includes raw/processed/cache/private/debug data, Supabase temp files, web build output, and dependency folders. Do not treat generated runtime files as source unless the user asks.

## Development Commands

Install Python and web dependencies:

```bash
uv sync --extra dev
npm --prefix apps/web ci
```

Backend checks:

```bash
uv run --extra dev pytest -q
uv run --extra dev ruff check src/pci_realtime tests
uv run --extra dev ruff format --check src/pci_realtime tests
```

Web checks:

```bash
npm --prefix apps/web run typecheck
npm --prefix apps/web run lint
npm --prefix apps/web run test:e2e
```

CI runs Python tests on 3.11 and 3.12, Ruff, Next typecheck/lint/build, and Playwright e2e.

## Main Pipeline Commands

Seed Supabase paper anchors:

```bash
uv run --extra dev python -m pci_realtime.pipeline.seed_supabase --dry-run
uv run --extra dev python -m pci_realtime.pipeline.seed_supabase
```

Run the weekly registry loop:

```bash
uv run --extra dev python -m pci_realtime.pipeline.weekly_live \
  --start-date 2026-05-18 \
  --end-date 2026-05-24 \
  --confirm-cost \
  --fetch-markets \
  --fetch-polymarket
```

Use `--dry-run --output-path data/debug/weekly_live_payload.json` to inspect payloads without writing Supabase.

Run standalone market discovery:

```bash
uv run --extra dev python -m pci_realtime.pipeline.market_discovery --dry-run \
  --output-path data/debug/market_discovery_payload.json
uv run --extra dev python -m pci_realtime.pipeline.market_discovery
```

Use `--include-all-candidates` only for bounded absence audits; the normal production job persists eligible markets and near-miss candidates instead of every sports/crypto/noise market.
The scheduled default scans 5,000 open Kalshi markets plus 1,000 active Polymarket events. Raise `--polymarket-limit` only for one-off deeper absence checks.

Refresh outcomes and context:

```bash
uv run --extra dev python -m pci_realtime.pipeline.daily_refresh --supabase
```

Local all-in-one registry run:

```bash
./scripts/run_registry.sh
```

`run_registry.sh` sources `.env`, starts local Supabase if needed, seeds anchors, runs weekly ingest/scoring/market matching, optionally runs daily refresh, builds the web app, and serves it on port `8510` unless overridden.

## Environment Boundaries

Read `.env.example` for variable names. Do not print or copy secrets from `.env` or `.env.local`.

Important variables:

- LLM: `OPENAI_API_KEY`, `PCI_*_PROVIDER`, `PCI_SCREENING_MODEL`, `PCI_SCORING_MODEL`, `PCI_AUDIT_MODEL`, `PCI_LLM_RUN_COST_CEILING_USD`.
- Official sources: `CONGRESS_GOV_API_KEY`, `PROPUBLICA_CONGRESS_API_KEY`, `REGULATIONS_GOV_API_KEY`, `GOVINFO_API_KEY`, `FRED_API_KEY`, `EIA_API_KEY`, `COURTLISTENER_API_TOKEN`, `FEDERAL_REGISTER_USER_AGENT`.
- Supabase: `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SERVICE_ROLE_KEY`.
- Web: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`.
- Live trading: `PCI_ENABLE_LIVE_TRADING`, `KALSHI_API_KEY_ID`, `KALSHI_PRIVATE_KEY_PATH`, `KALSHI_PRIVATE_KEY`.

The browser must use only publishable/anon Supabase keys. Python registry writes require the service-role key. Public Kalshi and Polymarket market reads do not require private execution credentials.

## Data Contracts

Schema A is raw official documents, written as:

```text
data/raw/<source>/<source>_<YYYY-WW>.parquet
```

`pci_realtime.ingest.base.SCHEMA_A_COLUMNS`:

```text
doc_id, date, source, agency, title, body, body_truncated, url,
provisions_mentioned, ingested_at, ingestor_version
```

Schema B is scored document/provision deltas, written as:

```text
data/processed/scored/scored_<YYYY-WW>.parquet
```

`pci_realtime.scoring.scorer.SCHEMA_B_COLUMNS`:

```text
doc_id, provision, specificity_delta, durability_delta, enforceability_delta,
rationale, confidence, model, prompt_version, temperature, scored_at,
cached, cost_usd
```

Schema C is the weekly PCI series, normally materialized through registry rows and optionally as:

```text
data/processed/pci_weekly.parquet
```

`pci_realtime.pci.builder.SCHEMA_C_COLUMNS`:

```text
provision, week, pci, specificity, durability, enforceability,
n_docs, delta_this_week, updated_at
```

The baseline anchor is immutable repo data in `data/baseline/pci_baseline.csv`. It starts at `2022-W33` and tracks six provisions: `45X`, `45V`, `45Q`, `30D`, `50144`, `50141`.

## Python Backend Map

`src/pci_realtime/config.py`

- Central paths, tracked provisions, baseline PCI anchors, OBBBA deltas, provision keywords, source URLs, model defaults, and cost guardrails.

`src/pci_realtime/ingest/`

- `base.py`: shared Schema A enforcement, date parsing, sessions, HTML cleanup, provision keyword inference, parquet writing.
- `federal_register.py`: Federal Register API search/body normalization with allowed agency filtering.
- `treasury.py`: Treasury and IRS guidance page crawling.
- `congress.py`: Congress.gov legislative ingest with optional ProPublica fallback.
- `omb.py`: OMB memoranda ingest.
- `public_sources.py`: Regulations.gov, RegInfo/OIRA, USAspending, GovInfo, EIA, FRED, and CourtListener clients/context pieces.

`src/pci_realtime/scoring/`

- `screener.py`: structured LLM screening into `relevant`, `irrelevant`, or `ambiguous`.
- `scorer.py`: structured LLM scoring into dimension deltas in `[-2, 2]`, with cost ceiling and audit log.
- `cache.py`: stable JSON cache keys for screening/scoring.
- `prompts.py`: JSON schemas and prompt builders.
- `calibrate.py`: calibration set expansion and RMSE reporting. It blocks until verified Yikai-scored rows exist.

`src/pci_realtime/pci/builder.py`

- Validates baseline/scored data, aggregates weekly deltas, applies sticky weekly PCI updates, clips dimensions to `[1, 5]`, and can rebuild `pci_weekly.parquet`.

`src/pci_realtime/forecast_registry/`

- `policy.py`: provision metadata, market keywords, exposure channels, policy relevance and orientation helpers.
- `discovery.py`: market-candidate audit rows, policy/provision term matching, resolution clarity checks, and scan result contracts.
- `kalshi.py`: public Kalshi market reads, fixture parsing, signed order request construction, and execution gates.
- `polymarket.py`: read-only Polymarket Gamma event/market snapshots.
- `engine.py`: policy events -> signals -> market matches -> forecasts -> trade proposals/outcomes/metrics.
- `store.py`: Supabase REST client, public payload safety checks, seed rows, row adapters, and write ordering.
- `evidence.py`: source documents, evidence items, source links, source health rows.
- `context.py`: daily public context rows from EIA, FRED, CourtListener, RegInfo/OIRA, and USAspending.

`src/pci_realtime/pipeline/`

- `seed_supabase.py`: writes paper anchors.
- `weekly_live.py`: official ingest, scoring, PCI build, market scan, forecast/proposal generation, evidence rows, Supabase writes.
- `market_discovery.py`: standalone public Kalshi/Polymarket discovery with candidate/rejection audit rows.
- `daily_refresh.py`: reads open forecasts, refreshes market snapshots, writes outcomes/performance/context rows.

## Forecast And Trading Rules

Market snapshots are public/read-only. Forecasts blend:

```text
market prior: 0.60
PCI rule:    0.25
LLM/audit:   0.15
```

The default forecast client is an offline, paper-grounded heuristic. `StructuredLLMForecastClient` exists for structured public-evidence forecasting.

Trade proposals are not orders. `RiskLimits` enforce edge, spread, liquidity, confidence, policy relevance, clear resolution wording, public-only evidence, and exposure limits. `build_trade_proposals` returns only risk-passing proposals by default.

Actual Kalshi execution requires all of the following:

- `PCI_ENABLE_LIVE_TRADING=true`.
- Risk checks passed.
- Proposal id explicitly approved in an approval file.
- Kalshi credentials present.
- A caller passes `--send` to the Kalshi CLI path.

Never weaken these gates or expose signed request payloads in public web data.

## Supabase Contract

Migrations live in `supabase/migrations/`.

Core tables:

```text
provisions, pipeline_runs, scored_deltas, pci_weekly, policy_events, market_snapshots,
market_discovery_candidates, forecasts, trade_proposals, forecast_outcomes,
source_documents, evidence_items, source_links, source_health
```

Public views:

```text
v_current_pci, v_provision_timelines, v_policy_events, v_open_forecasts,
v_resolved_forecasts, v_market_snapshots, v_market_discovery_candidates,
v_trade_proposals, v_forecast_performance, v_pipeline_status,
v_source_documents, v_evidence_items, v_source_links, v_source_health
```

Public forecast/proposal views deliberately require:

- `f.private_info_used = false`
- `reasoning -> match -> policy_relevant = true`
- `reasoning -> match -> resolution_clear = true`

`v_market_snapshots` filters to `policy_relevant = true`. `v_market_discovery_candidates` exposes the latest public near-misses and eligible candidates so a zero-forecast run can be audited. Tests assert these filters and contracts exist. If changing migrations, update the Python row adapters and web TypeScript types together.

## Web App Map

`apps/web` is a Next 16 / React 19 read-only frontend.

Routes:

- `/`: live tracker landing page using Supabase public views.
- `/dashboard`: interactive tracker dashboard.
- `/about`: paper companion page.

Key files:

- `apps/web/lib/data.ts`: typed public-view fetcher. Reads only public/publishable Supabase keys and paginates REST view results.
- `apps/web/lib/market-model.ts`: merges forecasts, market snapshots, policy rows, resolved rows, and source counts into UI-ready `PolicyMarket` rows.
- `apps/web/lib/policy-copy.ts`: policy-specific display copy.
- `apps/web/components/registry-dashboard.tsx`: dashboard filters, search, KPIs, cards/table/detail.
- `apps/web/components/market/*`: market cards, tables, details, activity, source health, policy trends, formatting.
- `apps/web/tests/e2e/mock-supabase.mjs`: local mock Supabase REST server for Playwright.

Do not expose the word `supabase` in rendered public pages; e2e tests check for that. The UI copy should stay product-facing rather than implementation-facing.

## Tests By Area

Backend:

- `tests/test_base_ingestor.py`: Schema A basics.
- `tests/test_federal_register.py`, `test_treasury.py`, `test_omb.py`, `test_congress.py`, `test_public_sources.py`: source normalization and public client behavior.
- `tests/test_screener.py`, `test_scorer.py`, `test_scoring_cache.py`, `test_calibrate.py`: LLM parsing, caching, scoring contracts, calibration gates.
- `tests/test_builder.py`: sticky PCI weekly index and clipping/decay.
- `tests/test_forecast_registry.py`: signal generation, market parsing/matching, forecasts, outcomes, risk gates, public payload safety.
- `tests/test_weekly_live.py`: weekly payload materialization and Supabase write semantics.
- `tests/test_daily_refresh.py`: Supabase daily refresh write behavior.
- `tests/test_supabase_contract.py`: public-view privacy/relevance filters.

Web:

- `apps/web/tests/e2e/registry.spec.ts`: landing, about, and dashboard behavior using mock Supabase.
- `apps/web/playwright.config.ts`: starts mock Supabase on `127.0.0.1:8787` and Next dev on `127.0.0.1:8511`.

## Source And Evidence Layer

The evidence layer turns raw public docs and public market snapshots into:

- `source_documents`: normalized public document/market source metadata.
- `evidence_items`: snippets or rationale tied to provisions and dimensions.
- `source_links`: trace links to policy events, forecasts, and market snapshots.
- `source_health`: per-source success/disabled/failed state with row counts and errors.

`daily_refresh` also builds public context rows from EIA, FRED, CourtListener, RegInfo/OIRA, and USAspending. Missing optional keys and source failures should be represented through source-health rows rather than breaking the whole refresh when the source is non-critical.

## Cost And Live Data Behavior

The scorer estimates cost as:

```text
n_docs * (1 + len(TRACKED_PROVISIONS)) * SCORING_ESTIMATED_COST_PER_CALL_USD
```

If the estimate exceeds `PCI_LLM_RUN_COST_CEILING_USD`, a live scoring run must pass `--confirm-cost`.

`weekly_live.run_official_ingest` degrades non-core source failures to source-health rows, but if all requested core policy sources fail it raises. Core policy sources are Federal Register, Congress, Regulations.gov, and RegInfo/OIRA.

## Cloud And Scheduling

GitHub workflows:

- `.github/workflows/ci.yml`: tests/lint/web checks.
- `.github/workflows/production-registry-pipeline.yml`: scheduled Monday finalized weekly loop plus weekday rolling live ingest.
- `.github/workflows/production-market-discovery.yml`: scheduled six-hour public market scan and candidate audit.
- `.github/workflows/production-registry-refresh.yml`: scheduled six-hour daily refresh.

Supabase functions:

- `trigger-weekly-pipeline`: proxies a weekly request to `PYTHON_PIPELINE_WEBHOOK_URL`.
- `trigger-daily-refresh`: proxies a daily refresh request.
- Both public Edge Function triggers require `x-pci-pipeline-secret` matching `PYTHON_PIPELINE_TRIGGER_SECRET` or `PYTHON_PIPELINE_WEBHOOK_SECRET`.

Vercel serves `apps/web`; it should receive only public Supabase URL/key values.

## Working Rules For Agents

- Check `git status --short --branch` before edits. This repo may be dirty; do not revert user changes.
- Prefer `rg` / `rg --files` for discovery.
- Use `uv run --extra dev ...` for Python commands unless the repo pattern clearly uses plain `python`.
- Use `npm --prefix apps/web ...` for web commands from repo root.
- Do not inspect or print `.env` or `.env.local` values.
- Do not edit immutable baseline/fixture data unless explicitly asked and tests/docs are updated.
- Keep Schema A/B/C, Supabase migrations, row adapters, TypeScript types, and tests aligned.
- Keep public payloads clean: no API key names or OpenAI-style `sk-*` secrets, `KALSHI_PRIVATE_KEY`, `raw_response`, private company identifiers, local `/Users/` paths, or signed trade data.
- Do not add fake forecasts when there are no eligible signals or markets. Tests expect baseline-only runs to produce no synthetic forecasts/proposals.
- Treat `apps/web/node_modules`, `.next`, `.venv`, `.pytest_cache`, `.ruff_cache`, `data/raw`, `data/processed`, `data/cache`, `data/debug`, and `data/private` as generated or local state.

## Common Safe Workflows

Dry-run weekly payload with fixtures or live public reads:

```bash
uv run --extra dev python -m pci_realtime.pipeline.weekly_live \
  --start-date 2026-05-18 \
  --end-date 2026-05-24 \
  --confirm-cost \
  --fetch-markets \
  --dry-run \
  --output-path data/debug/weekly_live_payload.json
```

Rebuild only the weekly PCI parquet from scored files:

```bash
uv run --extra dev python -m pci_realtime.pci.builder --rebuild
```

Run focused tests after backend contract changes:

```bash
uv run --extra dev pytest -q tests/test_weekly_live.py tests/test_supabase_contract.py tests/test_forecast_registry.py
```

Run focused web checks after UI/data changes:

```bash
npm --prefix apps/web run typecheck
npm --prefix apps/web run lint
npm --prefix apps/web run test:e2e
```
