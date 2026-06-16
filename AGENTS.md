# Repository Guidelines

## Project Structure & Module Organization

This repository implements the Policy Credibility Index registry. Python source lives in `src/pci_realtime/`, organized by `ingest/`, `scoring/`, `pci/`, `forecast_registry/`, and `pipeline/`. Backend tests live in `tests/`. The read-only Next.js app is in `apps/web/`, with routes in `app/`, shared UI in `components/`, data helpers in `lib/`, and Playwright tests in `tests/`. Supabase migrations and edge functions are in `supabase/`. Committed reference data is in `data/baseline/` and `data/fixtures/`; generated `data/raw`, `data/processed`, `data/cache`, `data/debug`, and `data/private` outputs are ignored.

## Build, Test, and Development Commands

Install dependencies with:

```bash
uv sync --extra dev
npm --prefix apps/web ci
```

Run backend checks:

```bash
uv run --extra dev pytest -q
uv run --extra dev ruff check src/pci_realtime tests
uv run --extra dev ruff format --check src/pci_realtime tests
```

Run web checks:

```bash
npm --prefix apps/web run typecheck
npm --prefix apps/web run lint
npm --prefix apps/web run test:e2e
```

Use `./scripts/run_registry.sh` for the local end-to-end registry run.

## Coding Style & Naming Conventions

Use Python 3.10+ and keep modules snake_case. Prefer typed, small functions that preserve the existing schema contracts. Format Python with Ruff and keep imports lint-clean. Frontend code is TypeScript/React with Next.js App Router conventions: component files are kebab-case under `components/`, exported components use PascalCase, and helpers stay in `apps/web/lib/`.

## Testing Guidelines

Pytest discovers backend tests from `tests/test_*.py`; add focused unit tests near the behavior changed. Playwright e2e tests live under `apps/web/tests/e2e/` and run against the mock Supabase server configured in `apps/web/playwright.config.ts`. Do not require real API keys in normal CI tests; gate live checks behind explicit environment variables.

## Commit & Pull Request Guidelines

Follow the existing history: concise imperative subjects such as `Add auditable market discovery coverage`, with optional scopes like `web:` or `scoring:`. PRs should describe the behavior change, list commands run, link issues when relevant, and include screenshots for visible UI changes.

## Security & Configuration Tips

Copy `.env.example` to `.env` locally, but never commit secrets. Public web code may use only publishable Supabase keys. Keep private order payloads, raw model responses, API keys, local `/Users/` paths, and signed trading data out of public views and fixtures. See `MCP.md` for agent intake setup.
