# Policy Intelligence Ledger Vision

## North Star

A live, citation-backed policy intelligence ledger that turns official policy activity into structured knowledge for policymakers, researchers, and AI agents.

The product exists to answer a simple set of questions: what changed in policy, why it matters, what evidence supports that interpretation, and how the change affects the policy over time. Policy changes are captured as evidence, organized into policy units, and made queryable through dossiers, dashboards, APIs, MCP tools, exports, and derived analytics.

The ledger is the product. The Policy Credibility Index is the first major derived signal built on top of it.

## Product Thesis

The main object is not a document, score, market, dashboard, or AI summary. The main object is an evidence event.

Official documents are raw material. Claims, citations, rationales, provenance, and affected policy units form the durable ledger. PCI scores, trends, forecasts, dashboards, reports, and AI answers are downstream products that must trace back to ledger evidence.

This means the system should optimize for:

- evidence before opinion
- citations before summaries
- structured records before prose
- traceable analysis before compressed scores
- public-safe outputs before convenience
- human-readable and machine-queryable records

## System Design Decisions

- Use official and public sources as the credibility base.
- Track policy at the provision level first, then expand to broader policy domains.
- Treat source documents as inputs and evidence events as the normalized ledger entries.
- Preserve a strict public/private boundary: no secrets, raw model responses, private execution payloads, signed trading data, local user paths, or private firm data in public views.
- Keep Postgres and Supabase as the operational source of truth for the current system.
- Borrow from provenance, annotation, legal-document, catalog, and controlled-vocabulary patterns without requiring RDF, OWL, or a graph database in v1.
- Expose MCP and API interfaces so external AI assistants can query the ledger directly.
- Keep PCI important, but define it as a derived analytical layer rather than the product identity.

## Architecture Model

```text
Official Sources
  -> Raw Source Archive
  -> Canonical Documents / Sections
  -> Evidence Events / Claims / Citations
  -> Policy Intelligence Ledger
  -> Derived Signals
  -> Web, Search, MCP, API, Reports
```

### Official Sources

- Federal agencies, statutes, rules, guidance, court records, budgets, public datasets, and other public policy sources.
- Sources must be identifiable, citeable, and safe for public use.
- General news can provide context later, but it should not outrank official evidence in the ledger.

### Raw Source Archive

- Stores retrieved source material with canonical URLs, retrieval metadata, timestamps, and stable identifiers.
- Preserves enough provenance to explain where each downstream record came from.
- Raw material is not itself the product-facing interpretation.

### Canonical Documents / Sections

- Normalizes source documents into stable document records and, where possible, sections or cited spans.
- Supports legal and policy structure: agencies, dates, provisions, programs, statutory references, and source type.
- Gives the system a durable basis for citation and later reprocessing.

### Evidence Events / Claims / Citations

- Converts source material into normalized ledger entries.
- Each promoted event should identify the policy unit, source document, citation or quote, structured claim, rationale, and provenance.
- This is the core source-of-truth layer for policy intelligence.

### Policy Intelligence Ledger

- Organizes evidence events across policy units, dates, sources, agencies, topics, and relationships.
- Supports audit, retrieval, trend analysis, comparison, and briefing workflows.
- This layer should remain stable even as product surfaces change.

### Derived Signals

- Includes PCI, credibility dimensions, implementation status, risk indicators, forecasts, alerts, and trend summaries.
- Derived signals must be explainable by tracing back to evidence events.
- A missing evidence trail means the signal is not ready for public trust.

### Web, Search, MCP, API, Reports

- These are interfaces over the ledger, not independent sources of truth.
- The web app should make the ledger readable for humans.
- MCP and APIs should make the ledger usable by external AI systems and institutional workflows.

## Core Data Objects

- `PolicyUnit`: a provision, program, statute, regulation, or other policy object being tracked.
- `SourceDocument`: official or public source metadata, canonical URL, source type, date, and stable identifier.
- `Citation`: exact quoted span, excerpt, or reference into a source document.
- `Claim`: structured statement extracted from evidence, such as "eligibility narrowed" or "implementation clarified."
- `EvidenceEvent`: normalized ledger entry saying what changed, which policy unit it affects, and why it matters.
- `DerivedSignal`: PCI, trend, risk, implementation status, forecast, alert, or other analytical output created from ledger evidence.
- `Interface`: web dossier, terminal, MCP tool, API endpoint, export, or report that exposes ledger information.

## Product Surfaces

- Policy dossiers: human-readable case files for each policy unit, including current status, history, evidence, citations, rationale, and trends.
- Terminal and search: ways to query, compare, filter, and inspect the ledger by policy unit, source, date, agency, topic, claim type, and natural language.
- Trends: time-series views that show policy movement with evidence-backed rationale.
- MCP and API: structured access so AI agents and external tools can ask policy questions with citations.
- Exports: durable datasets and reports for researchers, institutions, and policymakers.

