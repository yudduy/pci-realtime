# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Policy Credibility Index (PCI) registry: a Python backend turns official federal policy documents into a cited policy-change ledger and weekly PCI scores for six IRA provisions (`45X`, `45V`, `45Q`, `30D`, `50144`, `50141`), written to Supabase. A read-only Next.js app (`apps/web`, deployed at pcindex.vercel.app) renders the registry. Supabase is the boundary between the two halves: Python pipelines write tables with the service-role key; the web app reads only public `v_*` views from the browser with the publishable key.

Product direction (2026-07): the product is the cited policy-change ledger with push delivery, organized by climate-tech verticals (verticals are the first-class domain in UI/feeds/MCP; provisions are the scoring unit underneath). The prediction-market/forecast/trade-proposal layer was deleted in 2026-07 — never reintroduce market/forecast framing.

## Commands

Backend (Python ≥3.10; `uv run --extra dev` resolves the env from `uv.lock`, no separate install step):

```bash
uv run --extra dev pytest -q                        # full suite — offline, ~5s
uv run --extra dev pytest tests/test_scorer.py -q   # one file
uv run --extra dev pytest -k weekly_live -q         # by keyword
uv run --extra dev ruff check src/pci_realtime tests
uv run --extra dev ruff format --check src/pci_realtime tests
```

Web (`apps/web`, Next.js 16 / React 19 / Tailwind 4):

```bash
npm --prefix apps/web ci
npm --prefix apps/web run typecheck
npm --prefix apps/web run lint            # --max-warnings=0
npm --prefix apps/web run test:e2e       # Playwright; boots its own mock Supabase (:8787) + next dev (:8511) — no env needed
npm --prefix apps/web run test:e2e:live  # against production
```

Pipeline entry points (need `.env` — `cp .env.example .env`; prefer `--dry-run` first):

```bash
python -m pci_realtime.pipeline.seed_supabase --dry-run       # paper baseline + OBBBA anchors
python -m pci_realtime.pipeline.weekly_live --start-date 2026-05-18 --end-date 2026-05-24 \
  --confirm-cost                                              # full weekly ledger loop
python -m pci_realtime.pipeline.daily_refresh --dry-run       # public-context + source-health refresh
uv run --extra dev python -m pci_realtime.mcp_server          # local MCP (stdio; streamable-http via PCINDEX_MCP_TRANSPORT)
./scripts/run_registry.sh                                     # whole loop + web build/serve (requires OPENAI + CONGRESS_GOV keys)
```

The `pci` typer CLI (`pci_realtime.cli:app`) wraps the same service layer: `pci status`, `pci policies`, ….

No CI/CD workflows ship with the repo — run the checks above locally; registry commands run manually from a trusted environment.

## Architecture

Backend flow, one stage per package under `src/pci_realtime/`:

```text
ingest/           federal_register, treasury, congress (Congress.gov primary),
                  omb, public_sources → data/raw/<source>/<source>_<YYYY-WW>.parquet
scoring/          screener (LLM relevance filter) → scorer (dimension deltas in [-2,+2])
                  → data/processed/scored/scored_<YYYY-WW>.parquet
pci/builder       sticky weekly index: previous PCI + mean of dimension deltas, clipped to [1,5]
                  → data/processed/pci_weekly.parquet
forecast_registry/ registry spine: store.py (SupabaseRestClient — plain httpx REST, not supabase-py;
                  UPSERT_CONFLICT_KEYS is the single source of table conflict keys),
                  evidence.py (evidence/source-link/source-health row builders),
                  context.py (macro context: EIA/FRED/CourtListener/reginfo/USAspending)
```

The parquet paths are file-level contracts between stages; tests and offline runs depend on them. `data/raw|processed|cache|private|debug` are gitignored runtime state.

Orchestrators in `pipeline/`: `weekly_live` owns the full ledger loop (ingest → screen → score → PCI → policy_events/evidence/source_health rows); `daily_refresh` refreshes public context + source health; `seed_supabase` writes the paper anchors. The nine ledger tables written: provisions, pci_weekly, policy_events, scored_deltas, source_documents, evidence_items, source_links, source_health, pipeline_runs.

`service.py` is the shared agent-facing service layer with typed errors (`service_errors.py`); `cli.py`, `mcp_server.py` (FastMCP, read + write tools), and `scripts/` all consume it. The hosted read-only MCP at `/mcp` is a separate TypeScript implementation (`apps/web/app/mcp/route.ts` via `mcp-handler`) reading the same public views — changes to the tool surface may need mirroring in both.

Shared constants live in `config.py`: `TRACKED_PROVISIONS`, `BASELINE_PCI`, OBBBA deltas, provision keywords, and LLM routing (screening/scoring/audit tiers via `PCI_*` env vars). `env.py:load_local_env()` parses `.env` itself — python-dotenv is not a dependency.

LLM responses are cached under `data/cache` (`scoring/cache.py`), keyed by prompt + schema version. Tests run fully offline against `data/fixtures/`.

Supabase migrations are ordered SQL in `supabase/migrations/` (001–005). Migration 005 gates agent evidence intake (`agent_runs`, `evidence_submissions`); `service.status()` reports `agent_intake_configured` from it. Supabase Edge Functions only forward fail-closed webhook triggers to an external Python runner — they never run the pipeline themselves.

## Guardrails

- Nothing private in public views: `forecast_registry/store.py` enforces `FORBIDDEN_PUBLIC_STRINGS`/`FORBIDDEN_PUBLIC_PATTERNS` (API keys, `raw_response`, private paths, firm data) on rows bound for Supabase. New write paths must stay behind this check.
- LLM runs abort above `PCI_LLM_RUN_COST_CEILING_USD` unless `--confirm-cost` is passed.
- PCI updates come only from scored official documents; general news scraping is intentionally out of scope for the index.
- `SUPABASE_SERVICE_ROLE_KEY` is server-side only. The browser gets only `NEXT_PUBLIC_SUPABASE_URL` + `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`.
