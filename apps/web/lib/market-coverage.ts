import type { MarketDiscoveryCandidate, RegistryData, SourceHealth } from "@/lib/data"

const MARKET_SOURCES = new Set(["kalshi", "polymarket"])

const REJECTION_LABELS: Record<string, string> = {
  market_not_open: "Closed or inactive",
  no_policy_context: "No IRA/policy context",
  no_tracked_provision_overlap: "No tracked IRA provision",
  unclear_or_missing_resolution: "Unclear resolution",
}

export type MarketVenueCoverage = {
  source: string
  name: string
  scanned: number
  published: number
  storedCandidates: number
  rateLimited: number
  lastSuccessAt: string | null
}

export type MarketCoverageSummary = {
  scanned: number
  matched: number
  candidates: number
  assessed: number
  adjacent: number
  latestAt: string | null
  venues: MarketVenueCoverage[]
  rejectionCounts: { reason: string; label: string; count: number }[]
}

export function buildMarketCoverage(data: RegistryData): MarketCoverageSummary {
  const venues = data.sourceHealth
    .filter((source) => MARKET_SOURCES.has(source.source))
    .map((source) => venueCoverage(source))

  const rejectionMap = new Map<string, number>()
  for (const candidate of data.marketDiscoveryCandidates) {
    for (const reason of candidate.rejection_reasons) {
      rejectionMap.set(reason, (rejectionMap.get(reason) ?? 0) + 1)
    }
  }

  const candidateLatest = latestDate(
    data.marketDiscoveryCandidates.map((candidate) => candidate.generated_at),
  )
  const venueLatest = latestDate(
    venues.map((venue) => venue.lastSuccessAt).filter((value): value is string => Boolean(value)),
  )

  return {
    scanned: sum(venues.map((venue) => venue.scanned)),
    matched: data.marketSnapshots.length,
    candidates: data.marketDiscoveryCandidates.length,
    assessed: data.marketIntelligence.length,
    adjacent: data.marketIntelligence.filter((row) => !row.eligible_for_forecast).length,
    latestAt: latestDate([candidateLatest, venueLatest].filter((value): value is string => Boolean(value))),
    venues,
    rejectionCounts: [...rejectionMap.entries()]
      .map(([reason, count]) => ({
        reason,
        label: rejectionLabel(reason),
        count,
      }))
      .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label)),
  }
}

export function candidatesForProvision(
  candidates: MarketDiscoveryCandidate[],
  provision: string | null | undefined,
) {
  if (!provision) return candidates
  return candidates.filter((candidate) => candidate.matched_provisions.includes(provision))
}

export function rejectionLabel(reason: string) {
  return REJECTION_LABELS[reason] ?? reason.replaceAll("_", " ")
}

function venueCoverage(source: SourceHealth): MarketVenueCoverage {
  return {
    source: source.source,
    name: source.source_name,
    scanned: detailNumber(source.details, "scanned") ?? source.row_count ?? 0,
    published: detailNumber(source.details, "published") ?? 0,
    storedCandidates: detailNumber(source.details, "stored_candidates") ?? 0,
    rateLimited: detailNumber(source.details, "rate_limited") ?? 0,
    lastSuccessAt: source.last_success_at,
  }
}

function detailNumber(details: Record<string, unknown>, key: string) {
  const value = details[key]
  if (typeof value === "number" && Number.isFinite(value)) return value
  if (typeof value === "string") {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) return parsed
  }
  return null
}

function sum(values: number[]) {
  return values.reduce((total, value) => total + value, 0)
}

function latestDate(values: string[]) {
  let latest: string | null = null
  for (const value of values) {
    if (!latest || new Date(value).getTime() > new Date(latest).getTime()) {
      latest = value
    }
  }
  return latest
}
