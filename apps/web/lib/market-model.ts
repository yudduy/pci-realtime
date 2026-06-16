import { policyCopy } from "@/lib/policy-copy"
import type {
  CurrentPci,
  Forecast,
  MarketSnapshot,
  RegistryData,
  ResolvedForecast,
} from "@/lib/data"

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
  sourceCount: number
  searchText: string
  policy?: CurrentPci
  forecast?: Forecast
  market?: MarketSnapshot
  resolved?: ResolvedForecast
}

export function latestCompletedRun(data: RegistryData) {
  return data.pipelineRuns.find((run) => run.status === "success") ?? data.pipelineRuns[0] ?? null
}

export function buildPolicyMarkets(data: RegistryData): PolicyMarket[] {
  const sourceCounts = countSources(data)
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
      sourceCount: sourceCounts.get(`forecast:${forecast.forecast_id}`) ?? 0,
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
      sourceCount:
        sourceCounts.get(`market:${market.venue}:${market.ticker}`) ??
        sourceCounts.get(`market_snapshots:${market.venue}:${market.ticker}`) ??
        0,
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
    const eventCount = data.policyEvents.filter((event) => event.provision === policy.code).length

    return {
      id: `policy:${policy.code}`,
      kind: "policy",
      provision: policy.code,
      provisionName: copy.name,
      lane: copy.lane,
      title: copy.question,
      subtitle: copy.formalName,
      status: "Current PCI",
      primaryLabel: "PCI",
      primaryValue: policy.pci ?? policy.baseline_pci,
      secondaryLabel: "Events",
      secondaryValue: eventCount,
      edge: null,
      confidence: null,
      volume: null,
      liquidity: null,
      closeTime: null,
      updatedAt: policy.updated_at,
      ticker: policy.code,
      venue: "pci",
      sourceCount: eventCount,
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
      sourceCount: sourceCounts.get(`forecast:${row.forecast_id}`) ?? 0,
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

function countSources(data: RegistryData) {
  const linksByTarget = new Map<string, Set<string>>()
  for (const link of data.sourceLinks) {
    const targetKey =
      link.target_table === "forecasts"
        ? `forecast:${link.target_id}`
        : link.target_table === "market_snapshots"
          ? `market_snapshots:${link.target_id}`
          : `${link.target_table}:${link.target_id}`
    if (!linksByTarget.has(targetKey)) linksByTarget.set(targetKey, new Set())
    linksByTarget.get(targetKey)?.add(link.evidence_id)
  }
  return new Map(
    [...linksByTarget.entries()].map(([key, evidenceIds]) => [key, evidenceIds.size]),
  )
}

function edgeStatus(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "No edge"
  const sign = value >= 0 ? "+" : ""
  return `${sign}${Math.round(value * 100)} pts edge`
}
