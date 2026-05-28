# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

`AGENT.md` is the canonical, deeply detailed orientation for agents in this repo. Read it before non-trivial work — it covers Schema A/B/C, the Python module map, Supabase public-view contracts, web app structure, and working rules. This file holds only the short-form commands and the orientation Claude Code needs first.

## Top-Level Architecture

The repo is **Python backend + Next.js web app + Supabase registry**, glued together by `pci_realtime.pipeline.*` entry points.

```text
official policy documents
  -> relevance screening   (pci_realtime.scoring.screener)
  -> PCI delta scoring     (pci_realtime.scoring.scorer)
  -> weekly sticky PCI     (pci_realtime.pci.builder)
  -> market discovery      (pci_realtime.forecast_registry.discovery + kalshi/polymarket)
  -> forecast registry     (pci_realtime.forecast_registry.engine)
  -> gated trade proposal  (gated by --send + approval file + PCI_ENABLE_LIVE_TRADING)
  -> outcome tracking      (pci_realtime.pipeline.daily_refresh)
```

Three pipeline modules own everything:

| Module | Role |
|---|---|
| `pci_realtime.pipeline.weekly_live` | Full weekly loop: ingest → score → PCI → market scan → forecasts/proposals → evidence rows → Supabase writes. Defaults to `--evidence-mode audit` (caches HTTP, builds chunks, writes shadow evidence rows, does NOT change scores). |
| `pci_realtime.pipeline.market_discovery` | Standalone Kalshi (5k open markets default) + Polymarket (1k active events default) scan with eligible-and-near-miss audit rows. |
| `pci_realtime.pipeline.daily_refresh` | Reads open forecasts, refreshes market snapshots, writes outcomes/performance/public context rows. |

Trading is backend-only and **fail-closed**: live execution requires `PCI_ENABLE_LIVE_TRADING=true` + risk checks passed + proposal id in an approval file + Kalshi credentials + `--send`. Never weaken these gates.

The web app at `apps/web/` is read-only — it reads Supabase **public views** (e.g. `v_current_pci`, `v_open_forecasts`, `v_market_snapshots`) using only the publishable/anon key. Service-role writes happen only from Python.

## Schema Contracts (kept aligned across Python ↔ Supabase ↔ TypeScript)

If you change any of these, update Python row adapters, Supabase migrations, and `apps/web/lib/data.ts` types together.

- **Schema A** raw docs: `data/raw/<source>/<source>_<YYYY-WW>.parquet`. Columns enforced by `pci_realtime.ingest.base.SCHEMA_A_COLUMNS`.
- **Schema B** scored deltas: `data/processed/scored/scored_<YYYY-WW>.parquet`. Columns in `pci_realtime.scoring.scorer.SCHEMA_B_COLUMNS`. Deltas are dimension-level in `[-2, +2]`.
- **Schema C** weekly PCI: `data/processed/pci_weekly.parquet`. Columns in `pci_realtime.pci.builder.SCHEMA_C_COLUMNS`. PCI is sticky and clipped to `[1, 5]`.
- **Baseline anchor**: `data/baseline/pci_baseline.csv`. Immutable repo data starting `2022-W33`, six provisions: `45X`, `45V`, `45Q`, `30D`, `50144`, `50141`. Do not edit without explicit ask.

## Development Commands

Install:

```bash
uv sync --extra dev
npm --prefix apps/web ci
```

Backend checks (run after Python changes):

```bash
uv run --extra dev pytest -q
uv run --extra dev ruff check src/pci_realtime tests
uv run --extra dev ruff format --check src/pci_realtime tests
```

Single backend test file or pattern:

```bash
uv run --extra dev pytest -q tests/test_weekly_live.py
uv run --extra dev pytest -q -k "discovery and polymarket"
```

After backend contract changes, run the contract-sensitive trio:

```bash
uv run --extra dev pytest -q tests/test_weekly_live.py tests/test_supabase_contract.py tests/test_forecast_registry.py
```

Web checks (run after `apps/web/` changes):

```bash
npm --prefix apps/web run typecheck
npm --prefix apps/web run lint
npm --prefix apps/web run test:e2e
```

E2E uses a mock Supabase server (`apps/web/tests/e2e/mock-supabase.mjs`) on `127.0.0.1:8787` and Next dev on `127.0.0.1:8511` — both auto-started by `playwright.config.ts`. To run against a real Supabase instance use `npm --prefix apps/web run test:e2e:live` (config: `playwright.live.config.ts`).

Single Playwright test:

