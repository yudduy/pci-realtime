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
const policyEvents = []
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
