import { createServer } from "node:http"

const now = "2026-05-24T08:00:00.000Z"
const ago = (days) => new Date(Date.parse(now) - days * 86_400_000).toISOString()

const currentPci = [
  provision("30D", "Clean Vehicle Credit", 4.0, 4, 4, 4, 3.0, -0.05),
  provision("45Q", "Carbon Oxide Sequestration Credit", 4.33, 5, 4, 4, 4.33, 0),
  provision("45V", "Clean Hydrogen Production Credit", 4.0, 4, 4, 4, 3.33, -0.33),
  provision("45X", "Advanced Manufacturing Production Credit", 4.67, 5, 4, 5, 3.67, 0.0),
  provision("50141", "Loan Programs Office Funding", 3.0, 3, 3, 3, 2.33, 0.0),
  provision("50144", "Energy Infrastructure Reinvestment", 3.0, 4, 3, 3, 2.0, -0.33),
]

const openForecasts = [
  forecast({
    code: "45V",
    name: "Clean Hydrogen Production Credit",
    ticker: "KXIRA-45VREPEAL-YES",
    title: "Will Congress repeal or terminate the 45V clean hydrogen tax credit?",
    rules: "Resolves Yes if federal law repeals or terminates the Section 45V clean hydrogen production credit.",
    docId: "federal_register:45v-guidance",
    docSource: "federal_register",
    docTitle: "Clean hydrogen production credit guidance",
    docUrl: "https://www.federalregister.gov/documents/example",
    delta: -0.33,
    dimension: "specificity",
    market: 0.47,
    pciRule: 0.52,
    llm: 0.5,
    model: 0.49,
    confidence: 0.74,
    evidence: "Treasury guidance narrows eligibility for the clean hydrogen credit.",
    counter: "The market may already price the guidance.",
    risk: "Use only when the resolution criteria directly cover the official policy channel.",
  }),
  forecast({
    code: "30D",
    name: "Clean Vehicle Credit",
    ticker: "KXIRA-30DPHASEOUT-YES",
    title: "Will the 30D EV consumer credit be amended before 2027?",
    rules: "Resolves Yes if Congress passes an amendment that materially changes 30D eligibility before 2027-01-01.",
    docId: "congress:hr-9211",
    docSource: "congress",
    docTitle: "EV Credit Reform Act discussion draft",
    docUrl: "https://www.congress.gov/bill/hr-9211",
    delta: -0.05,
    dimension: "durability",
    market: 0.32,
    pciRule: 0.41,
    llm: 0.37,
    model: 0.38,
    confidence: 0.61,
    evidence: "House Ways and Means draft narrows price caps and sourcing rules.",
    counter: "Reform draft has not moved out of committee in three months.",
    risk: "Watch for committee markup before relying on this signal.",
  }),
]

const resolvedForecasts = [
  {
    forecast_id: "forecast:resolved:45Q:KXIRA-45QSTABLE-YES",
    created_at: ago(60),
    venue: "kalshi",
    market_ticker: "KXIRA-45QSTABLE-YES",
    market_title: "Will the 45Q carbon capture credit be amended in Q1 2026?",
    provision: "45Q",
    provision_name: "Carbon Oxide Sequestration Credit",
    market_probability: 0.18,
    pci_rule_probability: 0.12,
    model_probability: 0.14,
    edge: 0.04,
    confidence: 0.78,
    result: "no",
    settlement_value: 0,
    resolved_at: ago(7),
    brier_score: 0.0196,
  },
]

const tradeProposals = [
  {
    proposal_id: "proposal:45V:KXIRA-45VREPEAL-YES",
    created_at: now,
    forecast_id: "forecast:2026-W21:federal_register:45v-guidance:45V:pci_signal:KXIRA-45VREPEAL-YES",
    venue: "kalshi",
    market_ticker: "KXIRA-45VREPEAL-YES",
    edge: 0.02,
    confidence: 0.74,
    risk_passed: true,
    approval_status: "pending_human_review",
    human_approval_required: true,
    public_execution_status: "disabled_by_default",
    rejection_reasons: [],
  },
]

