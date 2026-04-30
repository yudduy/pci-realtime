# Module Interfaces — Hand-off Contracts

**Status:** Locked. Any change requires a PR with both Austin and Duy as reviewers and Yikai's signoff.

This file defines the three parquet schemas that connect the project's three subsystems:

```
ingest/  ──[Schema A]──►  scoring/  ──[Schema B]──►  pci/builder.py  ──[Schema C]──►  dashboard/
(Austin)                  (Duy)                       (Austin)                          (Austin)
```

Once these schemas are stable, Austin and Duy can work independently. Either RA producing or consuming one of them must conform to the column names, dtypes, and partitioning convention below.

---

## Schema A — Ingestor → Scoring

**Producer:** `pci_realtime.ingest.*` (Austin owns; Duy's `federal_register.py` is the reference implementation)
**Consumer:** `pci_realtime.scoring.screener`, `pci_realtime.scoring.scorer` (Duy)
**Path:** `data/raw/<source>/<source>_<YYYY-WW>.parquet` (one file per source per ISO week)

| Column | Type | Notes |
|---|---|---|
| `doc_id` | `string` | Stable identifier; format `<source>:<native-id>` (e.g. `federal_register:2024-12345`) |
| `date` | `date` | Publication or effective date (whichever is earlier and known); UTC |
| `source` | `string` | One of: `federal_register`, `treasury`, `irs`, `congress`, `omb` |
| `agency` | `string` | Issuing agency (free text from upstream; e.g. `Internal Revenue Service`) |
| `title` | `string` | Document title |
| `body` | `string` | Full plaintext or markdown; HTML stripped. May be truncated to 50k chars; if so set `body_truncated=True` |
| `body_truncated` | `bool` | Default `False` |
| `url` | `string` | Permalink to the upstream record |
| `provisions_mentioned` | `list[string]` | IRA section numbers detected by keyword (e.g. `["45X", "45V"]`); empty list if none. Used only as a heuristic — the screener re-classifies. |
| `ingested_at` | `timestamp[ns, UTC]` | When this row was written |
| `ingestor_version` | `string` | Semver of the ingestor module that produced this row |

**Examples** (file naming):
- `data/raw/federal_register/federal_register_2024-W15.parquet` ← Duy's POC
- `data/raw/treasury/treasury_2024-W15.parquet`
- `data/raw/congress/congress_2024-W15.parquet`

**Validation:** all ingestors share a `BaseIngestor` (Austin will define) that enforces this schema before write.

---

## Schema B — Scoring → Index

**Producer:** `pci_realtime.scoring.scorer` (Duy)
**Consumer:** `pci_realtime.pci.builder` (Austin)
**Path:** `data/processed/scored/scored_<YYYY-WW>.parquet`

| Column | Type | Notes |
|---|---|---|
| `doc_id` | `string` | Foreign key to Schema A |
| `provision` | `string` | One of: `45X`, `45V`, `45Q`, `30D`, `50141`, `50144`. One row per `(doc_id, provision)` pair. |
| `specificity_delta` | `float64` | In [−2.0, +2.0]; on the underlying 1–5 PCI dimension scale |
| `durability_delta` | `float64` | In [−2.0, +2.0] |
| `enforceability_delta` | `float64` | In [−2.0, +2.0] |
| `rationale` | `string` | Free-text justification, ~1–3 sentences |
| `confidence` | `float64` | In [0.0, 1.0]; the scorer's self-reported confidence |
| `model` | `string` | e.g. `gpt-4.1-2025-08-12`, `claude-sonnet-4.5-2026-01` |
| `prompt_version` | `string` | Semver of the prompt template (e.g. `v1.2.0`); see `pci_realtime.scoring.prompts` |
| `temperature` | `float64` | Inference temperature (0.3 default) |
| `scored_at` | `timestamp[ns, UTC]` | When the LLM call returned |
| `cached` | `bool` | `True` if this row was returned from the response cache |
| `cost_usd` | `float64` | Estimated marginal cost of this scoring call (0.0 if cached) |

**Validation rules** (the scorer must enforce, the builder may double-check):
- Each delta in [−2.0, +2.0]
- `provision` ∈ the six locked values
- `(doc_id, provision)` unique within the file
- A doc with no provision-relevant content from Schema A's screener emits NO rows in Schema B (rather than zero-deltas) — keeps the file sparse.

---

## Schema C — Index → Dashboard

**Producer:** `pci_realtime.pci.builder` (Austin)
**Consumer:** `pci_realtime.dashboard.app` (Austin), validation scripts (Duy), the public CSV export
**Path:** `data/processed/pci_weekly.parquet` (single file, append-only by week)

| Column | Type | Notes |
|---|---|---|
| `provision` | `string` | One of the six locked values |
| `week` | `string` | ISO week, format `YYYY-WW` (e.g. `2025-W23`) |
| `pci` | `float64` | Composite PCI score, in [1.0, 5.0]. `pci = (specificity + durability + enforceability) / 3` |
| `specificity` | `float64` | In [1.0, 5.0] |
| `durability` | `float64` | In [1.0, 5.0] |
| `enforceability` | `float64` | In [1.0, 5.0] |
| `n_docs` | `int64` | Number of scored docs that contributed to this week's update for this provision |
| `delta_this_week` | `float64` | `pci(t) − pci(t−1)`, for plotting/dashboards |
| `updated_at` | `timestamp[ns, UTC]` | When this row was (re-)computed |

**Update rule** (sticky, no decay):
```
pci[p, t] = clip(pci[p, t-1] + Σ scored_deltas[p, t] / 3, 1.0, 5.0)
```
where `Σ scored_deltas[p, t]` sums (specificity_delta + durability_delta + enforceability_delta) across all docs scored in week `t` that affect provision `p`.

**Anchors:** `data/baseline/pci_baseline.csv` provides the immutable Aug 2022 starting values (45X=4.67, 45V=4.33, 45Q=4.33, 30D=4.00, 50144=3.33, 50141=3.00). The first row of `pci_weekly.parquet` for each provision is `(provision, 2022-W33, baseline_value, 5, 4, 5, 0, 0.0, ...)`.

**Validation gate:** the builder's output for week `2025-W23` (peak OBBBA) must match the paper's post-OBBBA values within ±0.3 per provision. See `pci/validation.py::test_obbba_match`.

---

## Cross-cutting conventions

1. **Time zones:** all timestamps UTC. ISO weeks (`YYYY-WW`) computed in UTC.
2. **No nulls in key columns:** `doc_id`, `provision`, `week` are never null.
3. **Strings as utf-8.** No bytes columns.
4. **Provenance:** every row in Schemas B and C must be recoverable from the raw Schema A doc that produced it (via `doc_id`).
5. **Schema evolution:** add columns freely (consumers should ignore unknowns). Never rename or remove columns without a PR + both-RA review + Yikai signoff.
