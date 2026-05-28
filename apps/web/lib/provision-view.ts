import { policyCopy } from "@/lib/policy-copy"
import { buildMarketCoverage, candidatesForProvision } from "@/lib/market-coverage"
import { buildPolicyMarkets, type PolicyMarket } from "@/lib/market-model"
import { buildMarketProvenance, type MarketProvenance } from "@/lib/provenance"
import type {
  CurrentPci,
  Forecast,
  MarketDiscoveryCandidate,
  MarketSnapshot,
  PolicyEvent,
  ProvisionTimeline,
  RegistryData,
  ResolvedForecast,
} from "@/lib/data"

export type ProvisionView = {
  code: string
  name: string
  formalName: string
  question: string
  lane: string
  policy: CurrentPci | null
  baselinePci: number
  baselineDimensions: { specificity: number; durability: number; enforceability: number }
  stressPci: number
  pciMarket: PolicyMarket
  timelines: ProvisionTimeline[]
  events: PolicyEvent[]
  eligibleMarkets: MarketSnapshot[]
  nearMissMarkets: MarketDiscoveryCandidate[]
  openForecasts: Forecast[]
  resolvedForecasts: ResolvedForecast[]
  provenance: MarketProvenance
  marketSubrows: SubMarketRow[]
  coverage: ReturnType<typeof buildMarketCoverage>
  scopedCandidates: ReturnType<typeof candidatesForProvision>
}

export type SubMarketRow = {
  id: string
  marketKey: string
  title: string
  venue: string
  ticker: string
  status: string
  yes: number | null
  no: number | null
  volume: number | null
  liquidity: number | null
  closeTime: string | null
  policyRelevant: boolean
  resolutionClear: boolean
  url: string | null
  source: "snapshot" | "candidate"
  rejectionReasons: string[]
}

export function getProvisionView(data: RegistryData, code: string): ProvisionView | null {
  const copy = policyCopy(code)
  if (!copy || copy.code !== code) return null
  const policy = data.currentPci.find((row) => row.code === code) ?? null
  const allMarkets = buildPolicyMarkets(data)
  const pciMarket = allMarkets.find(
    (market) => market.kind === "policy" && market.provision === code,
  ) ?? {
    id: `policy:${code}`,
    kind: "policy" as const,
    provision: code,
    provisionName: copy.name,
    lane: copy.lane,
    title: copy.question,
    subtitle: copy.formalName,
    status: "No public market scan yet",
    primaryLabel: "Score",
    primaryValue: copy.baseline,
    secondaryLabel: "Stress",
    secondaryValue: copy.stress,
    edge: null,
    confidence: null,
    volume: null,
    liquidity: null,
    closeTime: null,
    updatedAt: null,
    ticker: code,
    venue: "pci",
    sourceCount: 0,
    searchText: code,
    policy: undefined,
    forecast: undefined,
    market: undefined,
    resolved: undefined,
  }

  const events = data.policyEvents
    .filter((event) => event.provision === code)
    .sort((a, b) => Number(new Date(b.created_at ?? b.week_start)) - Number(new Date(a.created_at ?? a.week_start)))

  const eligibleMarkets = data.marketSnapshots.filter(
    (snapshot) => provisionMatchesSnapshot(snapshot, code),
  )
  const coverage = buildMarketCoverage(data)
  const scopedCandidates = candidatesForProvision(data.marketDiscoveryCandidates, code)
  const nearMissMarkets = scopedCandidates.filter((candidate) => !candidate.eligible_snapshot)
  const openForecasts = data.openForecasts.filter((forecast) => forecast.provision === code)
  const resolvedForecasts = data.resolvedForecasts.filter((forecast) => forecast.provision === code)
  const timelines = data.provisionTimelines.filter((row) => row.provision === code)

  const provenance = buildMarketProvenance(pciMarket, data)

  const marketSubrows: SubMarketRow[] = [
    ...eligibleMarkets.map<SubMarketRow>((snapshot) => ({
      id: `snapshot:${snapshot.venue}:${snapshot.ticker}`,
      marketKey: `${snapshot.venue}:${snapshot.ticker}`,
      title: snapshot.title ?? snapshot.subtitle ?? snapshot.ticker,
      venue: snapshot.venue,
      ticker: snapshot.ticker,
      status: snapshot.status ?? "Active",
      yes: snapshot.yes_ask ?? snapshot.market_probability,
      no:
        snapshot.yes_bid === null || snapshot.yes_bid === undefined
          ? null
          : 1 - snapshot.yes_bid,
      volume: snapshot.volume,
      liquidity: snapshot.liquidity_dollars,
      closeTime: snapshot.close_time,
      policyRelevant: snapshot.policy_relevant,
      resolutionClear: Boolean(snapshot.resolution_text),
      url: null,
      source: "snapshot",
      rejectionReasons: [],
    })),
    ...nearMissMarkets.map<SubMarketRow>((candidate) => ({
      id: `candidate:${candidate.candidate_id}`,
      marketKey: `${candidate.venue}:${candidate.ticker}`,
      title: candidate.title,
      venue: candidate.venue,
      ticker: candidate.ticker,
      status: candidate.status ?? "Rejected",
      yes: null,
      no: null,
      volume: candidate.volume,
      liquidity: candidate.liquidity_dollars,
      closeTime: null,
      policyRelevant: candidate.policy_relevant,
      resolutionClear: candidate.resolution_clear,
      url: candidate.market_url,
      source: "candidate",
      rejectionReasons: candidate.rejection_reasons,
    })),
  ]

  return {
    code,
    name: copy.name,
    formalName: copy.formalName,
    question: copy.question,
    lane: copy.lane,
    policy,
    baselinePci: copy.baseline,
    baselineDimensions: {
      specificity: copy.specificity,
      durability: copy.durability,
      enforceability: copy.enforceability,
    },
    stressPci: copy.stress,
    pciMarket,
    timelines,
    events,
    eligibleMarkets,
    nearMissMarkets,
    openForecasts,
    resolvedForecasts,
    provenance,
    marketSubrows,
    coverage,
    scopedCandidates,
  }
}

function provisionMatchesSnapshot(snapshot: MarketSnapshot, code: string) {
  const candidates = [snapshot.query_name, snapshot.title, snapshot.subtitle, snapshot.ticker, snapshot.event_ticker]
  return candidates.some((value) => typeof value === "string" && value.toUpperCase().includes(code.toUpperCase()))
}