const marketSnapshots = [
  snapshot({
    code: "45V",
    venue: "kalshi",
    ticker: "KXIRA-45VREPEAL-YES",
    title: "Will Congress repeal or terminate the 45V clean hydrogen tax credit?",
    yesAsk: 0.47,
    yesBid: 0.45,
    volume: 188_500,
    liquidity: 42_000,
    resolution: "Resolves Yes if federal law repeals or terminates the Section 45V clean hydrogen production credit before 2027-01-01.",
  }),
  snapshot({
    code: "45Q",
    venue: "kalshi",
    ticker: "KXIRA-45QSTABLE-YES",
    title: "Will 45Q carbon capture credit remain unchanged through 2026?",
    yesAsk: 0.71,
    yesBid: 0.69,
    volume: 96_400,
    liquidity: 24_500,
    resolution: "Resolves Yes if the Section 45Q carbon oxide sequestration credit is not amended through 2026-12-31.",
  }),
  snapshot({
    code: "45X",
    venue: "polymarket",
    ticker: "45x-factory-2026",
    title: "Will the 45X factory production credit see a new Treasury guidance in 2026?",
    yesAsk: 0.58,
    yesBid: 0.55,
    volume: 121_200,
    liquidity: 31_000,
    resolution: "Resolves Yes if Treasury publishes new official 45X guidance in the Federal Register before 2027-01-01.",
  }),
]

const marketDiscoveryCandidates = [
  {
    candidate_id: "test-run:polymarket:tesla-robovan-orders",
    run_id: "test-run",
    generated_at: now,
    venue: "polymarket",
    ticker: "tesla-robovan-orders",
    event_ticker: "tesla-robovan-2027",
    title: "Will Tesla open orders for the Robovan before 2027?",
    market_url: "https://polymarket.com/market/will-tesla-open-orders-for-the-robovan-before-2027",
    status: "active",
    query_name: "polymarket_gamma_events",
    matched_keywords: ["electric vehicle"],
    matched_provisions: ["30D"],
    policy_relevant: false,
    resolution_clear: true,
    eligible_snapshot: false,
    rejection_reasons: ["no_policy_context"],
    liquidity_dollars: 18_284,
    volume: 37_550,
    volume_24h: 10,
  },
  {
    candidate_id: "test-run:polymarket:treasury-blockchain",
    run_id: "test-run",
    generated_at: now,
    venue: "polymarket",
    ticker: "treasury-blockchain",
    event_ticker: "treasury-blockchain-2026",
    title: "Will the US Treasury send transactions on blockchain by June 30?",
    market_url: "https://polymarket.com/market/us-treasury-transactions-on-blockchain-by-june-30",
    status: "active",
    query_name: "polymarket_gamma_events",
    matched_keywords: ["treasury"],
    matched_provisions: [],
    policy_relevant: false,
    resolution_clear: true,
    eligible_snapshot: false,
    rejection_reasons: ["no_tracked_provision_overlap"],
    liquidity_dollars: 9_400,
    volume: 24_000,
    volume_24h: 8,
  },
  {
    candidate_id: "test-run:kalshi:50141-loan-program",
    run_id: "test-run",
    generated_at: now,
    venue: "kalshi",
    ticker: "KXLPO2026-CONT",
    event_ticker: "lpo-2026",
    title: "Will Congress reauthorize the DOE Loan Programs Office in 2026?",
    market_url: "https://kalshi.com/markets/KXLPO2026-CONT",
    status: "active",
    query_name: "kalshi_search:loan office",
    matched_keywords: ["loan program", "DOE"],
    matched_provisions: ["50141"],
    policy_relevant: true,
    resolution_clear: false,
    eligible_snapshot: false,
    rejection_reasons: ["unclear_or_missing_resolution"],
    liquidity_dollars: 12_100,
    volume: 21_800,
    volume_24h: 0,
  },
  {
    candidate_id: "test-run:polymarket:50144-grid-reinvest",
    run_id: "test-run",
    generated_at: now,
    venue: "polymarket",
    ticker: "50144-grid-reinvest",
    event_ticker: "grid-reinvest-2026",
    title: "Will the Energy Infrastructure Reinvestment program disburse $1B+ by Q3 2026?",
    market_url: "https://polymarket.com/market/grid-reinvest-2026",
    status: "closed",
    query_name: "polymarket_gamma_events",
    matched_keywords: ["energy infrastructure"],
    matched_provisions: ["50144"],
    policy_relevant: true,
    resolution_clear: true,
    eligible_snapshot: false,
    rejection_reasons: ["market_not_open"],
    liquidity_dollars: 4_200,
    volume: 8_400,
    volume_24h: 0,
  },
]

