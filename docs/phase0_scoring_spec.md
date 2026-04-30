# Phase 0 Scoring Spec

This document freezes the initial design choices for the real-time PCI monitor before model scoring begins.

## Source Materials

This specification is derived from the current paper materials:

- `Credibility.tex`
- `SI_Appendix.tex` Section G
- `Uncertainty.tex`
- `Research_report.pdf`

These files are the source of truth for the baseline PCI logic, the OBBBA stress test, and the intended complementarity between PCI and CPU.

## Research Goal

Extend PCI from two static snapshots into a weekly time series that tracks how provision-level credibility changes as new policy documents are released.

The real-time PCI should remain conceptually consistent with the paper:

- PCI measures **institutional design quality**, not investor sentiment.
- CPU measures **market-perceived policy uncertainty**.
- The two should be treated as complementary signals, not substitutes.

## Tracked Provisions

The monitor starts with the six focal provisions used in the paper.

| Provision | Description | Provision Type |
| --- | --- | --- |
| `45X` | Advanced Manufacturing Production Credit | tax credit |
| `45V` | Clean Hydrogen Production Credit | tax credit |
| `45Q` | Carbon Oxide Sequestration Credit | tax credit |
| `30D` | Clean Vehicle Credit | tax credit |
| `50144` | Energy Infrastructure Reinvestment | DOE / LPO program |
| `50141` | Loan Programs Office Funding | DOE / LPO program |

## PCI Dimensions

PCI is the simple average of three dimensions, each scored on a `1-5` scale.

### Specificity

- `5`: Eligibility criteria fully codified in statute with quantitative thresholds; no agency discretion in qualification
- `4`: Criteria largely codified but with some parameters delegated to guidance
- `3`: Mixed statutory criteria and agency-determined requirements
- `2`: Broad statutory authorization with substantial agency discretion
- `1`: Fully discretionary allocation with no statutory eligibility criteria

### Durability

- `5`: Permanent authorization with no sunset; embedded in tax code
- `4`: Multi-year statutory horizon (`>= 10 years`) insulated from annual appropriations
- `3`: Medium-term horizon (`5-10 years`) or periodic reauthorization
- `2`: Short-term authorization (`< 5 years`) or annual appropriations dependence
- `1`: Single-year funding or annual discretionary allocation

### Enforceability

- `5`: Single agency, specified procedures, automatic implementation
- `4`: Clear agency assignment with published guidance and standard process
- `3`: Clear agency assignment but multi-step review or interagency coordination
- `2`: Overlapping agencies or revisable procedures
- `1`: No clear agency assignment; implementation depends on executive discretion

## Baseline Snapshot at IRA Enactment

Baseline date: **2022-08-16**

| Provision | Specificity | Durability | Enforceability | PCI |
| --- | --- | --- | --- | --- |
| `45X` | 5.00 | 4.00 | 5.00 | 4.67 |
| `45V` | 5.00 | 4.00 | 4.00 | 4.33 |
| `45Q` | 5.00 | 4.00 | 4.00 | 4.33 |
| `30D` | 4.00 | 4.00 | 4.00 | 4.00 |
| `50144` | 4.00 | 3.00 | 3.00 | 3.33 |
| `50141` | 3.00 | 3.00 | 3.00 | 3.00 |

## OBBBA Snapshot and Anchor

The paper provides provision-specific PCI shocks under the 2025 OBBBA framework.

| Provision | Delta PCI | Implied Post-OBBBA PCI |
| --- | --- | --- |
| `45X` | `-1.00` | `3.67` |
| `45V` | `-1.00` | `3.33` |
| `45Q` | `0.00` | `4.33` |
| `30D` | `-1.00` | `3.00` |
| `50144` | `-1.33` | `2.00` |
| `50141` | `-0.67` | `2.33` |

These values are the first validation anchor for the realtime series. A successful weekly backfill should recover these values approximately during the OBBBA window.

## Realtime Update Logic

For each `(provision, week)`:

1. collect relevant source documents,
2. screen whether each document is relevant to a tracked provision,
3. score document-level deltas for:
   - `specificity_delta`
   - `durability_delta`
   - `enforceability_delta`
4. aggregate document deltas within week and provision,
5. update weekly PCI.

Initial operational update rule:

```text
PCI[p, t] = clip(
    PCI[p, t-1] + sum_doc((specificity_delta + durability_delta + enforceability_delta) / 3),
    lower = 1.0,
    upper = 5.0
)
```

Notes:

- `clip` keeps the index on the same `1-5` scale used in the paper.
- Raw dimension deltas should still be stored before clipping for auditability.
- The default assumption is **sticky credibility**: no decay back to baseline when there is no new document.
- A decay-to-baseline sensitivity check can be added later, but it is **not** the default.

## Document Sources In Scope for Initial Build

### Required in Phase 1 proof of concept

- Federal Register

### Intended next sources

- Treasury guidance pages
- IRS notices / proposed and final rules
- Congressional Record / Congress API
- OMB memos

## Federal Register Phase 1 Scope

For the first build, Federal Register ingestion will:

- query by date window and policy keywords,
- retain documents from agencies most relevant to IRA implementation,
- deduplicate repeated hits across query terms,
- infer which tracked provisions are mentioned,
- store a weekly parquet.

Agency allowlist for phase 1:

- Treasury Department
- Internal Revenue Service
- Department of Energy / Energy Department
- Environmental Protection Agency

## Keyword Set for Phase 1

Core policy and provision terms:

- `Inflation Reduction Act`
- `section 45X`
- `advanced manufacturing production credit`
- `section 45V`
- `clean hydrogen production credit`
- `section 45Q`
- `carbon oxide sequestration credit`
- `section 30D`
- `clean vehicle credit`
- `section 6417 elective payment of applicable credits`
- `section 6418 transfer of certain credits`
- `section 50141`
- `loan programs office`
- `section 50144`
- `energy infrastructure reinvestment`

## LLM Scoring Contract

The realtime scorer must eventually return one record per `(document, provision)`:

```json
{
  "provision": "45X",
  "specificity_delta": 0.0,
  "durability_delta": 0.0,
  "enforceability_delta": 0.0,
  "rationale": "Explain why the document changes or does not change credibility.",
  "confidence": 0.0
}
```

Operational constraints:

- deltas should live on a `[-2, +2]` range by dimension,
- confidence should be on `[0, 1]`,
- scoring outputs must store prompt version, model name, timestamp, and raw response text.

## Relationship to CPU

Per `Uncertainty.tex`, CPU is a news-based measure of market-perceived uncertainty, normalized to mean `100`. The paper's conceptual design is:

- PCI = institutional design quality
- CPU = market-perceived uncertainty

The realtime monitor should therefore preserve enough weekly structure to support later validation against:

- aggregate CPU
- implementation uncertainty
- reversal uncertainty

## First Validation Targets

Phase 0 freezes the following validation targets for later phases:

1. **Snapshot consistency**: realtime PCI should approximately recover the post-OBBBA provision values above.
2. **Directional consistency with CPU**: worsening PCI should generally align with higher reversal-oriented uncertainty.
3. **Document provenance**: every weekly PCI value must be traceable to specific source documents and model outputs.

## Open Items For Phase 2

These are intentionally deferred, not unresolved:

- final prompt wording
- screening/scoring model split
- multi-source document deduplication across APIs
- weekly weighting if multiple documents in same week conflict
- decay sensitivity implementation
