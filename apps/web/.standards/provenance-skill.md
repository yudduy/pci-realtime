# PCIndex Provenance UI Skill

## Purpose
Design and review PCIndex UI as a source-grounded policy-market registry. The UI must connect: **official source → extracted evidence → PCI dimension → market eligibility → forecast/proposal/outcome**. Do not design generic SaaS dashboards. Do not design gambling-first prediction market UI.

## Design Grammar

### Borrow from prediction markets
compact market cards · question-first cards · filter/topic tabs · odds/score chips · liquidity/status metadata · detail pages · bottom-sheet drawers · time-range chart tabs

### Borrow from policy index platforms
visible methodology · score decomposition · rating rationale · comparison tables · source transparency

### Borrow from RAG/citation products
inline citations · evidence drawers · exact quotes/spans · source links · trace timelines

## Required Components

### `ProvisionCard`
provision code · plain-language question · category/lane · PCI · stress PCI · market eligibility state · evidence count · last update · detail link.

### `MarketCandidateRow`
title · venue · probability if available · liquidity/volume · close/resolution date · eligibility status · rejection reason if ineligible · source link · detail action.

### `EvidenceDrawer`
claim · source document · source type · source URL · extracted span · publication date · fetched_at · evidence type · provision match · extractor version · rubric version · pipeline run · support relation.

### `PciBreakdown`
specificity score · durability score · enforceability score · rationale for each · supporting evidence IDs · missing-evidence warnings.

## State Labels (exact)
`Eligible public market` · `No eligible public market` · `Near-miss market` · `Evidence found` · `Evidence insufficient` · `Forecast abstained` · `Human review pending` · `Source scan stale` · `Pipeline error`

Avoid: `Waiting`, `Processing`, `Maybe`, `AI says`, `Market unavailable`.

## Review Checklist (must verify before completing a UI change)
- Every claim has evidence or an abstention reason
- PCI is decomposed, not a magic number
- Market absence is explained with scan counts and rejection reasons
- Tables support find, compare, inspect, act
- Cards scanable in <5s
- Charts have accompanying text/table values
- Empty states are specific + actionable
- No private cache data or secrets exposed
- Mobile layout preserves identity, score, status per provision
- Loading, error, stale states implemented
