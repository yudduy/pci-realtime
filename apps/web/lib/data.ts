import { policyCopy } from "@/lib/policy-copy"

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

export type PolicyMarketKind = "forecast" | "policy" | "market" | "resolved"

export type PolicyMarket = {
  id: string
  kind: PolicyMarketKind
  provision: string
  provisionName: string
  lane: string
  title: string
  subtitle: string
  status: string
  primaryLabel: string
  primaryValue: number | null
  secondaryLabel: string
  secondaryValue: number | null
  edge: number | null
  confidence: number | null
  volume: number | null
  liquidity: number | null
  closeTime: string | null
  updatedAt: string | null
  ticker: string | null
  venue: string | null
  searchText: string
  policy?: CurrentPci
  forecast?: Forecast
  market?: MarketSnapshot
  resolved?: ResolvedForecast
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

export function latestCompletedRun(data: RegistryData) {
  return data.pipelineRuns.find((run) => run.status === "success") ?? data.pipelineRuns[0] ?? null
}

export function buildPolicyMarkets(data: RegistryData): PolicyMarket[] {
  const forecasts = data.openForecasts.map((forecast): PolicyMarket => {
    const copy = policyCopy(forecast.provision, forecast.provision_name)
    const title =
      forecast.market_title ?? `${forecast.venue.toUpperCase()} ${forecast.market_ticker}`

    return {
      id: `forecast:${forecast.forecast_id}`,
      kind: "forecast",
      provision: forecast.provision,
      provisionName: copy.name,
      lane: copy.lane,
      title,
      subtitle: `${copy.name} / ${forecast.market_ticker}`,
      status: edgeStatus(forecast.edge),
      primaryLabel: "Market",
      primaryValue: forecast.market_probability,
      secondaryLabel: "Model",
      secondaryValue: forecast.model_probability,
      edge: forecast.edge,
      confidence: forecast.confidence,
      volume: null,
      liquidity: null,
      closeTime: forecast.market_close_time,
      updatedAt: forecast.created_at,
      ticker: forecast.market_ticker,
      venue: forecast.venue,
      searchText: [
        title,
        copy.name,
        copy.formalName,
        forecast.market_ticker,
        forecast.provision,
        "forecast",
      ].join(" "),
      forecast,
    }
  })

  const markets = data.marketSnapshots.map((market): PolicyMarket => {
    const title = market.title ?? market.subtitle ?? market.event_ticker ?? market.ticker
    const copy = policyCopy(market.query_name ?? "", market.query_name)

    return {
      id: `market:${market.venue}:${market.ticker}`,
      kind: "market",
      provision: copy.code,
      provisionName: copy.name,
      lane: copy.lane,
      title,
      subtitle: `${market.venue.toUpperCase()} / ${market.ticker}`,
      status: market.status ?? "Market",
      primaryLabel: "Yes",
      primaryValue: market.yes_ask ?? market.market_probability,
      secondaryLabel: "No",
      secondaryValue: market.yes_bid === null || market.yes_bid === undefined ? null : 1 - market.yes_bid,
      edge: null,
      confidence: null,
      volume: market.volume,
      liquidity: market.liquidity_dollars,
      closeTime: market.close_time,
      updatedAt: market.generated_at,
      ticker: market.ticker,
      venue: market.venue,
      searchText: [
        title,
        market.ticker,
        market.event_ticker,
        market.query_name,
        market.status,
        "market",
      ].join(" "),
      market,
    }
  })

  const policies = data.currentPci.map((policy): PolicyMarket => {
    const copy = policyCopy(policy.code, policy.name)

    return {
      id: `policy:${policy.code}`,
      kind: "policy",
      provision: policy.code,
      provisionName: copy.name,
      lane: copy.lane,
      title: copy.question,
      subtitle: copy.formalName,
      status: "Waiting for a clean public market",
      primaryLabel: "PCI",
      primaryValue: policy.pci ?? policy.baseline_pci,
      secondaryLabel: "Stress",
      secondaryValue: policy.obbba_post_pci,
      edge: null,
      confidence: null,
      volume: null,
      liquidity: null,
      closeTime: null,
      updatedAt: policy.updated_at,
      ticker: policy.code,
      venue: "pci",
      searchText: [
        policy.code,
        policy.name,
        copy.name,
        copy.formalName,
        copy.lane,
        "policy",
      ].join(" "),
      policy,
    }
  })

  const resolved = data.resolvedForecasts.map((row): PolicyMarket => {
    const copy = policyCopy(row.provision, row.provision_name)

    return {
      id: `resolved:${row.forecast_id}`,
      kind: "resolved",
      provision: row.provision,
      provisionName: copy.name,
      lane: copy.lane,
      title: row.market_title ?? row.market_ticker,
      subtitle: `${copy.name} / ${row.market_ticker}`,
      status: row.result,
      primaryLabel: "Model",
      primaryValue: row.model_probability,
      secondaryLabel: "Market",
      secondaryValue: row.market_probability,
      edge: row.edge,
      confidence: row.confidence,
      volume: null,
      liquidity: null,
      closeTime: row.resolved_at,
      updatedAt: row.resolved_at,
      ticker: row.market_ticker,
      venue: row.venue,
      searchText: [
        row.market_title,
        row.market_ticker,
        copy.name,
        row.result,
        "resolved",
      ].join(" "),
      resolved: row,
    }
  })

  return [...forecasts, ...markets, ...policies, ...resolved]
}

function edgeStatus(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "No edge"
  const sign = value >= 0 ? "+" : ""
  return `${sign}${Math.round(value * 100)} pts edge`
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
  const pipelineRuns = pipelineRunsResult.rows
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
