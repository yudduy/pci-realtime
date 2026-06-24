import { getPolicyIntelligence, type PolicyIntelligence } from "@/lib/intelligence"
import type {
  EvidenceItem,
  PolicySourceCandidate,
  RegistryData,
} from "@/lib/data"

export type StaffQuestion = {
  question: string
  answer: string
  citations: Array<{ label: string; href: string | null }>
}

export type PolicyDossier = {
  policy: PolicyIntelligence
  evidence: EvidenceItem[]
  reviewedLeads: PolicySourceCandidate[]
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

  const evidence = data.policyEvidenceItems
    .filter(
      (item) =>
        item.provision === policy.code &&
        item.evidence_type !== "market_snapshot" &&
        item.quote_verified_against_source === true,
    )
    .sort(compareNewest)
  const reviewedLeads = data.policySourceCandidates
    .filter((candidate) => candidate.provision === policy.code)
    .sort(compareNewest)
  return {
    policy,
    evidence,
    reviewedLeads,
    staffQuestions: buildStaffQuestions({
      evidence,
      reviewedLeads,
    }),
  }
}

function buildStaffQuestions({
  evidence,
  reviewedLeads,
}: {
  evidence: EvidenceItem[]
  reviewedLeads: PolicySourceCandidate[]
}): StaffQuestion[] {
  const latestEvidence = evidence[0] ?? null
  const latestLead = reviewedLeads[0] ?? null
  return [
    {
      question: "Why did this move?",
      answer:
        latestEvidence?.snippet ??
        latestEvidence?.citation_quote ??
        "No verified source-backed move is available for this policy in the current window.",
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