```bash
npm --prefix apps/web exec playwright test tests/e2e/registry.spec.ts -g "dashboard"
```

CI (`.github/workflows/ci.yml`) runs Python tests on 3.11 and 3.12, Ruff, Next typecheck/lint/build, and Playwright.

## Pipeline Commands

Seed Supabase paper anchors:

```bash
uv run --extra dev python -m pci_realtime.pipeline.seed_supabase --dry-run
uv run --extra dev python -m pci_realtime.pipeline.seed_supabase
```

Weekly registry loop (live):

```bash
uv run --extra dev python -m pci_realtime.pipeline.weekly_live \
  --start-date 2026-05-18 --end-date 2026-05-24 \
  --confirm-cost --fetch-markets --fetch-polymarket
```

Inspect payload without writing Supabase:

```bash
uv run --extra dev python -m pci_realtime.pipeline.weekly_live \
  --start-date 2026-05-18 --end-date 2026-05-24 \
  --confirm-cost --fetch-markets --dry-run \
  --output-path data/debug/weekly_live_payload.json
```

`--confirm-cost` is required when estimated cost (`n_docs * (1 + len(TRACKED_PROVISIONS)) * SCORING_ESTIMATED_COST_PER_CALL_USD`) exceeds `PCI_LLM_RUN_COST_CEILING_USD`. `--evidence-mode off` disables the audit layer for debugging.

Standalone market discovery:

```bash
uv run --extra dev python -m pci_realtime.pipeline.market_discovery
```

Rebuild only the weekly PCI parquet from scored files:

```bash
uv run --extra dev python -m pci_realtime.pci.builder --rebuild
```

Local all-in-one (sources `.env`, runs full stack, builds web, serves on `:8510`):

```bash
./scripts/run_registry.sh
```

## Critical Working Rules

These are non-obvious and break things if violated. Most of them are enforced by tests.

- **Public-view privacy filters.** Public forecast/proposal views require `private_info_used = false`, `reasoning -> match -> policy_relevant = true`, and `reasoning -> match -> resolution_clear = true`. `v_market_snapshots` filters to `policy_relevant = true`. `tests/test_supabase_contract.py` asserts this.
- **No `supabase` token in rendered public pages.** E2E tests check that the string never appears in landing/dashboard markup. Keep UI copy product-facing.
- **No fake forecasts on empty baseline runs.** Tests expect baseline-only runs to produce no synthetic forecasts/proposals when there are no eligible signals or markets.
- **Live trading gates are fail-closed.** All five conditions (`PCI_ENABLE_LIVE_TRADING=true` + risk pass + approval-file proposal id + Kalshi credentials + `--send`) must hold. Never weaken.
- **Browser uses publishable key only.** `apps/web/lib/data.ts` reads `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`. Service-role key (`SUPABASE_SERVICE_ROLE_KEY`) is Python-only.
- **Core ingest failures are hard, others degrade.** `weekly_live.run_official_ingest` raises only when ALL of Federal Register, Congress, Regulations.gov, and RegInfo/OIRA fail. Other source failures become `source_health` rows.
- **Don't print or copy `.env` / `.env.local` values.** Use names from `.env.example` when referring to vars.
- **Don't edit `data/baseline/` or `data/fixtures/`** without explicit user ask + matching test/doc updates.
- **Treat as generated state:** `apps/web/node_modules`, `apps/web/.next`, `.venv`, `.pytest_cache`, `.ruff_cache`, `data/raw`, `data/processed`, `data/cache`, `data/debug`, `data/private`.
- **Public payload safety.** Never leak: API key names, `sk-*` style secrets, `KALSHI_PRIVATE_KEY`, raw model responses, private firm identifiers, `/Users/` paths, signed trade payloads.

## Deeper References

- **`AGENT.md`** — full Python backend map, Supabase contract, web file map, evidence/source layer, cloud scheduling. Read this before non-trivial changes.
- **`README.md`** — product-facing description, PCI methodology, capability status, cloud provisioning steps (Vercel/Supabase CLI).
- **`.env.example`** — canonical list of environment variables with comments.
- **`supabase/migrations/`** — Supabase schema source of truth. `supabase/functions/` are fail-closed Edge Function triggers (require `x-pci-pipeline-secret`).
- **`.github/workflows/`** — `production-registry-pipeline.yml` (weekly Monday + weekday rolling ingest), `production-market-discovery.yml` (6h), `production-registry-refresh.yml` (6h), `production-smoke.yml` (smoke against `pcindex.vercel.app`).
