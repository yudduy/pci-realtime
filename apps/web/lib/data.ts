export type CurrentPci = {
  code: string
  name: string
  provision_type: string
  primary_channel: string
  paper_role?: string
  week: string | null
  week_start: string | null
  pci: number | null
  specificity: number | null
  durability: number | null
  enforceability: number | null
  delta_this_week: number | null
  data_origin: string | null
  baseline_pci: number
  obbba_delta_pci?: number
  obbba_post_pci: number
  obbba_summary: string
  updated_at: string | null
}

export type Forecast = {
  forecast_id: string
  created_at: string
  venue: string
  market_ticker: string
  market_title: string | null
  market_rules: string | null
  market_close_time: string | null
  provision: string
  provision_name: string
  dimension: string | null
  pci_delta: number | null
  shock_type: string | null
  market_probability: number
  pci_rule_probability: number
  llm_probability: number | null
  model_probability: number
  edge: number
  confidence: number
  method_version?: string | null
  model_provider?: string | null
  model_name?: string | null
  source_doc: Record<string, unknown>
  evidence: Record<string, unknown>
  reasoning: Record<string, unknown>
  counterarguments: string | null
  resolution_risk_notes: string | null
}

export type TradeProposal = {
  proposal_id: string
  created_at: string
  forecast_id: string
  venue: string
  market_ticker: string
  edge: number
  confidence: number
  risk_passed: boolean
  approval_status: string
  human_approval_required: boolean
  public_execution_status: string
  rejection_reasons: string[]
}

export type MarketSnapshot = {
  snapshot_id: string
  generated_at: string
  venue: string
  ticker: string
  event_ticker: string | null
  title: string | null
  subtitle: string | null
  status: string | null
  result: string | null
  yes_bid: number | null
  yes_ask: number | null
  bid_ask_spread: number | null
  market_probability: number | null
  liquidity_dollars: number | null
  volume: number | null
  volume_24h: number | null
  open_interest: number | null
  close_time: string | null
  expected_expiration_time: string | null
  latest_expiration_time: string | null
  policy_relevant: boolean
  resolution_text: string | null
  query_name: string | null
}

export type PolicyEvent = {
  event_id: string
  provision: string
  provision_name: string
  week: string
  week_start: string
  agency: string | null
  doc_id?: string
  doc_source?: string | null
  title: string | null
  url: string | null
  pci_delta: number
  dimension_deltas: Record<string, number>
  rationale: string | null
  confidence: number | null
  prompt_version?: string | null
  scored_at?: string | null
  created_at: string
}

export type ResolvedForecast = {
  forecast_id: string
  created_at: string
  venue: string
  market_ticker: string
  market_title: string | null
  provision: string
  provision_name: string
  market_probability: number
  pci_rule_probability: number
  model_probability: number
  edge: number
  confidence: number
  result: string
  settlement_value: number
  resolved_at: string
  brier_score: number
}

export type PipelineRun = {
  run_id: string
  run_type: string
  status: string
  started_at: string
  completed_at: string | null
  git_sha?: string | null
  source: string
  error_summary: string | null
  metadata: Record<string, unknown>
}

export type ProvisionTimeline = {
  provision: string
  name: string
  week: string
  week_start: string
  pci: number
  specificity: number
  durability: number
  enforceability: number
  n_docs: number
  delta_this_week: number
  data_origin: string
  source_event_ids: string[]
  provenance_status: string
}

export type ForecastPerformance = {
  forecast_count: number
  resolved_count: number
  model_brier_score: number | null
  market_brier_score: number | null
  pci_brier_score: number | null
}

export type RegistryData = {
  currentPci: CurrentPci[]
  openForecasts: Forecast[]
  resolvedForecasts: ResolvedForecast[]
  tradeProposals: TradeProposal[]
  marketSnapshots: MarketSnapshot[]
  policyEvents: PolicyEvent[]
  pipelineRuns: PipelineRun[]
  provisionTimelines: ProvisionTimeline[]
  forecastPerformance: ForecastPerformance | null
  connected: boolean
  viewErrors: string[]
}