const policyEvents = [
  policyEvent({
    code: "45V",
    name: "Clean Hydrogen Production Credit",
    week: "2026-W21",
    weekStart: "2026-05-18",
    docId: "federal_register:45v-guidance",
    docSource: "federal_register",
    agency: "Treasury Department",
    title: "Clean hydrogen production credit guidance",
    url: "https://www.federalregister.gov/documents/example",
    delta: -0.33,
    dims: { specificity: -1, durability: 0, enforceability: 0 },
    rationale: "Treasury guidance narrows eligibility for the clean hydrogen credit.",
    createdAt: ago(4),
  }),
  policyEvent({
    code: "30D",
    name: "Clean Vehicle Credit",
    week: "2026-W20",
    weekStart: "2026-05-11",
    docId: "congress:hr-9211",
    docSource: "congress",
    agency: "House Ways and Means",
    title: "EV Credit Reform Act discussion draft",
    url: "https://www.congress.gov/bill/hr-9211",
    delta: -0.05,
    dims: { specificity: 0, durability: -0.5, enforceability: 0 },
    rationale: "House Ways and Means draft narrows price caps and sourcing rules.",
    createdAt: ago(10),
  }),
  policyEvent({
    code: "45X",
    name: "Advanced Manufacturing Production Credit",
    week: "2026-W19",
    weekStart: "2026-05-04",
    docId: "treasury:45x-faq",
    docSource: "treasury",
    agency: "Treasury Department",
    title: "Treasury 45X FAQ update on critical minerals",
    url: "https://home.treasury.gov/system/files/136/45X-FAQ.pdf",
    delta: 0,
    dims: { specificity: 0, durability: 0, enforceability: 0 },
    rationale: "Treasury clarified critical minerals eligibility — no PCI change, but reduces ambiguity.",
    createdAt: ago(18),
  }),
  policyEvent({
    code: "45Q",
    name: "Carbon Oxide Sequestration Credit",
    week: "2026-W19",
    weekStart: "2026-05-04",
    docId: "federal_register:45q-rule",
    docSource: "federal_register",
    agency: "EPA",
    title: "EPA finalizes 45Q sequestration measurement rule",
    url: "https://www.federalregister.gov/documents/45q-rule",
    delta: 0.0,
    dims: { specificity: 0.0, durability: 0.0, enforceability: 0 },
    rationale: "Final EPA measurement rule resolves a multi-year ambiguity.",
    createdAt: ago(20),
  }),
  policyEvent({
    code: "50144",
    name: "Energy Infrastructure Reinvestment",
    week: "2026-W18",
    weekStart: "2026-04-27",
    docId: "omb:apportionment-50144",
    docSource: "omb",
    agency: "OMB",
    title: "OMB pauses 50144 disbursements pending review",
    url: "https://www.whitehouse.gov/omb/example-50144",
    delta: -0.33,
    dims: { specificity: 0, durability: -1, enforceability: 0 },
    rationale: "OMB apportionment notice pauses Energy Infrastructure Reinvestment disbursements pending policy review.",
    createdAt: ago(25),
  }),
]

const provisionTimelines = currentPci.flatMap((policy) => [
  timeline(policy, "2022-W33", "2022-08-15", policy.baseline_pci),
  timeline(policy, "2025-W26", "2025-06-23", policy.baseline_pci),
  timeline(policy, "2025-W52", "2025-12-22", policy.baseline_pci + policy.delta_this_week * 0.4),
  timeline(policy, "2026-W14", "2026-03-30", policy.baseline_pci + policy.delta_this_week * 0.7),
  timeline(policy, "2026-W21", "2026-05-18", policy.pci),
])

