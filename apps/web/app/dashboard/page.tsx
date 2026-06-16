import { PolicyTerminal } from "@/components/policy/terminal"
import { latestCompletedRun } from "@/lib/market-model"
import { buildPolicyIntelligence } from "@/lib/intelligence"
import { SOURCE_PORTFOLIO } from "@/lib/policy-copy"
import { getRegistryData } from "@/lib/data"

export const dynamic = "force-dynamic"

export default async function DashboardPage() {
  const data = await getRegistryData()
  const policies = buildPolicyIntelligence(data).map((policy) => ({
    code: policy.code,
    name: policy.name,
    formalName: policy.formalName,
    lane: policy.lane,
    question: policy.question,
    currentPci: policy.currentPci,
    weeklyDelta: policy.weeklyDelta,
    specificity: policy.specificity,
    durability: policy.durability,
    enforceability: policy.enforceability,
    updatedAt: policy.updatedAt,
    latestEvidenceAt: policy.latestEvidenceAt,
    latestEvidenceTitle: policy.latestEvidenceTitle,
    latestEvidenceSource: policy.latestEvidenceSource,
    evidenceAnchorCount: policy.evidenceAnchorCount,
    eventCount: policy.eventCount,
    attributionDrivers: policy.attributionDrivers,
    latestRefreshAt: policy.latestRefreshAt,
  }))
  const run = latestCompletedRun(data)
  const lastSourceRefresh =
    latestDate(data.sourceHealth.map((source) => source.last_success_at)) ??
    run?.completed_at ??
    run?.started_at ??
    null
  const evidenceAnchors = policies.reduce((sum, policy) => sum + policy.evidenceAnchorCount, 0)

  return (
    <PolicyTerminal
      data={{
        policies,
        sourceHealth: data.sourceHealth.map((source) => ({
          ...source,
          details: {},
          last_error_summary: null,
        })),
        connected: data.connected,
        viewErrors: data.viewErrors,
        sourceMapCount: data.sourceHealth.length || SOURCE_PORTFOLIO.length,
        evidenceAnchors,
        averagePci: policies.length
          ? policies.reduce((sum, policy) => sum + Number(policy.currentPci ?? 0), 0) /
            policies.length
          : null,
        lastSourceRefresh,
        policyEventCount: data.policyEvents.length,
      }}
    />
  )
}

function latestDate(values: Array<string | null | undefined>) {
  return values.reduce<string | null>((latest, value) => {
    if (!value) return latest
    if (!latest) return value
    return new Date(value).getTime() > new Date(latest).getTime() ? value : latest
  }, null)
}
