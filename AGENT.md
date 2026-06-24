# AGENT.md

Repository orientation for agents working on `pci-realtime`.

Last repo survey: 2026-06-23.

## Purpose

This repo implements a Policy Credibility Index (PCI) registry for IRA-related climate policy provisions. It ingests official public policy documents, screens and scores document-level PCI deltas, builds a sticky weekly PCI time series, tracks reviewed policy-source leads, and exposes a read-only public web app backed by Supabase views.

The public app is a research companion. It must never place trades, expose private execution payloads, leak API keys, publish raw model responses, or include private firm-level data.

Canonical production URL: `https://pcindex.vercel.app`.

## Product Loop

The intended loop is:

```text
official policy documents
  -> relevance screening
  -> PCI delta scoring
  -> weekly PCI series
  -> source documents / evidence links / source health
reviewed public leads
  -> policy discovery
  -> governed evidence promotion
  -> quote-verified policy evidence
```

`pci_realtime.pipeline.weekly_live` owns the weekly official-source path. `pci_realtime.pipeline.policy_discovery` owns source-lead review and promotion support. Supabase Edge Functions only proxy to an external Python runner; they do not run the pandas/parquet/LLM pipeline themselves.

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

Run these checks manually before shipping relevant changes.

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
  --confirm-cost
```

Use `--dry-run --output-path data/debug/weekly_live_payload.json` to inspect payloads without writing Supabase.

Run policy source discovery:

```bash
uv run --extra dev python -m pci_realtime.pipeline.policy_discovery \
  --since 2026-06-01 \
  --dry-run \
  --output-path data/debug/policy_discovery_payload.json