const forecastPerformance = [
  {
    forecast_count: openForecasts.length + resolvedForecasts.length,
    resolved_count: resolvedForecasts.length,
    model_brier_score: 0.0196,
    market_brier_score: 0.0324,
    pci_brier_score: 0.0144,
  },
]

const pipelineRuns = [
  {
    run_id: "test-run",
    run_type: "weekly",
    status: "success",
    started_at: now,
    completed_at: now,
    git_sha: null,
    source: "mock-supabase",
    error_summary: null,
    metadata: {
      policy_events: policyEvents.length,
      markets: marketSnapshots.length,
      forecasts: openForecasts.length,
      trade_proposals: tradeProposals.length,
      market_scan: {
        scanned: 16_095,
        published: marketSnapshots.length,
        rejected_not_policy_relevant: marketDiscoveryCandidates.filter((c) => !c.policy_relevant).length,
      },
    },
  },
]

const evidenceItems = policyEvents.map((event) => evidenceFromEvent(event))

const sourceLinks = [
  ...policyEvents.map((event) => ({
    link_id: `link:policy_events:${event.event_id}`,
    evidence_id: `evidence:${event.event_id}`,
    target_table: "policy_events",
    target_id: event.event_id,
    link_type: "primary_source",
    created_at: now,
  })),
  ...openForecasts.map((f) => ({
    link_id: `link:forecasts:${f.forecast_id}`,
    evidence_id: `evidence:${f.source_doc.doc_id}:${f.provision}`,
    target_table: "forecasts",
    target_id: f.forecast_id,
    link_type: "forecast_basis",
    created_at: now,
  })),
  ...marketSnapshots.map((m) => ({
    link_id: `link:market_snapshots:${m.venue}:${m.ticker}`,
    evidence_id: evidenceIdForCode(m.query_name ?? ""),
    target_table: "market_snapshots",
    target_id: `${m.venue}:${m.ticker}`,
    link_type: "market_match",
    created_at: now,
  })),
]

const sourceHealth = [
  {
    source: "federal_register",
    source_name: "Federal Register",
    status: "success",
    last_attempt_at: now,
    last_success_at: now,
    latency_ms: 123,
    row_count: policyEvents.filter((e) => e.doc_source === "federal_register").length,
    last_error_class: null,
    last_error_summary: null,
    details: {},
  },
  {
    source: "congress",
    source_name: "Congress.gov",
    status: "success",
    last_attempt_at: now,
    last_success_at: now,
    latency_ms: 284,
    row_count: policyEvents.filter((e) => e.doc_source === "congress").length,
    last_error_class: null,
    last_error_summary: null,
    details: {},
  },
  {
    source: "treasury",
    source_name: "Treasury",
    status: "success",
    last_attempt_at: now,
    last_success_at: now,
    latency_ms: 412,
    row_count: policyEvents.filter((e) => e.doc_source === "treasury").length,
    last_error_class: null,
    last_error_summary: null,
    details: {},
  },
  {
    source: "omb",
    source_name: "OMB",
    status: "success",
    last_attempt_at: now,
    last_success_at: now,
    latency_ms: 198,
    row_count: policyEvents.filter((e) => e.doc_source === "omb").length,
    last_error_class: null,
    last_error_summary: null,
    details: {},
  },
  {
    source: "kalshi",
    source_name: "Kalshi markets",
    status: "success",
    last_attempt_at: now,
    last_success_at: now,
    latency_ms: 4_372,
    row_count: 5_000,
    last_error_class: null,
    last_error_summary: null,
    details: {
      scanned: 5_000,
      published: marketSnapshots.filter((m) => m.venue === "kalshi").length,
      stored_candidates: marketDiscoveryCandidates.filter((c) => c.venue === "kalshi").length,
      rate_limited: 0,
    },
  },
  {
    source: "polymarket",
    source_name: "Polymarket markets",
    status: "success",
    last_attempt_at: now,
    last_success_at: now,
    latency_ms: 14_644,
    row_count: 11_095,
    last_error_class: null,
    last_error_summary: null,
    details: {
      scanned: 11_095,
      published: marketSnapshots.filter((m) => m.venue === "polymarket").length,
      stored_candidates: marketDiscoveryCandidates.filter((c) => c.venue === "polymarket").length,
      rate_limited: 0,
    },
  },
]

