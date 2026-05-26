import { createServer } from "node:http"

const now = "2026-05-24T08:00:00.000Z"

const currentPci = [
  provision("30D", "Clean Vehicle Credit", 4.0, 4, 4, 4, 3.0),
  provision("45Q", "Carbon Oxide Sequestration Credit", 4.33, 5, 4, 4, 4.33),
  provision("45V", "Clean Hydrogen Production Credit", 4.33, 5, 4, 4, 3.33),
  provision("45X", "Advanced Manufacturing Production Credit", 4.67, 5, 4, 5, 3.67),
  provision("50141", "Loan Programs Office Funding", 3.0, 3, 3, 3, 2.33),
  provision("50144", "Energy Infrastructure Reinvestment", 3.33, 4, 3, 3, 2.0),
]

const openForecasts = []
const tradeProposals = []
const marketSnapshots = []
const policyEvents = [
  {
    event_id: "2026-W21:federal_register:45v-guidance:45V",
    provision: "45V",
    provision_name: "Clean Hydrogen Production Credit",
    week: "2026-W21",
    week_start: "2026-05-18",
    doc_id: "federal_register:45v-guidance",
    doc_source: "federal_register",
    agency: "Treasury Department",
    title: "Clean hydrogen production credit guidance",
    url: "https://www.federalregister.gov/documents/example",
    pci_delta: -0.33,
    dimension_deltas: { specificity: -1, durability: 0, enforceability: 0 },
    rationale: "Treasury guidance narrows eligibility for the clean hydrogen credit.",
    confidence: 0.82,
    prompt_version: "test",
    scored_at: now,
    created_at: now,
  },
]
const provisionTimelines = currentPci.flatMap((policy) => [
  timeline(policy, "2022-W33", "2022-08-15", policy.baseline_pci),
  timeline(policy, "2026-W21", "2026-05-18", policy.pci),
])
const forecastPerformance = [
  {
    forecast_count: 0,
    resolved_count: 0,
    model_brier_score: null,
    market_brier_score: null,
    pci_brier_score: null,
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
      policy_events: 0,
      markets: 0,
      forecasts: 0,
      trade_proposals: 0,
      market_scan: {
        scanned: 12,
        published: 0,
        rejected_not_policy_relevant: 12,
      },
    },
  },
]

const evidenceItems = [
  {
    evidence_id: "evidence:2026-W21:federal_register:45v-guidance:45V",
    source_doc_id: "federal_register:45v-guidance",
    provision: "45V",
    provision_name: "Clean Hydrogen Production Credit",
    evidence_type: "pci_scoring_rationale",
    snippet: "Treasury guidance narrows eligibility for the clean hydrogen credit.",
    normalized_signal: "-0.33 PCI",
    score_dimension: "specificity",
    confidence: 0.82,
    extractor_version: "test",
    created_at: now,
    source: "federal_register",
    source_name: "Federal Register",
    source_type: "official_text",
    source_title: "Clean hydrogen production credit guidance",
    agency: "Treasury Department",
    url: "https://www.federalregister.gov/documents/example",
    published_at: now,
    fetched_at: now,
  },
]

const sourceLinks = [
  {
    link_id: "link:policy_events:2026-W21:federal_register:45v-guidance:45V",
    evidence_id: "evidence:2026-W21:federal_register:45v-guidance:45V",
    target_table: "policy_events",
    target_id: "2026-W21:federal_register:45v-guidance:45V",
    link_type: "primary_source",
    created_at: now,
  },
]

const sourceHealth = [
  {
    source: "federal_register",
    source_name: "Federal Register",
    status: "success",
    last_attempt_at: now,
    last_success_at: now,
    latency_ms: 123,
    row_count: 1,
    last_error_class: null,
    last_error_summary: null,
    details: {},
  },
]

const views = {
  v_current_pci: currentPci,
  v_open_forecasts: openForecasts,
  v_resolved_forecasts: [],
  v_trade_proposals: tradeProposals,
  v_market_snapshots: marketSnapshots,
  v_policy_events: policyEvents,
  v_pipeline_status: pipelineRuns,
  v_provision_timelines: provisionTimelines,
  v_forecast_performance: forecastPerformance,
  v_evidence_items: evidenceItems,
  v_source_links: sourceLinks,
  v_source_health: sourceHealth,
}

function provision(code, name, pci, specificity, durability, enforceability, obbbaPostPci) {
  return {
    code,
    name,
    provision_type: code.startsWith("50") ? "appropriation" : "tax_credit",
    primary_channel: "paper channel",
    paper_role: "paper anchor",
    week: "2022-W33",
    week_start: "2022-08-15",
    pci,
    specificity,
    durability,
    enforceability,
    delta_this_week: 0,
    data_origin: "paper_anchor",
    baseline_pci: pci,
    obbba_delta_pci: obbbaPostPci - pci,
    obbba_post_pci: obbbaPostPci,
    obbba_summary: "Paper OBBBA stress-test anchor.",
    updated_at: now,
  }
}

function timeline(policy, week, weekStart, pci) {
  return {
    provision: policy.code,
    name: policy.name,
    week,
    week_start: weekStart,
    pci,
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
