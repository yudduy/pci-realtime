# PCI Real-Time Monitor

Real-time **Policy Credibility Index** (PCI) monitor for key Inflation Reduction Act (IRA) climate provisions. Ingests federal policy documents weekly, scores their effect on policy credibility with LLMs, and publishes a weekly time series of provision-level PCI scores via a Streamlit dashboard.

> **Status:** Active build, Phase 0 + 1 complete (Apr 23, 2026). See `CLAUDE.md` for the full status board and two-RA track ownership.

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
| Second author / infrastructure | **Austin** | additional ingestors (`src/pci_realtime/ingest/`), time-series builder (`src/pci_realtime/pci/`), Streamlit dashboard, GHA cron |
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
│   ├── pci/                 # Austin owns — builder + validation
│   └── dashboard/           # Austin owns — Streamlit app
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
```

## Hand-off contracts

The three module boundaries are locked schemas in `docs/interfaces.md`:

1. `ingest/` → `scoring/` — raw document parquet
2. `scoring/` → `pci/builder.py` — scored deltas parquet
3. `pci/` → `dashboard/` — weekly PCI time series parquet

Either Austin or Duy can change a column ONLY via PR with both as reviewers and Yikai signoff.

## Phase status

| Phase | Status | Owner | Output |
|---|---|---|---|
| 0 — Scoring spec | ✅ done | Duy | `docs/phase0_scoring_spec.md` |
| 1 — Federal Register ingestion | ✅ done (POC week) | Duy | `src/pci_realtime/ingest/federal_register.py` |
| 1 ext — Treasury / Congress / OMB ingestors | ✅ done (scaffold) | Austin | `src/pci_realtime/ingest/{base,treasury,congress,omb}.py` |
| 2 — LLM scoring + calibration | 🚧 starting | Duy | `src/pci_realtime/scoring/`, `docs/calibration_report.md` |
| 3 — Time series builder | ⏳ Week 4 | Austin | `src/pci_realtime/pci/builder.py` |
| 4 — Validation analysis | ⏳ Week 6 | Duy | `src/pci_realtime/pci/validation.py`, `docs/validation_memo.md` |
| 5 — Dashboard + cron | ⏳ Week 7 | Austin | Streamlit Community Cloud + `.github/workflows/weekly_update.yml` |
| 6 — Methods paper draft | ⏳ Week 8 | Duy + Yikai | external draft |

## Data and license

- **Code:** MIT.
- **Output data:** PCI time series and validation outputs are public.
- **Licensed inputs (PitchBook):** never enter this repo. Validation Check 2 reads them from the parent project's `Data/PanelData/` and only commits aggregated/de-identified outputs.

## Privacy

This is a private repo until the methods paper is on arXiv, then it flips to public for replication.
