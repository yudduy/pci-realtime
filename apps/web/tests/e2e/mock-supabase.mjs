import { createServer } from "node:http"

const now = new Date().toISOString()
const staleTimestamp = "2020-01-01T08:00:00.000Z"
const fixtureModes = new Set([
  "all-views-fail",
  "empty-views",
  "stale-timestamps",
])

const currentPci = [
  policyUnit("30D", "Clean Vehicle Credit", 4.0, 4, 4, 4),
  policyUnit("45Q", "Carbon Oxide Sequestration Credit", 3.0, 5, 4, 4, 4.33),
  policyUnit("45V", "Clean Hydrogen Production Credit", 4.0, 5, 4, 4, 4.33),
  policyUnit("45X", "Advanced Manufacturing Production Credit", 4.67, 5, 4, 5),
  policyUnit("50141", "Loan Programs Office Funding", 3.0, 3, 3, 3),
  policyUnit("50144", "Energy Infrastructure Reinvestment", 3.33, 4, 3, 3),
]

const verticalPci = [
  {
    id: "advanced-manufacturing",
    name: "Advanced Manufacturing",
    coverage_note:
      "Tracks the section 45X production credit only; excludes 48C, tariffs, and state incentives.",
    display_order: 1,
    vertical_pci: 4.67,
    baseline_pci: 4.67,
    weekly_delta: 0.17,
    as_of_week_start: "2026-05-18",
    last_change_week_start: "2026-05-18",
    provisions: ["45X"],
  },
  {
    id: "clean-hydrogen",
    name: "Clean Hydrogen",
    coverage_note:
      "Tracks the section 45V production credit only; excludes DOE hydrogen hub grants.",
    display_order: 2,
    vertical_pci: 4.0,
    baseline_pci: 4.33,
    weekly_delta: -0.33,
    as_of_week_start: "2026-05-18",
    last_change_week_start: "2026-05-18",
    provisions: ["45V"],
  },
  {
    id: "carbon-capture",
    name: "Carbon Capture",
    coverage_note:
      "Tracks the section 45Q sequestration credit only; excludes DAC hub programs.",
    display_order: 3,
    vertical_pci: 3.0,
    baseline_pci: 4.33,
    weekly_delta: -1.5,
    as_of_week_start: "2026-05-18",
    last_change_week_start: "2026-05-18",
    provisions: ["45Q"],
  },
  {
    id: "electric-vehicles",
    name: "Electric Vehicles",
    coverage_note:
      "Tracks the consumer 30D credit only; excludes 45W commercial and 30C charging credits.",
    display_order: 4,
    vertical_pci: 4.0,
    baseline_pci: 4.0,
    weekly_delta: -0.33,
    as_of_week_start: "2026-05-18",
    last_change_week_start: "2026-05-18",
    provisions: ["30D"],
  },
  {
    id: "clean-energy-finance",
    name: "Clean Energy Finance",
    coverage_note:
      "Tracks DOE Loan Programs Office funding (50141) and Energy Infrastructure Reinvestment authority (50144).",
    display_order: 5,
    // Equal-weight blend of the distinct 3.00 and 3.33 provision PCIs.
    vertical_pci: 3.17,
    baseline_pci: 3.17,
    weekly_delta: 0,
    as_of_week_start: "2026-05-18",
    last_change_week_start: null,
    provisions: ["50141", "50144"],
  },
]

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
    schema_version: "schema-b-v1.0.0",
    method_version: "pci-delta-v1",
    scored_at: now,
    created_at: now,
  },
  {
    event_id: "2025-W51:irs:30d-transition:30D",
    provision: "30D",
    provision_name: "Clean Vehicle Credit",
    week: "2025-W51",
    week_start: "2025-12-15",
    doc_id: "irs:30d-transition",
    doc_source: "irs",
    agency: "Internal Revenue Service",
    title: "Clean vehicle credit transition & eligibility guidance",
    url: "https://www.irs.gov/credits-deductions/clean-vehicle-credit-transition",
    pci_delta: -0.1,
    dimension_deltas: { specificity: 0, durability: -0.3, enforceability: 0 },
    rationale: "IRS guidance changes transition rules for manufacturers & buyers.",
    confidence: 0.78,
    prompt_version: "test",
    scored_at: "2025-12-16T18:00:00.000Z",
    created_at: "2025-12-16T18:00:00.000Z",
  },
]
// Representative PCI arcs: the IRA-enactment anchor, the OBBBA stress dip, and
// recent recovery/guidance. Several provisions carry real movement so the trend
// chart and row sparklines render; 50144/50141 stay flat to exercise the
// honest "holding at baseline" state.
const trendArcs = {
  "45X": [
    ["2022-W33", "2022-08-15", 4.0],
    ["2024-W20", "2024-05-13", 4.33],
    ["2025-W30", "2025-07-21", 4.5],
    ["2026-W21", "2026-05-18", 4.67],
  ],
  "45V": [
    ["2022-W33", "2022-08-15", 4.0],
    ["2024-W20", "2024-05-13", 4.33],
    ["2025-W30", "2025-07-21", 4.33],
    ["2026-W21", "2026-05-18", 4.0, ["2026-W21:federal_register:45v-guidance:45V"]],
  ],
  "45Q": [
    ["2022-W33", "2022-08-15", 4.0],
    ["2024-W20", "2024-05-13", 4.0],
    ["2025-W30", "2025-07-21", 4.5],
    ["2026-W21", "2026-05-18", 3.0],
  ],
  "30D": [
    ["2022-W33", "2022-08-15", 4.33],
    ["2026-W21", "2026-05-18", 4.0],
  ],
}
const provisionTimelines = currentPci.flatMap((policy) => {
  const arc = trendArcs[policy.code] ?? [
    ["2022-W33", "2022-08-15", policy.baseline_pci],
    ["2026-W21", "2026-05-18", policy.pci],
  ]
  let previous = null
  return arc.map(([week, weekStart, pci, eventIds = []]) => {
    const delta = previous === null ? 0 : Number((pci - previous).toFixed(2))
    previous = pci
    return timeline(policy, week, weekStart, pci, eventIds, delta)
  })
})
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
    citation_quote: "Treasury guidance narrows eligibility for the clean hydrogen credit.",
    citation_section: "Eligibility",
    citation_page: null,
    citation_url_fragment: null,
    claim_hash: "claim-hash-45v",
    submitted_by_agent_run_id: "agent-run:test-45v",
    extraction_confidence: 0.82,
    raw_public_metadata: {},
    source: "federal_register",
    source_name: "Federal Register",
    source_type: "official_text",
    source_title: "Clean hydrogen production credit guidance",
    agency: "Treasury Department",
    url: "https://www.federalregister.gov/documents/example",
    canonical_url: "https://www.federalregister.gov/documents/example",
    published_at: "2026-05-20T14:00:00.000Z",
    fetched_at: now,
  },
  {
    evidence_id: "evidence:2025-W51:irs:30d-transition:30D",
    source_doc_id: "irs:30d-transition",
    provision: "30D",
    provision_name: "Clean Vehicle Credit",
    evidence_type: "pci_scoring_rationale",
    snippet: "Transition rules changed for manufacturers and buyers.",
    normalized_signal: "-0.10 PCI",
    score_dimension: "durability",
    confidence: 0.78,
    extractor_version: "test",
    created_at: "2025-12-16T18:00:00.000Z",
    citation_quote: "Transition rules apply to manufacturers & buyers.",
    citation_section: "Transition rules",
    citation_page: null,
    citation_url_fragment: null,
    claim_hash: "claim-hash-30d",
    submitted_by_agent_run_id: null,
    extraction_confidence: 0.78,
    raw_public_metadata: {},
    source: "irs",
    source_name: "Internal Revenue Service",
    source_type: "official_text",
    source_title: "Clean vehicle credit transition guidance",
    agency: "Internal Revenue Service",
    url: "https://www.irs.gov/credits-deductions/clean-vehicle-credit-transition",
    canonical_url:
      "https://www.irs.gov/credits-deductions/clean-vehicle-credit-transition",
    published_at: "2025-12-16T12:00:00.000Z",
    fetched_at: "2025-12-16T18:00:00.000Z",
  },
]