## Non-Goals

- Not a generic news aggregator.
- Not a trading app.
- Not an unsupported chatbot.
- Not a score-only website.
- Not a place where AI-generated claims outrank cited evidence.
- Not a replacement for expert judgment; the system organizes evidence so judgment becomes easier.

## Phase Gates And Verification

### Phase 0: Vision Alignment

Passes when:

- `VISION.md` clearly says the ledger is the product and PCI is a derived feature.
- README and agent guidance do not contradict the vision.
- A new engineer can explain the product in three sentences without calling it only a PCI dashboard.

Checks:

- Documentation review confirms README remains operational, while `VISION.md` remains conceptual.
- Search review confirms public product copy does not reduce the project to a trading app, generic AI summarizer, or score-only dashboard.

### Phase 1: Ledger Foundation

Passes when:

- Every promoted evidence item has a policy unit, source document, citation or quote, claim, rationale, and provenance.
- Invalid sources, missing quotes, duplicate evidence, wrong policy mapping, and unsafe public payloads are rejected or clearly marked.
- Given one official source URL, the system can create a traceable ledger entry without exposing private data.

Tests:

- Unit tests for evidence intake validation and canonical URL handling.
- Contract tests for source documents, evidence items, source links, agent submissions, and public views.
- Safety tests for secrets, raw model responses, local paths, private payloads, and signed execution data.

### Phase 2: Queryable Knowledge Layer

Passes when:

- Users can retrieve evidence by policy unit, source, date, agency, topic, claim type, and natural-language query.
- Retrieved answers preserve citations and do not replace missing evidence with generic summaries.
- Empty or ambiguous queries return clear no-evidence states.

Tests:

- Query fixtures for exact policy codes, source names, dates, and agencies.
- Semantic-style fixtures for natural questions such as "Why did 45V credibility change?"
- Citation preservation tests from retrieval result through UI or API response.
- Empty-result tests that verify no invented evidence appears.

### Phase 3: Derived Signals

Passes when:

- PCI and other signals trace back to evidence events.
- Score changes expose rationale and source-event links.
- No-evidence and no-change periods remain visible instead of being filled with fake movement.

Tests:

- PCI calculation tests for dimension deltas, clipping, sticky weeks, and no-change behavior.
- Signal trace tests proving each visible movement has linked evidence.
- Regression tests that prevent synthetic forecasts or score movements without eligible evidence.

### Phase 4: Policymaker Terminal

Passes when:

- The UI supports dossier reading, trend inspection, source audit, and policy comparison without market or trading confusion.
- A policy staffer can inspect a policy, see what changed, and cite the source.
- Public language reinforces policy intelligence, not unsupported AI or execution.

Tests:

- Playwright tests for navigation, dossiers, citations, trend views, empty states, and comparison surfaces.
- Copy tests that reject confusing terms such as trading-first, unsupported-agent, or fake-readiness language.
- Public payload tests confirming the browser only receives publishable data.

### Phase 5: Agent And MCP Integration

Passes when:

- MCP and API tools expose structured reads and controlled evidence submission.
- External AI assistants can answer policy questions using ledger citations instead of hallucinated context.
- Evidence submissions are idempotent, citeable, public-safe, and schema-stable.

Tests:

- MCP and API schema tests for stable tool names, arguments, and response shapes.
- Bad-input tests for unknown policy units, private URLs, missing citations, duplicate submissions, and malformed dates.
- End-to-end fixture showing an external agent can submit or retrieve evidence and receive citation-backed output.

## Decision Log

- The product is a policy intelligence ledger first; PCI is a derived signal.
- Evidence events are the normalized center of the system.
- Official and public sources have priority over general commentary.
- Human-readable dossiers and machine-queryable interfaces are both first-class outputs.
- Postgres/Supabase remains the operational source of truth until a graph-specific need is proven.
- MCP/API access is part of the core platform strategy, not an afterthought.
- Public trust depends on citation, provenance, and safe output boundaries.

## Open Decisions

- Graph timing: when to introduce a dedicated graph database or graph projection beyond relational tables.
- Embeddings: which provider, model, refresh cadence, and storage strategy should power semantic search.
- Ontology depth: how formal the policy taxonomy should become before expansion beyond IRA climate provisions.
- Review workflow: what evidence can be auto-promoted, what requires human review, and who can approve corrections.
- Domain expansion: which policy areas after IRA climate should be added first.
- Versioning: how to represent policy unit revisions, superseded interpretations, and disputed claims.
- Public exports: which dataset formats and licenses should be supported for researchers and institutions.

## Document Role

`VISION.md` is the product compass. It should stay conceptual and stable.

README is for setup, commands, and current capability status. Agent guidance is for repo-specific working rules. Implementation details belong in code, tests, migrations, and operational docs.
