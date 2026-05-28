import Link from "next/link"
import { formatDateTime, formatScore } from "@/components/market/format"
import { MarketCoveragePanel } from "@/components/market/market-coverage"
import { ProvisionGrid } from "@/components/market/provision-grid"
import { SourceHealthStrip } from "@/components/market/source-health"
import { SiteHeader } from "@/components/layout/site-header"
import { latestCompletedRun } from "@/lib/market-model"
import { buildMarketCoverage } from "@/lib/market-coverage"
import { getRegistryData } from "@/lib/data"

export const dynamic = "force-dynamic"

export default async function Home() {
  const data = await getRegistryData()
  const run = latestCompletedRun(data)
  const averagePci = data.currentPci.length
    ? data.currentPci.reduce((sum, policy) => sum + Number(policy.pci ?? policy.baseline_pci), 0) /
      data.currentPci.length
    : null
  const coverage = buildMarketCoverage(data)

  return (
    <main className="tracker-page">
      <SiteHeader />

      <section className="landing-hero">
        <div className="landing-hero-copy">
          <p className="eyebrow">PCIndex</p>
          <h1>Policy credibility, market-by-market.</h1>
          <p>
            Six IRA climate provisions, scored 1–5 from official sources, matched against public prediction markets.
            Each card opens its own modular page with evidence, market candidates, and methodology.
          </p>
        </div>

        <div className="landing-status">
          <div className="live-chip">
            <span className={data.connected && !data.viewErrors.length ? "live-dot" : "live-dot muted"} />
            {data.connected && !data.viewErrors.length ? "Live data" : "Offline preview"}
          </div>
          <div className="landing-kpis">
            <Kpi label="Avg score" value={formatScore(averagePci)} />
            <Kpi label="Open forecasts" value={String(data.openForecasts.length)} />
            <Kpi label="Eligible markets" value={String(coverage.matched)} />
            <Kpi label="Last update" value={formatDateTime(run?.completed_at ?? run?.started_at)} />
          </div>
        </div>
      </section>

      <SourceHealthStrip sources={data.sourceHealth} />

      <section className="landing-grid-section">
        <header className="landing-section-head">
          <div>
            <p className="eyebrow">Tracked provisions</p>
            <h2>Pick a provision to inspect.</h2>
          </div>
          <Link href="/about" className="landing-secondary-link">
            How scoring works →
          </Link>
        </header>
        <ProvisionGrid data={data} />
      </section>

      <section className="landing-coverage-section">
        <MarketCoveragePanel data={data} />
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
