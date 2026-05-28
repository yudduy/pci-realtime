# PCIndex — 2-5 minute walkthrough

Use as a teleprompter. Each section labeled with target seconds. **Bolded** text = what's on screen.

---

## (0:00–0:25) Open — what & why
"PCIndex is a public, source-grounded registry of how credible IRA climate-policy commitments are. The paper defines **Policy Credibility Index (PCI)** as institutional design quality scored 1–5 across three dimensions — **specificity, durability, enforceability**. We turn the static paper anchor into a weekly index that updates from official documents, then matches each provision to clean public prediction markets when one exists."

*(Open `https://pcindex.vercel.app/`)*

---

## (0:25–1:00) The product loop — one breath
"Six IRA provisions are tracked: **45X factory credits, 45V hydrogen, 45Q carbon capture, 30D EV, 50144 reinvestment, 50141 loan office**.

Every Monday a pipeline runs: ingest Federal Register, Congress.gov, Treasury, OMB — score document-level deltas in [-2, +2] — apply the sticky weekly update rule — scan ~16,000 public Kalshi and Polymarket markets — record either an eligible match, a near-miss with rejection reason, or an explicit abstention. Forecasts only publish when a usable market exists."

*(Hover the **provision grid** so they see Spec/Dur/Enf chips + state pills.)*

---

## (1:00–1:50) Live click-through — the modular surface
"Click into **45V hydrogen**."

*(Open `/markets/45V`.)*

"The hero shows: current score 4.0, stress score 3.33 from the paper's post-OBBBA snapshot, last 5 weeks of policy events. Right rail decomposes the PCI into the three paper dimensions and tracks market eligibility separately.

The four tabs are the four lenses on the same provision:
- **Evidence** — every weekly policy event with the dimension-level delta and the official source link
- **Markets** — eligible public markets and near-miss candidates with explicit rejection reasons
- **Methodology** — the literal scoring formula from the paper
- **Trace** — the pipeline run that produced this state

Click any **View source** in the Evidence tab —"

*(Click "View source" on the top event.)*

"— and a **bottom-sheet drawer** opens with the extracted span, chunk hash, agency, fetched-at timestamp, and dimension deltas. The URL updates to `/evidence/[id]`, so I can share it; hard-refresh shows the standalone page. **Every visible score traces back to one click on the official document.**"

---

## (1:50–2:30) Why this differs from related work
"Four references shaped this product:
- **Polymarket** for scannable density and the bottom-sheet detail pattern — but PCIndex is evidence-first, not trading-first.
- **Metaculus** for the question-page + probability decomposition.
- **Climate Action Tracker** for the rating-with-methodology discipline — the score is always one click from how it was computed.
- **ChatGPT / Claude citation UI** for inline provenance — every claim has a traceable source or an explicit abstention.

The product is positioned as a research-grade policy registry, not a betting market. **Trading is backend-gated and fail-closed** — five conditions including human approval before any execution. Public surface never exposes private credentials or order payloads."

---

## (2:30–3:30) The two things that make this defensible
"**One: explicit abstention is a feature.** When 16,000 markets scanned yields 0 eligible matches, the UI shows scan counts, rejection categories, and links to the closest near-misses. That's the abstention audit trail — most policy dashboards either fake forecasts or hide the gap.

**Two: every weekly PCI delta has a provenance chain.** Source document → chunked retrieval → LLM-scored dimension delta → sticky weekly update → optional market match. The chunk hash and extractor version are exposed, so a reviewer can replay the inference."

---

## (3:30–4:30) What the paper contributes vs what the product adds
"The paper produced the **anchor**: six tracked provisions, the baseline scores at IRA enactment, and the post-OBBBA stress snapshot. The product adds the **temporal axis**: a weekly index that absorbs real official-source changes, market-eligibility audit, and inline provenance.

So if a researcher asks 'is 45V still credible?' the paper says 'as of August 2022, baseline 4.33; post-OBBBA stress 3.33'. PCIndex says: 'as of this week, current PCI 4.00, down 0.33 since Treasury narrowed eligibility on May 18 — here's the Federal Register page, here's the dimension that moved, here's whether Kalshi prices it.'"

---

## (4:30–5:00) Close
"Three takeaways:
1. PCI is **source-grounded** — every score traces to an official document.
2. Market eligibility is **separate** from forecasting — the system abstains audibly when no clean market exists.
3. The product is **the temporal extension of the paper**, not a replacement.

`https://pcindex.vercel.app` · `github.com/yudduy/pci-realtime`. Code is MIT. Pipeline runs every Monday."

---

## Demo URLs
- Landing: `/`
- All provisions: `/markets`
- 45V hydrogen (good demo — has events + forecast + snapshot): `/markets/45V`
- 50141 loan office (no eligible market, near-miss + rejection reason): `/markets/50141`
- Standalone evidence: `/evidence/2026-W21:federal_register:45v-guidance:45V`

## Backup phrasing if asked
- *"Why not just use Polymarket directly?"* — Polymarket prices many things; we filter to public markets where the resolution criteria directly cover an official IRA policy channel. The rejection audit shows what we discarded and why.
- *"Why three dimensions and not a single score?"* — Because the paper argues credibility moves separately along rule-clarity, time-horizon, and agency follow-through. A change to one dimension is a different signal than a change to another.
- *"Can this trade?"* — Backend-only. Five conditions including human approval. Public site is read-only.
