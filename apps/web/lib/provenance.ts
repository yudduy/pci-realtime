import type {
  EvidenceItem,
  PolicyEvent,
  RegistryData,
  SourceLink,
  TradeProposal,
} from "@/lib/data"
import { buildMarketCoverage, candidatesForProvision } from "@/lib/market-coverage"
import type { PolicyMarket } from "@/lib/market-model"

export type ProvenanceCitation = {
  id: string
  sourceTitle: string
  sourceName: string
  sourceUrl: string | null
  sourceType: string | null
  agency: string | null
  quote: string | null
  evidenceType: string
  scoreDimension: string | null
  normalizedSignal: string | null
  confidence: number | null
  extractorVersion: string | null
  createdAt: string
  publishedAt: string | null
  fetchedAt: string | null
  sourceDocumentId: string | null
  chunkId: string | null
  chunkHash: string | null
  sectionTitle: string | null
  matchedTerms: string[]
  retrievalScore: number | null
}

export type CitedClaim = {
  id: string
  claimType: "policy_event" | "pci_score" | "market_match" | "market_rejection" | "forecast" | "trade_proposal"
  title: string
  claimText: string
  citations: ProvenanceCitation[]
  details: string[]
}

export type TraceStep = {
  id: string
  label: string
  detail: string
  status: "complete" | "pending" | "blocked"
}

export type MarketProvenance = {
  claims: CitedClaim[]
  citations: ProvenanceCitation[]
  relatedEvents: PolicyEvent[]
  proposals: TradeProposal[]
  traceSteps: TraceStep[]
}

export function buildMarketProvenance(market: PolicyMarket, data: RegistryData): MarketProvenance {
  const relatedEvents = data.policyEvents
    .filter((event) => event.provision === market.provision)
    .slice(0, 3)
  const proposals = proposalsForMarket(market, data)
  const linkedCitations = citationsForMarket(market, data, relatedEvents)
  const coverage = buildMarketCoverage(data)
  const scopedCandidates = candidatesForProvision(data.marketDiscoveryCandidates, market.provision)
  const marketScanDetails = marketAbsenceDetails(scopedCandidates, coverage.rejectionCounts)
  const claims: CitedClaim[] = []

  if (market.policy) {
    claims.push({
      id: `${market.id}:pci-score`,
      claimType: "pci_score",
      title: "Policy score",
      claimText: `${market.provision} scores ${scoreText(market.policy.pci ?? market.policy.baseline_pci)} out of 5 across rule clarity, durability, and enforceability.`,
      citations: linkedCitations,
      details: market.policy.delta_this_week ? [`Weekly delta ${scoreText(market.policy.delta_this_week)}`] : [],
    })
  }

  for (const event of relatedEvents) {
    const eventCitations = citationsForTargets(data, [`policy_events:${event.event_id}`])
    claims.push({
      id: `${event.event_id}:policy-event`,
      claimType: "policy_event",
      title: "Policy event",
      claimText: event.rationale || event.title || "Official policy update recorded.",
      citations: eventCitations.length ? eventCitations : [fallbackCitationFromEvent(event)],
      details: [`${event.pci_delta >= 0 ? "+" : ""}${event.pci_delta.toFixed(2)} score`, event.agency ?? event.doc_source ?? "Official source"],
    })
  }

  if (market.forecast) {
    const forecastCitations = citationsForTargets(data, [`forecasts:${market.forecast.forecast_id}`])
    claims.push({
      id: `${market.forecast.forecast_id}:forecast`,
      claimType: "forecast",
      title: "Forecast basis",
      claimText: `Model probability is ${percentText(market.forecast.model_probability)} versus market probability ${percentText(market.forecast.market_probability)}.`,
      citations: forecastCitations.length ? forecastCitations : linkedCitations,
      details: [`Model gap ${pointsText(market.forecast.edge)}`, `Confidence ${percentText(market.forecast.confidence)}`],
    })
  }

  if (market.market) {
    const marketCitations = citationsForTargets(data, [`market_snapshots:${market.market.venue}:${market.market.ticker}`])
    claims.push({
      id: `${market.id}:market-match`,
      claimType: "market_match",
      title: "Public market snapshot",
      claimText: market.market.resolution_text || market.market.title || "Public market snapshot recorded.",
      citations: marketCitations,
      details: [
        market.market.market_probability === null ? "No public probability" : `${percentText(market.market.market_probability)} market`,
        market.market.status ?? "Market status unknown",
      ],
    })
  }

  if (market.kind === "policy" && !market.market && !market.forecast && coverage.scanned > 0) {
    claims.push({
      id: `${market.id}:market-abstention`,
      claimType: "market_rejection",
      title: "Why there is no forecast",
      claimText: `No usable public market matched this policy after checking ${coverage.scanned.toLocaleString("en-US")} public market rows.`,
      citations: [],
      details: marketScanDetails,
    })
  }

  for (const proposal of proposals) {
    claims.push({
      id: `${proposal.proposal_id}:proposal`,
      claimType: "trade_proposal",
      title: "Trade gate",
      claimText: `Proposal is ${proposal.approval_status.replaceAll("_", " ")} with execution disabled in the public app.`,
      citations: market.forecast ? citationsForTargets(data, [`forecasts:${market.forecast.forecast_id}`]) : [],
      details: [`Risk ${proposal.risk_passed ? "passed" : "blocked"}`, `Model gap ${pointsText(proposal.edge)}`],
    })
  }

  const citations = uniqueCitations(claims.flatMap((claim) => claim.citations))
  return {
    claims,
    citations,
    relatedEvents,
    proposals,
    traceSteps: traceStepsForMarket({
      citations,
      coverageScanned: coverage.scanned,
      hasForecast: Boolean(market.forecast),
      hasMarket: Boolean(market.market),
      hasPci: Boolean(market.policy),
      proposals,
      relatedEvents,
    }),
  }
}

