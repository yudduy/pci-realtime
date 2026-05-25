# Reference Data

Small, committed reference data files used for tests and calibration.

## `federal_register_known_documents.csv` (Duy)

11 documents with known Federal Register IDs used as a golden test set for
the `federal_register.py` ingestor. Lives alongside `tests/test_federal_register.py`.
**Do not edit** without updating the test.

## `calibration_set_v1.csv` (Austin extends, Yikai scores, Duy uses)

20 federal-policy events spanning Aug 2022 → Jun 2025, each with manual
ΔPCI scores on (specificity, durability, enforceability) for the affected
provision(s). This is the **ground truth** used by scorer calibration to
measure LLM scoring RMSE before scaling to the full corpus.

**Review path:**

1. **Austin** — extends the seeded 20 rows: verify dates, fill in
   missing URLs (Federal Register, Treasury press releases, IRS Notice
   pages, EO listings), and tighten the `notes` column. Add up to 5 more
   high-impact events if found. Set `verified=TRUE` on rows whose
   metadata you've fact-checked against the upstream document.
2. **Yikai** — reviews Austin's verified rows; overrides any
   `*_delta` values that disagree with his manual scoring. Sets
   `scored_by=yikai` and `confidence` to `high` on rows he's signed off on.
3. **Duy** — runs the LLM scoring module 5x per row at `temperature=0.3`.
   Gate: RMSE < 0.5 on the 1-5 scale.

**Internal consistency check:** Σ Δ-values per provision across all 20 rows
should approximately equal the cumulative ΔPCI from the paper's Aug 2022
baseline to the post-OBBBA values (45X: −1.00, 45V: −1.00, 30D: −1.00,
50141: −0.67, 50144: −1.33, 45Q: 0.00). If they don't sum, that's a
calibration error to fix before Duy uses this for RMSE.

**Schema** (the columns in `calibration_set_v1.csv`):

| Column | Type | Notes |
|---|---|---|
| `row_id` | `int` | 1-indexed, stable across versions |
| `date` | `YYYY-MM-DD` | Publication or effective date |
| `provision` | `string` | One of `45X`, `45V`, `45Q`, `30D`, `50141`, `50144`, or a `+`-joined combination, or `ALL` for cross-cutting events |
| `doc_title` | `string` | Short human-readable title |
| `url` | `string` | Federal Register / Treasury / EO permalink (Austin fills in if blank) |
| `specificity_delta` | `float` | Manual score, ±2.0 scale |
| `durability_delta` | `float` | Manual score, ±2.0 scale |
| `enforceability_delta` | `float` | Manual score, ±2.0 scale |
| `confidence` | `string` | `low` / `medium` / `high` — Yikai's confidence in the score |
| `notes` | `string` | Free-text rationale and review notes |
| `scored_by` | `string` | `starter` (this file's seed), `austin`, or `yikai` |
| `verified` | `bool` | `TRUE` once the row has been cross-checked against upstream |

## `scored_2024-W44_fixture.csv` (Duy reference scorer output)

Small synthetic scored-delta fixture for Austin's `pci/builder.py` work.
The rows follow the scored-delta contract in the root README but are not live
LLM outputs and should not be used for calibration or paper results.