const sourceDocuments = [
  {
    source_doc_id: "federal_register:45v-guidance",
    source: "federal_register",
    source_name: "Federal Register",
    source_type: "official_text",
    external_id: "45v-guidance",
    title: "Clean hydrogen production credit guidance",
    agency: "Treasury Department",
    url: "https://www.federalregister.gov/documents/example",
    canonical_url: "https://www.federalregister.gov/documents/example",
    published_at: now,
    fetched_at: now,
    first_seen_at: now,
    last_seen_at: now,
    submitted_by_agent_run_id: "agent-run:test-45v",
    text_excerpt: "Treasury guidance narrows eligibility for the clean hydrogen credit.",
    raw_public_metadata: {
      citation_section: "Eligibility",
    },
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
  {
    link_id: "link:policy_events:2025-W51:irs:30d-transition:30D",
    evidence_id: "evidence:2025-W51:irs:30d-transition:30D",
    target_table: "policy_events",
    target_id: "2025-W51:irs:30d-transition:30D",
    link_type: "primary_source",
    created_at: "2025-12-16T18:00:00.000Z",
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
  {
    source: "kalshi",
    source_name: "Kalshi markets",
    status: "success",
    last_attempt_at: now,
    last_success_at: now,
    latency_ms: 4372,
    row_count: 5000,
    last_error_class: null,
    last_error_summary: null,
    details: {
      scanned: 5000,
      published: 0,
      stored_candidates: 0,
      rate_limited: 0,
    },
  },
  {
    source: "polymarket",
    source_name: "Polymarket markets",
    status: "success",
    last_attempt_at: now,
    last_success_at: now,
    latency_ms: 14644,
    row_count: 11095,
    last_error_class: null,
    last_error_summary: null,
    details: {
      scanned: 11095,
      published: 0,
      stored_candidates: 2,
      rate_limited: 0,
    },
  },
]

const agentEvidenceSubmissions = [
  {
    submission_id: "submission:test-45v",
    agent_run_id: "agent-run:test-45v",
    provision: "45V",
    provision_name: "Clean Hydrogen Production Credit",
    source_doc_id: "federal_register:45v-guidance",
    evidence_id: "evidence:2026-W21:federal_register:45v-guidance:45V",
    event_id: "2026-W21:federal_register:45v-guidance:45V",
    canonical_url: "https://www.federalregister.gov/documents/example",
    source_title: "Clean hydrogen production credit guidance",
    claim_hash: "claim-hash-45v",
    status: "promoted",
    rejection_reason: null,
    promotion_result: {
      week: "2026-W21",
      pci_delta: -0.33,
    },
    submitted_at: now,
    promoted_at: now,
    raw_public_metadata: {},
  },
]

const views = {
  v_vertical_pci: verticalPci,
  v_current_pci: currentPci,
  v_policy_events: policyEvents,
  v_pipeline_status: pipelineRuns,
  v_provision_timelines: provisionTimelines,
  v_evidence_items: evidenceItems,
  v_source_documents: sourceDocuments,
  v_source_links: sourceLinks,
  v_source_health: sourceHealth,
  v_agent_evidence_submissions: agentEvidenceSubmissions,
}

function policyUnit(
  code,
  name,
  pci,
  specificity,
  durability,
  enforceability,
  baselinePci = pci,
) {
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
    baseline_pci: baselinePci,
    updated_at: now,
  }
}

function timeline(policy, week, weekStart, pci, sourceEventIds = [], deltaThisWeek = 0) {
  return {
    provision: policy.code,
    name: policy.name,
    week,
    week_start: weekStart,
    pci,
    specificity: policy.specificity,
    durability: policy.durability,
    enforceability: policy.enforceability,
    n_docs: sourceEventIds.length,
    delta_this_week: deltaThisWeek,
    data_origin: policy.data_origin,
    source_event_ids: sourceEventIds,
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
    const mode = fixtureMode(url)
    if (mode === "all-views-fail") {
      response.writeHead(500, { ...corsHeaders(), "content-type": "application/json" })
      response.end(JSON.stringify({ error: `${view} fixture failure` }))
      return
    }
    respond(response, fixturePayload(view, mode))
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

function fixtureMode(url) {
  const mode = url.searchParams.get("__mock_mode") ?? process.env.MOCK_SUPABASE_MODE
  return fixtureModes.has(mode) ? mode : null
}

function fixturePayload(view, mode) {
  if (mode === "empty-views") return []
  if (mode !== "stale-timestamps") return views[view]

  if (view === "v_pipeline_status") {
    return pipelineRuns.map((run) => ({
      ...run,
      started_at: staleTimestamp,
      completed_at: staleTimestamp,
    }))
  }
  if (view === "v_source_health") {
    return sourceHealth.map((source) => ({
      ...source,
      last_attempt_at: staleTimestamp,
      last_success_at: staleTimestamp,
    }))
  }
  return views[view]
}