function proposalsForMarket(market: PolicyMarket, data: RegistryData): TradeProposal[] {
  return data.tradeProposals
    .filter(
      (proposal) =>
        proposal.forecast_id === market.forecast?.forecast_id ||
        proposal.market_ticker === market.forecast?.market_ticker ||
        proposal.market_ticker === market.market?.ticker,
    )
    .slice(0, 2)
}

function citationsForMarket(
  market: PolicyMarket,
  data: RegistryData,
  relatedEvents: PolicyEvent[],
): ProvenanceCitation[] {
  const targets = new Set<string>()
  if (market.forecast?.forecast_id) targets.add(`forecasts:${market.forecast.forecast_id}`)
  if (market.market?.venue && market.market.ticker) {
    targets.add(`market_snapshots:${market.market.venue}:${market.market.ticker}`)
  }
  for (const event of relatedEvents) targets.add(`policy_events:${event.event_id}`)
  return citationsForTargets(data, [...targets])
}

function citationsForTargets(data: RegistryData, targetKeys: string[]): ProvenanceCitation[] {
  const evidenceIds = new Set<string>()
  const targetSet = new Set(targetKeys)
  for (const link of data.sourceLinks) {
    if (targetSet.has(linkKey(link))) evidenceIds.add(link.evidence_id)
  }
  return uniqueCitations(
    data.evidenceItems
      .filter((item) => evidenceIds.has(item.evidence_id))
      .map(citationFromEvidence),
  )
}

function linkKey(link: SourceLink) {
  return `${link.target_table}:${link.target_id}`
}

function citationFromEvidence(item: EvidenceItem): ProvenanceCitation {
  const metadata = item.raw_public_metadata ?? {}
  const chunkHash = stringMetadata(metadata, "chunk_hash")
  return {
    id: item.evidence_id,
    sourceTitle: item.source_title ?? item.snippet ?? "Public source",
    sourceName: item.source_name ?? item.source ?? "Public source",
    sourceUrl: item.url,
    sourceType: item.source_type,
    agency: item.agency,
    quote: item.snippet,
    evidenceType: item.evidence_type,
    scoreDimension: item.score_dimension,
    normalizedSignal: item.normalized_signal,
    confidence: item.confidence,
    extractorVersion: item.extractor_version,
    createdAt: item.created_at,
    publishedAt: item.published_at,
    fetchedAt: item.fetched_at,
    sourceDocumentId: item.source_doc_id,
    chunkId: stringMetadata(metadata, "chunk_id"),
    chunkHash: chunkHash ? chunkHash.slice(0, 12) : null,
    sectionTitle: stringMetadata(metadata, "section_title"),
    matchedTerms: stringListMetadata(metadata, "matched_terms"),
    retrievalScore: numberMetadata(metadata, "retrieval_score"),
  }
}