const views = {
  v_current_pci: currentPci,
  v_open_forecasts: openForecasts,
  v_resolved_forecasts: resolvedForecasts,
  v_trade_proposals: tradeProposals,
  v_market_snapshots: marketSnapshots,
  v_market_discovery_candidates: marketDiscoveryCandidates,
  v_policy_events: policyEvents,
  v_pipeline_status: pipelineRuns,
  v_provision_timelines: provisionTimelines,
  v_forecast_performance: forecastPerformance,
  v_evidence_items: evidenceItems,
  v_source_links: sourceLinks,
  v_source_health: sourceHealth,
}

function provision(code, name, pci, specificity, durability, enforceability, obbbaPostPci, delta = 0) {
  return {
    code,
    name,
    provision_type: code.startsWith("50") ? "appropriation" : "tax_credit",
    primary_channel: "paper channel",
    paper_role: "paper anchor",
    week: "2026-W21",
    week_start: "2026-05-18",
    pci,
    specificity,
    durability,
    enforceability,
    delta_this_week: delta,
    data_origin: "paper_anchor",
    baseline_pci: pci - delta,
    obbba_delta_pci: obbbaPostPci - (pci - delta),
    obbba_post_pci: obbbaPostPci,
    obbba_summary: "Paper OBBBA stress-test anchor.",
    updated_at: now,
  }
}

function forecast(arg) {
  return {
    forecast_id: `forecast:2026-W21:${arg.docSource}:${slug(arg.docId)}:${arg.code}:pci_signal:${arg.ticker}`,
    created_at: now,
    venue: "kalshi",
    market_ticker: arg.ticker,
    market_title: arg.title,
    market_rules: arg.rules,
    market_close_time: "2026-12-31T23:59:59.000Z",
    provision: arg.code,
    provision_name: arg.name,
    dimension: arg.dimension,
    pci_delta: arg.delta,
    shock_type: arg.delta < 0 ? "negative_credibility_shock" : "positive_credibility_shock",
    market_probability: arg.market,
    pci_rule_probability: arg.pciRule,
    llm_probability: arg.llm,
    model_probability: arg.model,
    edge: Number((arg.market - arg.model).toFixed(2)),
    confidence: arg.confidence,
    method_version: "hybrid_market_pci_llm_v1",
    model_provider: "offline",
    model_name: "paper_grounded_heuristic_v1",
    source_doc: {
      doc_id: arg.docId,
      source: arg.docSource,
      title: arg.docTitle,
      url: arg.docUrl,
    },
    evidence: { source_evidence: arg.evidence },
    reasoning: { match: { policy_relevant: true, resolution_clear: true } },
    counterarguments: arg.counter,
    resolution_risk_notes: arg.risk,
  }
}

function snapshot({ code, venue, ticker, title, yesAsk, yesBid, volume, liquidity, resolution }) {
  return {
    snapshot_id: `snapshot:${venue}:${ticker}`,
    generated_at: now,
    venue,
    ticker,
    event_ticker: `${ticker}-event`,
    title,
    subtitle: `${venue.toUpperCase()} · ${code}`,
    status: "active",
    result: null,
    yes_bid: yesBid,
    yes_ask: yesAsk,
    bid_ask_spread: Number((yesAsk - yesBid).toFixed(3)),
    market_probability: yesAsk,
    liquidity_dollars: liquidity,
    volume,
    volume_24h: Math.round(volume * 0.02),
    open_interest: Math.round(liquidity * 0.6),
    close_time: "2026-12-31T23:59:59.000Z",
    expected_expiration_time: "2027-01-15T00:00:00.000Z",
    latest_expiration_time: "2027-02-15T00:00:00.000Z",
    policy_relevant: true,
    resolution_text: resolution,
    query_name: `provision:${code}`,
  }
}

