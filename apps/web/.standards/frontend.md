# PCIndex Frontend Standards

The web app is a **source-grounded policy credibility registry**, NOT a generic dashboard, betting app, or news feed. Every UI surface must help answer:

1. **Did official policy credibility change?**
2. **Is there a clean public market that prices the change?**
3. **What exact source evidence supports the system state?**

## Core UX Principles

### 1. Evidence before aesthetics
Every visible policy claim, PCI score, market status, forecast, and abstention must be traceable to evidence or to an explicit no-evidence/no-market reason. Every claim-like component supports at least one of: inline citation, evidence drawer, source link, run trace, rejection/abstention reason.

### 2. State must be legible at a glance
Every provision card exposes: provision code, plain-language question, current PCI, stress PCI, market eligibility state, evidence count, last updated timestamp. Never show vague empty states (`Waiting`, `Loading`). Use explicit states:
`Eligible public market` · `No eligible public market` · `Near-miss market` · `Source scan stale` · `Evidence insufficient` · `Forecast abstained` · `Human review pending`

### 3. Polymarket density, not Polymarket psychology
Borrow: dense card grid, topic/filter tabs, compact score chips, search-first nav, table↔card toggle, bottom-sheet detail drawers, time-range chart tabs. Do NOT borrow: gambling tone, profit-first framing, unsupported trade CTAs, hidden methodology.

### 4. Tables for comparison, cards for discovery
- Cards: provision overview, latest evidence, market discovery
- Tables: market candidates, near-misses, source health, pipeline runs, forecast history, trade proposals
Tables must support filtering, sorting, row expansion, row-level actions, and have empty/loading/error states.

### 5. Provenance drawer is mandatory for serious outputs
Any score, event, forecast, or rejection opens an `EvidenceDrawer` exposing: source title, source type, source URL, extracted quote/span, publication date, fetched_at, source_document_id, document_chunk_id or chunk_hash, extractor version, rubric version, pipeline_run_id, support relation (quote · compression · inference · absence).

### 6. Score decomposition must be visible
Never show PCI alone. Always one click to: Specificity, Durability, Enforceability — each with score, rationale, supporting evidence IDs, last update, confidence/uncertainty.

### 7. Avoid false precision
Show `PCI 4.3`, `11 near-misses`, `Last scan 2h ago`. Not `PCI 4.333333`, `confidence 87.124%`, vague `AI confidence high`.

### 8. No uncited model prose
Any model-generated sentence in the UI must be marked as: extracted from source · model summary of cited evidence · model inference · unsupported/no evidence.

### 9. Accessibility & interaction
Visible focus, semantic buttons/links, alt text, color is never the only status signal, skeleton/loading/error/empty states, mobile degradation.

### 10. Performance budget
First useful paint < 1.5s. No giant client bundle for static registry data. Virtualize long tables. Lazy-load heavy charts/drawers. Default to server components.

## Default Route Structure

| Route | Purpose |
|---|---|
| `/` | Landing — Polymarket-style provision grid + KPI strip |
| `/markets` | Same grid expanded, full filters/sort, no hero |
| `/markets/[code]` | Provision detail — tabs: Overview, Evidence, Markets, Methodology, Trace |
| `/evidence` | Searchable source/evidence registry |
| `/evidence/[id]` | Single evidence item (deep-link target for inline citations) |
| `/source-health` | Source health board |
| `/about` | Paper companion |

## Modal/Drawer Surfaces (non-routing)

- `EvidenceDrawer` — bottom sheet. Tabs: Source · Passage · Extraction · Scoring · Linkage · Run.
- `MarketCandidateDrawer` — bottom sheet. Scan metadata + rejection reasons + venue URL.
- `MethodologyDrawer` — bottom sheet. Formula + clipping + decay rules.

All drawers use the same `BottomSheet` primitive — drag handle, dismiss-on-backdrop, Escape closes, focus trap.

## Component Standard

Every production component:
- typed props
- loading state
- empty state with explicit reason
- error state
- keyboard accessibility
- responsive behavior
- no hardcoded production data
- no secret exposure (no `supabase` token in markup)

## Forbidden Patterns

- `Waiting` without reason
- Uncited policy claims
- Unlabeled AI-generated summaries
- Pure color status labels
- Hidden methodology
- Fake interactivity
- Trade-like CTAs without eligibility/compliance state
- Unbounded client-side data fetching
- Large tables without filters/sorting
- Screenshots as data
- The literal token `supabase` in rendered markup
