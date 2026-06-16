import Link from "next/link"
import { ActivityList } from "@/components/market/activity-list"
import { formatDateTime, formatScore } from "@/components/market/format"
import { SourceHealthStrip } from "@/components/market/source-health"
import { SiteHeader } from "@/components/layout/site-header"
import { PolicyRegister } from "@/components/policy/register"
import { latestCompletedRun } from "@/lib/market-model"
import { buildPolicyIntelligence } from "@/lib/intelligence"
import { SOURCE_PORTFOLIO } from "@/lib/policy-copy"
import {
  getRegistryData,
} from "@/lib/data"

export const dynamic = "force-dynamic"

export default async function Home() {
  const data = await getRegistryData()
  const policies = buildPolicyIntelligence(data)
  const run = latestCompletedRun(data)
  const averagePci = policies.length
    ? policies.reduce((sum, policy) => sum + Number(policy.currentPci ?? 0), 0) /
      policies.length
    : null
  const lastSourceRefresh =
    latestDate(data.sourceHealth.map((source) => source.last_success_at)) ??
    run?.completed_at ??
    run?.started_at
  const sourceMapCount = data.sourceHealth.length || SOURCE_PORTFOLIO.length
  const evidenceAnchors = policies.reduce((sum, policy) => sum + policy.evidenceAnchorCount, 0)
  const registryState = formatRegistryState(lastSourceRefresh)

  return (
    <main className="tracker-page">
      <SiteHeader />

      <section className="tracker-hero">
        <div className="tracker-hero-copy">
          <p className="eyebrow">Policy Credibility Index</p>
          <h1>Live evidence for climate policy credibility.</h1>
          <p>
            PCIndex parses official policy sources, updates policy-level
            credibility state, and explains the week-to-week trajectory with
            attribution a policy desk can use.
          </p>
          <div className="hero-actions">
            <Link href="/dashboard" className="primary-action">
              Open terminal
            </Link>
            <Link href="/about" className="secondary-action">
              Read about the paper
            </Link>
          </div>
        </div>

        <div className="hero-status">
          <div className="live-chip">
            <span className={data.connected && !data.viewErrors.length ? "live-dot" : "live-dot muted"} />
            {registryState}
          </div>
          <div className="hero-kpis">
            <Kpi label="Avg PCI" value={formatScore(averagePci)} />
            <Kpi label="Tracked policies" value={String(policies.length)} />
            <Kpi label="Source coverage" value={String(sourceMapCount)} />
            <Kpi label="Cited evidence" value={String(evidenceAnchors)} />
            <Kpi label="Score dimensions" value="3" />
          </div>
        </div>
      </section>

      <SourceHealthStrip sources={data.sourceHealth} />

      <section className="tracker-grid-section">
        <div className="section-heading">
          <p>Policy Intelligence</p>
          <h2>Current PCI scores, source freshness, and policy movement.</h2>
        </div>
        <PolicyRegister data={data} />
      </section>

      <section className="tracker-updates-section">
        <ActivityList events={data.policyEvents} outcomes={data.resolvedForecasts} />
      </section>
    </main>
  )
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="kpi-chip">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function latestDate(values: Array<string | null | undefined>) {
  return values.reduce<string | null>((latest, value) => {
    if (!value) return latest
    if (!latest) return value
    return new Date(value).getTime() > new Date(latest).getTime() ? value : latest
  }, null)
}

function formatRegistryState(value: string | null | undefined) {
  return value ? `Latest update ${formatDateTime(value)}` : "Current policy registry"
}