function policyEvent({ code, name, week, weekStart, docId, docSource, agency, title, url, delta, dims, rationale, createdAt }) {
  return {
    event_id: `${week}:${docSource}:${slug(docId)}:${code}`,
    provision: code,
    provision_name: name,
    week,
    week_start: weekStart,
    doc_id: docId,
    doc_source: docSource,
    agency,
    title,
    url,
    pci_delta: delta,
    dimension_deltas: dims,
    rationale,
    confidence: 0.82,
    prompt_version: "test",
    scored_at: createdAt,
    created_at: createdAt,
  }
}

function evidenceFromEvent(event) {
  return {
    evidence_id: `evidence:${event.event_id}`,
    source_doc_id: event.doc_id,
    provision: event.provision,
    provision_name: event.provision_name,
    evidence_type: "pci_scoring_rationale",
    snippet: event.rationale,
    normalized_signal: `${event.pci_delta >= 0 ? "+" : ""}${event.pci_delta.toFixed(2)} PCI`,
    score_dimension: dominantDim(event.dimension_deltas),
    confidence: 0.82,
    extractor_version: "test",
    created_at: event.created_at,
    source: event.doc_source,
    source_name: prettySource(event.doc_source),
    source_type: "official_text",
    source_title: event.title,
    agency: event.agency,
    url: event.url,
    published_at: event.created_at,
    fetched_at: event.created_at,
    raw_public_metadata: {
      chunk_id: `chunk:${event.doc_source}:${slug(event.doc_id)}:0:${hex(event.event_id)}`,
      chunk_hash: hex(event.event_id) + hex(event.event_id),
      chunk_index: 0,
      section_title: event.title,
      matched_terms: [event.provision, event.agency ?? "Official"],
      retrieval_score: 7.2,
    },
  }
}

function timeline(policy, week, weekStart, pci) {
  return {
    provision: policy.code,
    name: policy.name,
    week,
    week_start: weekStart,
    pci: Number(pci.toFixed(2)),
    specificity: policy.specificity,
    durability: policy.durability,
    enforceability: policy.enforceability,
    n_docs: 0,
    delta_this_week: 0,
    data_origin: policy.data_origin,
    source_event_ids: [],
    provenance_status: "complete",
  }
}

function slug(id) {
  const sep = id.indexOf(":")
  return sep >= 0 ? id.slice(sep + 1) : id
}

function hex(seed) {
  let h = 0
  for (let i = 0; i < seed.length; i += 1) h = (Math.imul(31, h) + seed.charCodeAt(i)) | 0
  return Math.abs(h).toString(16).padStart(12, "0").slice(0, 12)
}

function dominantDim(dims) {
  let best = "specificity"
  let max = 0
  for (const [k, v] of Object.entries(dims ?? {})) {
    if (Math.abs(v) > max) {
      max = Math.abs(v)
      best = k
    }
  }
  return best
}

function prettySource(source) {
  return {
    federal_register: "Federal Register",
    congress: "Congress.gov",
    treasury: "Treasury",
    omb: "OMB",
  }[source] ?? source
}

function evidenceIdForCode(queryName) {
  const code = queryName.replace("provision:", "")
  const event = policyEvents.find((e) => e.provision === code)
  return event ? `evidence:${event.event_id}` : `evidence:${policyEvents[0].event_id}`
}

const server = createServer((request, response) => {
  const url = new URL(request.url ?? "/", "http://127.0.0.1:8787")

  if (request.method === "OPTIONS") {
    response.writeHead(204, corsHeaders())
    response.end()
    return
  }

  if (url.pathname === "/health") {
    respond(response, { ok: true })
    return
  }

  const view = url.pathname.replace("/rest/v1/", "")
  if (Object.hasOwn(views, view)) {
    respond(response, views[view])
    return
  }

  response.writeHead(404, { ...corsHeaders(), "content-type": "application/json" })
  response.end(JSON.stringify({ error: "not found" }))
})

server.listen(8787, "127.0.0.1")

function corsHeaders() {
  return {
    "access-control-allow-origin": "*",
    "access-control-allow-headers": "apikey, authorization, content-type",
    "access-control-allow-methods": "GET, OPTIONS",
  }
}

function respond(response, payload) {
  response.writeHead(200, { ...corsHeaders(), "content-type": "application/json" })
  response.end(JSON.stringify(payload))
}
