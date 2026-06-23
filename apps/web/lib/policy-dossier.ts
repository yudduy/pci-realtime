import { getPolicyIntelligence, type PolicyIntelligence } from "@/lib/intelligence"
import type {
  BeliefUpdate,
  EvidenceItem,
  MarketSnapshot,
  PolicyBrief,
  PolicySourceCandidate,
  PolicyThesis,
  RegistryData,
} from "@/lib/data"

export type StaffQuestion = {
  question: string
  answer: string
  citations: Array<{ label: string; href: string | null }>
}

export type PolicyDossier = {
  policy: PolicyIntelligence
  theses: PolicyThesis[]
  beliefUpdates: BeliefUpdate[]
  latestBrief: PolicyBrief | null
  evidence: EvidenceItem[]
  reviewedLeads: PolicySourceCandidate[]
  marketSignals: MarketSnapshot[]
  staffQuestions: StaffQuestion[]
}

type SortableDateRow = {
  created_at?: string | null
  generated_at?: string | null
  discovered_at?: string | null
  published_at?: string | null
  reviewed_at?: string | null
  period_end?: string | null
}

export function buildPolicyDossier(data: RegistryData, code: string): PolicyDossier | null {
  const policy = getPolicyIntelligence(data, code)
  if (!policy) return null

  const theses = data.policyTheses
    .filter((thesis) => thesis.provision === policy.code)
    .sort((a, b) => a.thesis_type.localeCompare(b.thesis_type))
  const beliefUpdates = data.beliefUpdates
    .filter((update) => update.provision === policy.code)
    .sort(compareNewest)
  const latestBrief =
    data.policyBriefs
      .filter((brief) => brief.provision === policy.code)
      .sort(compareNewest)[0] ?? null
  const evidenceSource = data.policyEvidenceItems.length
    ? data.policyEvidenceItems
    : data.evidenceItems
  const evidence = evidenceSource
    .filter((item) => item.provision === policy.code && item.evidence_type !== "market_snapshot")
    .sort(compareNewest)
  const reviewedLeads = data.policySourceCandidates
    .filter((candidate) => candidate.provision === policy.code)
    .sort(compareNewest)
  const marketSignals = data.marketSnapshots
    .filter((market) => marketMatchesPolicy(market, policy.code))
    .sort(compareNewest)

  return {
    policy,
    theses,
    beliefUpdates,
    latestBrief,
    evidence,
    reviewedLeads,
    marketSignals,
    staffQuestions: buildStaffQuestions({
      latestBrief,
      beliefUpdates,
      evidence,
      reviewedLeads,
    }),
  }
}

function buildStaffQuestions({
  latestBrief,
  beliefUpdates,
  evidence,
  reviewedLeads,
}: {
  latestBrief: PolicyBrief | null
  beliefUpdates: BeliefUpdate[]
  evidence: EvidenceItem[]
  reviewedLeads: PolicySourceCandidate[]
}): StaffQuestion[] {
  const latestUpdate = beliefUpdates[0] ?? null
  const latestEvidence = evidence[0] ?? null
  const latestLead = reviewedLeads[0] ?? null
  return [
    {
      question: "Why did this move?",
      answer:
        latestUpdate?.rationale ??
        latestBrief?.what_changed ??
        "No approved belief update is available for this policy in the current window.",
      citations: latestUpdate
        ? [{ label: latestUpdate.update_id, href: null }]
        : latestBrief
          ? [{ label: latestBrief.brief_id, href: null }]
          : [],
    },
    {
      question: "What source proves it?",
      answer:
        latestEvidence?.citation_quote ??
        latestEvidence?.snippet ??
        "No verified policy-evidence citation is available yet.",
      citations: latestEvidence
        ? [
            {
              label: latestEvidence.source_title ?? latestEvidence.evidence_id,
              href: latestEvidence.canonical_url ?? latestEvidence.url,
            },
          ]
        : [],
    },
    {
      question: "What should staff watch next?",
      answer:
        latestBrief?.watch_items[0] ??
        latestLead?.why_it_matters ??
        "Watch for new reviewed primary-source activity before changing staff guidance.",
      citations: latestLead
        ? [
            {
              label: latestLead.title,
              href: latestLead.resolved_primary_url ?? latestLead.canonical_url,
            },
          ]
        : [],
    },
  ]
}

function marketMatchesPolicy(market: MarketSnapshot, code: string): boolean {
  return [
    market.query_name,
    market.title,
    market.subtitle,
    market.ticker,
    market.event_ticker,
  ].some((value) => typeof value === "string" && value.toUpperCase().includes(code))
}

function compareNewest(a: SortableDateRow, b: SortableDateRow): number {
  return dateValue(b) - dateValue(a)
}

function dateValue(row: SortableDateRow): number {
  const value =
    row.created_at ??
    row.generated_at ??
    row.discovered_at ??
    row.reviewed_at ??
    row.published_at ??
    row.period_end
  return value ? new Date(value).getTime() : 0
}
