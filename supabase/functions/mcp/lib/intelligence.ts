// Ported from apps/web/lib/intelligence.ts — keep in sync.
import { POLICIES, policyCopy, type PolicySourceReference } from "./policy-copy.ts"
import type {
  CurrentPci,
  EvidenceItem,
  PolicyEvent,
  RegistryData,
} from "./data.ts"

export type PolicyIntelligence = {
  code: string
  name: string
  formalName: string
  lane: string
  question: string
  policy: CurrentPci | null
  currentPci: number | null
  scoreOrigin: "live" | "baseline_view" | "hardcoded_copy"
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
}

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

function buildPolicy(data: RegistryData, code: string): PolicyIntelligence {
  const copy = policyCopy(code)
  const score = data.currentPci.find((row) => row.code === code) ?? null
  const events = data.policyEvents
    .filter((event) => event.provision === code)
    .sort(compareNewest)
  const evidence = evidenceForEvents(events, data)
  const latestEvidence = newestEvidence(evidence, events)
  const fallbackSource = copy.sourceReferences[0] ?? null
  const currentPci = score?.pci ?? score?.baseline_pci ?? copy.baseline
  const scoreOrigin =
    score?.pci !== null && score?.pci !== undefined
      ? "live"
      : score?.baseline_pci !== null && score?.baseline_pci !== undefined
        ? "baseline_view"
        : "hardcoded_copy"

  return {
    code,
    name: copy.name,
    formalName: copy.formalName,
    lane: copy.lane,
    question: copy.question,
    policy: score,
    currentPci,
    scoreOrigin,
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

function compareNewest(
  a: {
    created_at?: string | null
    published_at?: string | null
    date?: string | null
  },
  b: {
    created_at?: string | null
    published_at?: string | null
    date?: string | null
  },
) {
  return dateValue(b) - dateValue(a)
}

function dateValue(value: {
  created_at?: string | null
  published_at?: string | null
  date?: string | null
}) {
  const date = value.date ?? value.published_at ?? value.created_at
  return date ? new Date(date).getTime() : 0
}
