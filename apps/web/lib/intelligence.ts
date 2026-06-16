import { POLICIES, policyCopy, type PolicySourceReference } from "@/lib/policy-copy"
import type {
  CurrentPci,
  EvidenceItem,
  MarketDiscoveryCandidate,
  MarketSnapshot,
  PipelineRun,
  PolicyEvent,
  RegistryData,
} from "@/lib/data"
import { buildMarketCoverage } from "@/lib/market-coverage"

export type PolicyEvidenceStatus =
  | "market_attached"
  | "documented"
  | "source_review"
  | "source_refresh"
  | "stale"

export type PolicyIntelligence = {
  code: string
  name: string
  formalName: string
  lane: string
  question: string
  policy: CurrentPci | null
  currentPci: number | null
  weeklyDelta: number | null
  specificity: number | null
  durability: number | null
  enforceability: number | null
  updatedAt: string | null
  latestEvidenceAt: string | null
  latestEvidenceTitle: string | null
  latestEvidenceSource: string | null
  evidenceCount: number
  evidenceAnchorCount: number
  eventCount: number
  attributionDrivers: string[]
  sourceReferences: PolicySourceReference[]
  marketSignals: MarketSnapshot[]
  reviewCandidates: MarketDiscoveryCandidate[]
  evidenceStatus: PolicyEvidenceStatus
  latestRefreshAt: string | null
}

const SOURCE_STALE_HOURS = 36

export function buildPolicyIntelligence(data: RegistryData): PolicyIntelligence[] {
  return POLICIES.map((policy) => buildPolicy(data, policy.code))
}

export function getPolicyIntelligence(
  data: RegistryData,
  code: string,
): PolicyIntelligence | null {
  const normalized = code.toUpperCase()
  if (!POLICIES.some((policy) => policy.code === normalized)) return null
  return buildPolicy(data, normalized)
}

export function deriveEvidenceStatus({
  marketSignals,
  reviewCandidates,
  latestRefreshAt,
  scanned,
  now = new Date(),
}: {
  marketSignals: unknown[]
  reviewCandidates: unknown[]
  latestRefreshAt: string | null
  scanned: number
  now?: Date
}): PolicyEvidenceStatus {
  if (!latestRefreshAt && !scanned) return "source_refresh"
  if (latestRefreshAt && hoursBetween(latestRefreshAt, now) > SOURCE_STALE_HOURS) return "stale"
  if (marketSignals.length) return "market_attached"
  if (reviewCandidates.length) return "source_review"
  return scanned ? "documented" : "source_refresh"
}

function buildPolicy(data: RegistryData, code: string): PolicyIntelligence {
  const copy = policyCopy(code)
  const score = data.currentPci.find((row) => row.code === code) ?? null
  const events = data.policyEvents
    .filter((event) => event.provision === code)
    .sort(compareNewest)
  const evidence = evidenceForEvents(events, data)
  const latestEvidence = newestEvidence(evidence, events)
  const fallbackSource = copy.sourceReferences[0] ?? null
  const marketSignals = data.marketSnapshots.filter((snapshot) =>
    policyMatchesSnapshot(snapshot, code),
  )
  const reviewCandidates = data.marketDiscoveryCandidates
    .filter(
      (candidate) =>
        candidate.matched_provisions.includes(code) && !candidate.eligible_snapshot,
    )
    .sort(compareNewest)
  const coverage = buildMarketCoverage(data)
  const sourceHealthLatest = latestDate(
    data.sourceHealth
      .map((source) => source.last_success_at)
      .filter((value): value is string => Boolean(value)),
  )
  const latestRefreshAt = latestRefreshDate(data.pipelineRuns, sourceHealthLatest ?? coverage.latestAt)
  const evidenceStatus = deriveEvidenceStatus({
    marketSignals,
    reviewCandidates,
    latestRefreshAt,
    scanned: coverage.scanned,
  })

  return {
    code,
    name: copy.name,
    formalName: copy.formalName,
    lane: copy.lane,
    question: copy.question,
    policy: score,
    currentPci: score?.pci ?? score?.baseline_pci ?? copy.baseline,
    weeklyDelta: score?.delta_this_week ?? 0,
    specificity: score?.specificity ?? copy.specificity,
    durability: score?.durability ?? copy.durability,
    enforceability: score?.enforceability ?? copy.enforceability,
    updatedAt: score?.updated_at ?? null,
    latestEvidenceAt: latestEvidence?.date ?? null,
    latestEvidenceTitle: latestEvidence?.title ?? fallbackSource?.title ?? null,
    latestEvidenceSource: latestEvidence?.source ?? fallbackSource?.source ?? null,
    evidenceCount: evidence.length,
    evidenceAnchorCount: evidence.length + copy.sourceReferences.length,
    eventCount: events.length,
    attributionDrivers: copy.attributionDrivers,
    sourceReferences: copy.sourceReferences,
    marketSignals,
    reviewCandidates,
    evidenceStatus,
    latestRefreshAt,
  }
}