```

Local all-in-one registry run:

```bash
./scripts/run_registry.sh
```

`run_registry.sh` sources `.env`, starts local Supabase if needed, seeds anchors, runs weekly ingest/scoring, builds the web app, and serves it on port `8510` unless overridden.

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

- `policy.py`: provision metadata, policy keywords, exposure channels, relevance and orientation helpers.
- `discovery.py`, `kalshi.py`, `polymarket.py`, `engine.py`: legacy market/forecast compatibility helpers. They are not part of the default policy-desk pipeline.
- `store.py`: Supabase REST client, public payload safety checks, seed rows, row adapters, and write ordering.
- `evidence.py`: source documents, evidence items, source links, source health rows.
- `context.py`: optional public context rows from EIA, FRED, CourtListener, RegInfo/OIRA, and USAspending.

`src/pci_realtime/pipeline/`

- `seed_supabase.py`: writes paper anchors.
- `weekly_live.py`: official ingest, scoring, PCI build, evidence/source rows, source health, Supabase writes.
- `policy_discovery.py`: official-source and web-search lead discovery, source-health rows, candidate review, and governed promotion commands.

Agent evidence automation:

- `src/pci_realtime/agent_research.py`: OpenAI web-search scout restricted by default to official public domains. It returns structured `EvidenceCandidate` rows with policy code, source metadata, exact quote, claim, evidence type, and stable idempotency key.
- `scripts/run_agent_research_intake.py`: CLI wrapper for the scout. Default mode is dry-run JSON output. `--write` submits candidates only after `service.status().write_configured` is true.
- `src/pci_realtime/agent_intake.py`: validates tracked policy units, canonicalizes public URLs, rejects private hosts and missing quotes, scores cited evidence, builds agent runs, submissions, source docs, evidence items, scored deltas, policy events, PCI weekly rows, and source links.
- `src/pci_realtime/service.py`: agent-facing read/write service. It dedupes by idempotency-key hash, loads historical scored deltas before recomputing PCI rows, writes in dependency order, and reports missing migration `005` cleanly.
- `src/pci_realtime/mcp_server.py`: local write-capable MCP tools plus read tools. Hosted `/mcp` in `apps/web/app/mcp/route.ts` is read-only.

## Legacy Forecast And Trading Compatibility

Forecast/trading tables and helpers remain for schema and regression compatibility, but they are not product-facing and the default policy-desk pipeline must not create new forecast, outcome, market-snapshot, or trade-proposal rows. Markets, where used manually, are read-only context and never make evidence ready or imply a trading edge.

Trade proposals, if exercised in a manual legacy path, are not orders. `RiskLimits` enforce edge, spread, liquidity, confidence, policy relevance, clear resolution wording, public-only evidence, and exposure limits.

Actual Kalshi execution requires all of the following:

- `PCI_ENABLE_LIVE_TRADING=true`.
- Risk checks passed.
- Proposal id explicitly approved in an approval file.
- Kalshi credentials present.
- A caller passes `--send` to the Kalshi CLI path.

Never weaken these gates or expose signed request payloads in public web data.

## Supabase Contract

Migrations live in `supabase/migrations/`.

Active product tables:

```text
provisions, pipeline_runs, scored_deltas, pci_weekly, policy_events,
policy_source_candidates, source_documents, evidence_items, source_links,
source_health, agent_runs, evidence_submissions
```

Legacy compatibility tables include `market_snapshots`, `market_discovery_candidates`, `forecasts`, `trade_proposals`, `forecast_outcomes`, `policy_theses`, `belief_updates`, and `policy_briefs`; do not drop them without a consumer/data audit.

Active public views:

```text
v_current_pci, v_provision_timelines, v_policy_events, v_pipeline_status,
v_policy_source_candidates, v_source_documents, v_evidence_items,
v_policy_evidence_items, v_source_links, v_source_health,
v_agent_evidence_submissions
```

Public forecast/proposal views deliberately require:

- `f.private_info_used = false`
- `reasoning -> match -> policy_relevant = true`
- `reasoning -> match -> resolution_clear = true`

Legacy forecast/market views keep their public filters for compatibility. The public web read model should prefer verified policy evidence, reviewed source candidates, and source freshness over legacy market attachment. If changing migrations, update the Python row adapters and web TypeScript types together.

## Web App Map

`apps/web` is a Next 16 / React 19 read-only frontend.

Routes:

- `/`: live tracker landing page using Supabase public views.
- `/dashboard`: interactive tracker dashboard.
- `/about`: paper companion page.

Key files:

- `apps/web/lib/data.ts`: typed public-view fetcher. Reads only public/publishable Supabase keys and paginates REST view results.
- `apps/web/lib/intelligence.ts`: builds source-led policy status from PCI rows, reviewed leads, verified evidence, source health, and pipeline runs.
- `apps/web/lib/policy-dossier.ts`: builds policy detail pages from verified evidence, reviewed leads, and ledger Q&A.
- `apps/web/lib/terminal-data.ts`: builds the current desk feed and policy timeline data.
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
- `tests/test_forecast_registry.py`: legacy market/forecast helper contracts and public payload safety.
- `tests/test_weekly_live.py`: weekly payload materialization and Supabase write semantics.
- `tests/test_policy_discovery.py`: source discovery, candidate review, and governed promotion behavior.
- `tests/test_agent_intake.py`, `test_agent_research.py`: governed evidence intake and official-source scout behavior.
- `tests/test_supabase_contract.py`: public-view privacy/relevance filters.

Web:

- `apps/web/tests/e2e/registry.spec.ts`: landing, about, and dashboard behavior using mock Supabase.
- `apps/web/playwright.config.ts`: starts mock Supabase on `127.0.0.1:8787` and Next dev on `127.0.0.1:8511`.

## Source And Evidence Layer

The evidence layer turns raw public docs and governed source submissions into:

- `source_documents`: normalized public document source metadata.
- `evidence_items`: snippets or rationale tied to provisions and dimensions.
- `source_links`: trace links to policy events and verified evidence.
- `source_health`: per-source success/disabled/failed state with row counts and errors.

Missing optional keys and non-critical source failures should be represented through source-health rows rather than breaking the whole refresh when the source is non-critical.

## Automated Research Scout

The backend can support an automatic evidence-scout loop without adding GitHub
Actions:

```text
external cron / trusted worker / supervised Codex automation
  -> uv run --extra dev python scripts/run_agent_research_intake.py --since <date> --output-path data/debug/agent_research_intake.json
  -> human or narrow agent review of exact quotes and policy mapping
  -> rerun with --write only when status.write_configured is true
  -> get_evidence_trace and policy_dossier verify the promoted evidence