function supabaseConfig() {
  const url = process.env.SUPABASE_URL ?? process.env.NEXT_PUBLIC_SUPABASE_URL
  const key =
    process.env.SUPABASE_ANON_KEY ??
    process.env.SUPABASE_PUBLISHABLE_KEY ??
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ??
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

  if (!url || !key) return null
  return { url: url.replace(/\/$/, ""), key }
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : String(error)
}

async function fetchView<T>(
  view: string,
  query = "select=*",
): Promise<{ rows: T[]; error: string | null }> {
  const config = supabaseConfig()
  if (!config) return { rows: [], error: null }

  try {
    const response = await fetch(`${config.url}/rest/v1/${view}?${query}`, {
      headers: {
        apikey: config.key,
        authorization: `Bearer ${config.key}`,
      },
      cache: "no-store",
    })

    if (!response.ok) return { rows: [], error: `${view}: ${response.status}` }
    return { rows: (await response.json()) as T[], error: null }
  } catch (error) {
    return { rows: [], error: `${view}: ${errorMessage(error)}` }
  }
}

export function emptyRegistryData(viewErrors: string[] = []): RegistryData {
  return {
    currentPci: [],
    openForecasts: [],
    resolvedForecasts: [],
    tradeProposals: [],
    marketSnapshots: [],
    policyEvents: [],
    pipelineRuns: [],
    provisionTimelines: [],
    forecastPerformance: null,
    connected: false,
    viewErrors,
  }
}

export async function getRegistryData(): Promise<RegistryData> {
  const config = supabaseConfig()
  const [
    currentPciResult,
    openForecastsResult,
    resolvedForecastsResult,
    tradeProposalsResult,
    marketSnapshotsResult,
    policyEventsResult,
    pipelineRunsResult,
    provisionTimelinesResult,
    forecastPerformanceResult,
  ] = await Promise.all([
    fetchView<CurrentPci>("v_current_pci", "select=*&order=code.asc"),
    fetchView<Forecast>("v_open_forecasts", "select=*&order=created_at.desc"),
    fetchView<ResolvedForecast>("v_resolved_forecasts", "select=*&order=resolved_at.desc&limit=8"),
    fetchView<TradeProposal>("v_trade_proposals", "select=*&order=created_at.desc"),
    fetchView<MarketSnapshot>("v_market_snapshots", "select=*&order=generated_at.desc&limit=12"),
    fetchView<PolicyEvent>("v_policy_events", "select=*&order=created_at.desc&limit=10"),
    fetchView<PipelineRun>("v_pipeline_status", "select=*&limit=5"),
    fetchView<ProvisionTimeline>(
      "v_provision_timelines",
      "select=*&order=provision.asc,week_start.asc&limit=240",
    ),
    fetchView<ForecastPerformance>("v_forecast_performance", "select=*&limit=1"),
  ])
  const viewErrors = [
    currentPciResult.error,
    openForecastsResult.error,
    resolvedForecastsResult.error,
    tradeProposalsResult.error,
    marketSnapshotsResult.error,
    policyEventsResult.error,
    pipelineRunsResult.error,
    provisionTimelinesResult.error,
    forecastPerformanceResult.error,
  ].filter((error): error is string => Boolean(error))

  const currentPci = currentPciResult.rows
  const openForecasts = openForecastsResult.rows
  const resolvedForecasts = resolvedForecastsResult.rows
  const tradeProposals = tradeProposalsResult.rows
  const marketSnapshots = marketSnapshotsResult.rows
  const policyEvents = policyEventsResult.rows
  const pipelineRuns = pipelineRunsResult.rows.map((run) => ({
    ...run,
    source: "registry",
  }))
  const provisionTimelines = provisionTimelinesResult.rows
  const forecastPerformance = forecastPerformanceResult.rows[0] ?? null

  return {
    currentPci,
    openForecasts,
    resolvedForecasts,
    tradeProposals,
    marketSnapshots,
    policyEvents,
    pipelineRuns,
    provisionTimelines,
    forecastPerformance,
    connected: Boolean(config),
    viewErrors,
  }
}