function evidenceForEvents(events: PolicyEvent[], data: RegistryData) {
  const eventTargetIds = new Set(events.map((event) => `policy_events:${event.event_id}`))
  const evidenceIds = new Set(
    data.sourceLinks
      .filter((link) => eventTargetIds.has(`${link.target_table}:${link.target_id}`))
      .map((link) => link.evidence_id),
  )
  return data.evidenceItems.filter((item) => evidenceIds.has(item.evidence_id))
}

function newestEvidence(evidence: EvidenceItem[], events: PolicyEvent[]) {
  const evidenceRows = evidence
    .map((item) => ({
      date: item.published_at ?? item.created_at,
      title: item.source_title ?? item.snippet ?? "Official source",
      source: item.source_name ?? item.agency ?? "Official source",
    }))
    .sort(compareNewest)
  if (evidenceRows[0]) return evidenceRows[0]

  const eventRows = events
    .map((event) => ({
      date: event.created_at ?? event.week_start,
      title: event.title ?? event.rationale ?? "Official policy update",
      source: event.agency ?? event.doc_source ?? "Official source",
    }))
    .sort(compareNewest)
  return eventRows[0] ?? null
}

function latestRefreshDate(runs: PipelineRun[], sourceHealthLatest: string | null) {
  const marketRuns = runs
    .filter((run) => run.status === "success" && run.run_type === "market_discovery")
    .map((run) => run.completed_at ?? run.started_at)
    .filter((value): value is string => Boolean(value))
  return latestDate(
    [...marketRuns, sourceHealthLatest].filter((value): value is string => Boolean(value)),
  )
}

function latestDate(values: string[]) {
  return values.reduce<string | null>((latest, value) => {
    if (!latest) return value
    return new Date(value).getTime() > new Date(latest).getTime() ? value : latest
  }, null)
}

function policyMatchesSnapshot(snapshot: MarketSnapshot, code: string) {
  const candidates = [
    snapshot.query_name,
    snapshot.title,
    snapshot.subtitle,
    snapshot.ticker,
    snapshot.event_ticker,
  ]
  return candidates.some(
    (value) => typeof value === "string" && value.toUpperCase().includes(code),
  )
}

function compareNewest(
  a: {
    created_at?: string | null
    generated_at?: string | null
    published_at?: string | null
    date?: string | null
  },
  b: {
    created_at?: string | null
    generated_at?: string | null
    published_at?: string | null
    date?: string | null
  },
) {
  return dateValue(b) - dateValue(a)
}

function dateValue(value: {
  created_at?: string | null
  generated_at?: string | null
  published_at?: string | null
  date?: string | null
}) {
  const date = value.date ?? value.published_at ?? value.generated_at ?? value.created_at
  return date ? new Date(date).getTime() : 0
}

function hoursBetween(iso: string, now: Date) {
  const timestamp = new Date(iso).getTime()
  if (Number.isNaN(timestamp)) return 0
  return (now.getTime() - timestamp) / 36e5
}