function fallbackCitationFromEvent(event: PolicyEvent): ProvenanceCitation {
  return {
    id: `fallback:${event.event_id}`,
    sourceTitle: event.title ?? event.agency ?? "Official policy update",
    sourceName: event.agency ?? event.doc_source ?? "Official source",
    sourceUrl: event.url,
    sourceType: "official_text",
    agency: event.agency,
    quote: event.rationale,
    evidenceType: "policy_event",
    scoreDimension: "pci",
    normalizedSignal: `${event.pci_delta >= 0 ? "+" : ""}${event.pci_delta.toFixed(2)} PCI`,
    confidence: event.confidence,
    extractorVersion: event.prompt_version ?? null,
    createdAt: event.created_at,
    publishedAt: event.week_start,
    fetchedAt: event.created_at,
    sourceDocumentId: event.doc_id ?? null,
    chunkId: null,
    chunkHash: null,
    sectionTitle: null,
    matchedTerms: [],
    retrievalScore: null,
  }
}

function traceStepsForMarket({
  citations,
  coverageScanned,
  hasForecast,
  hasMarket,
  hasPci,
  proposals,
  relatedEvents,
}: {
  citations: ProvenanceCitation[]
  coverageScanned: number
  hasForecast: boolean
  hasMarket: boolean
  hasPci: boolean
  proposals: TradeProposal[]
  relatedEvents: PolicyEvent[]
}): TraceStep[] {
  return [
    {
      id: "source",
      label: "Source checked",
      detail: citations.length ? `${citations.length} public citation${citations.length === 1 ? "" : "s"} attached` : "No cited source attached yet",
      status: citations.length ? "complete" : "pending",
    },
    {
      id: "evidence",
      label: "Evidence found",
      detail: relatedEvents.length ? `${relatedEvents.length} scored policy update${relatedEvents.length === 1 ? "" : "s"}` : "No scored policy update yet",
      status: relatedEvents.length ? "complete" : "pending",
    },
    {
      id: "pci",
      label: "Policy score updated",
      detail: hasPci ? "Policy score dimensions available" : "Policy score pending",
      status: hasPci ? "complete" : "pending",
    },
    {
      id: "market",
      label: "Market search",
      detail: hasMarket ? "Usable public market attached" : coverageScanned ? `${coverageScanned.toLocaleString("en-US")} public market rows checked` : "Public market search pending",
      status: hasMarket ? "complete" : coverageScanned ? "blocked" : "pending",
    },
    {
      id: "forecast",
      label: "Forecast status",
      detail: hasForecast ? "Open forecast published" : "No forecast until a usable market exists",
      status: hasForecast ? "complete" : "blocked",
    },
    {
      id: "proposal",
      label: "Review status",
      detail: proposals.length ? "Human review gate recorded" : "No public execution path",
      status: proposals.length ? "complete" : "pending",
    },
  ]
}

function marketAbsenceDetails(
  scopedCandidates: ReturnType<typeof candidatesForProvision>,
  rejectionCounts: ReturnType<typeof buildMarketCoverage>["rejectionCounts"],
) {
  const rows: string[] = []
  if (scopedCandidates.length) {
    rows.push(`${scopedCandidates.length} rejected candidate${scopedCandidates.length === 1 ? "" : "s"} mention this policy`)
  }
  for (const rejection of rejectionCounts.slice(0, 2)) {
    rows.push(`${rejection.label}: ${rejection.count}`)
  }
  return rows.length ? rows : ["No stored rejection reason yet"]
}

function uniqueCitations(citations: ProvenanceCitation[]) {
  const seen = new Set<string>()
  const rows: ProvenanceCitation[] = []
  for (const citation of citations) {
    if (seen.has(citation.id)) continue
    seen.add(citation.id)
    rows.push(citation)
  }
  return rows
}

function stringMetadata(metadata: Record<string, unknown>, key: string) {
  const value = metadata[key]
  return typeof value === "string" && value.trim() ? value : null
}

function stringListMetadata(metadata: Record<string, unknown>, key: string) {
  const value = metadata[key]
  if (!Array.isArray(value)) return []
  return value.filter((item): item is string => typeof item === "string" && Boolean(item.trim()))
}

function numberMetadata(metadata: Record<string, unknown>, key: string) {
  const value = metadata[key]
  if (typeof value === "number" && Number.isFinite(value)) return value
  if (typeof value === "string") {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

function scoreText(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-"
  return value.toFixed(value % 1 === 0 ? 0 : 2)
}

function percentText(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-"
  return `${Math.round(value * 100)}%`
}

function pointsText(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-"
  const sign = value >= 0 ? "+" : ""
  return `${sign}${Math.round(value * 100)} pts`
}