```

Codex, Claude Code, Omnigent, or a similar agent should be treated as a research
operator or parser, not as the source of truth. It may search the web, parse
official updates, and prepare submissions, but the accepted write path is still
`submit_policy_evidence` through the local MCP/service layer. Production writes
need server-side `SUPABASE_SERVICE_ROLE_KEY` and `OPENAI_API_KEY`; hosted write
access is intentionally absent until scoped auth, rate limits, and submitter
audit are designed.

Use news only as a lead to primary evidence. PCI is not a news sentiment index:
score movement requires a public, citeable policy source with an exact quote or
visible section anchor. If an item only has commentary or unattributed claims,
keep it in review/context and do not promote it to `scored_deltas`.

The "automatic rendering" path is data-driven. Backend jobs write Supabase rows,
public views filter and sanitize them, and the Next.js app renders current state
from those views. There is no separate static render artifact to regenerate for
normal updates.

## Cost And Live Data Behavior

The scorer estimates cost as:

```text
n_docs * (1 + len(TRACKED_PROVISIONS)) * SCORING_ESTIMATED_COST_PER_CALL_USD
```

If the estimate exceeds `PCI_LLM_RUN_COST_CEILING_USD`, a live scoring run must pass `--confirm-cost`.

`weekly_live.run_official_ingest` degrades non-core source failures to source-health rows, but if all requested core policy sources fail it raises. Core policy sources are Federal Register, Congress, Regulations.gov, and RegInfo/OIRA.

## Cloud And Scheduling

GitHub Actions CI/CD workflows are intentionally not configured in this repository. Run checks and production registry commands manually from a trusted local or server environment, or attach an external scheduler outside the repo when needed.

Recommended external scheduled jobs:

- Weekly official-source pipeline: `pci_realtime.pipeline.weekly_live` with cost confirmation.
- Policy source discovery: `pci_realtime.pipeline.policy_discovery --since <date>` dry-run first, then reviewed writes.
- Agent evidence scout: `scripts/run_agent_research_intake.py` dry-run first, then governed writes only after readiness checks and review.

Supabase functions:

- `trigger-weekly-pipeline`: proxies a weekly request to `PYTHON_PIPELINE_WEBHOOK_URL`.
- Public Edge Function triggers require `x-pci-pipeline-secret` matching `PYTHON_PIPELINE_TRIGGER_SECRET` or `PYTHON_PIPELINE_WEBHOOK_SECRET`.

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
- Do not add fake forecasts, market snapshots, or trade proposals to the default policy desk path.
- Treat `apps/web/node_modules`, `.next`, `.venv`, `.pytest_cache`, `.ruff_cache`, `data/raw`, `data/processed`, `data/cache`, `data/debug`, and `data/private` as generated or local state.

## Common Safe Workflows

Dry-run weekly payload with fixtures or live public reads:

```bash
uv run --extra dev python -m pci_realtime.pipeline.weekly_live \
  --start-date 2026-05-18 \
  --end-date 2026-05-24 \
  --confirm-cost \
  --dry-run \
  --output-path data/debug/weekly_live_payload.json
```

Dry-run policy source discovery:

```bash
uv run --extra dev python -m pci_realtime.pipeline.policy_discovery \
  --since 2026-06-01 \
  --dry-run \
  --output-path data/debug/policy_discovery_payload.json
```

Rebuild only the weekly PCI parquet from scored files:

```bash
uv run --extra dev python -m pci_realtime.pci.builder --rebuild
```

Run focused tests after backend contract changes:

```bash
uv run --extra dev pytest -q tests/test_weekly_live.py tests/test_policy_discovery.py tests/test_supabase_contract.py
```

Run focused web checks after UI/data changes:

```bash
npm --prefix apps/web run typecheck
npm --prefix apps/web run lint
npm --prefix apps/web run test:e2e
```
