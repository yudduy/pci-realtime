import Link from "next/link"
import { ActivityList } from "@/components/market/activity-list"
import { formatDateTime, formatScore } from "@/components/market/format"
import { MarketCard } from "@/components/market/market-card"
import { MarketCoveragePanel } from "@/components/market/market-coverage"
import { PolicyTrend } from "@/components/market/policy-trend"
import { SourceHealthStrip } from "@/components/market/source-health"
import { SiteHeader } from "@/components/layout/site-header"
import { buildPolicyMarkets, latestCompletedRun } from "@/lib/market-model"
import { buildMarketCoverage } from "@/lib/market-coverage"
import {
  getRegistryData,
} from "@/lib/data"

export const dynamic = "force-dynamic"

export default async function Home() {
  const data = await getRegistryData()
  const markets = buildPolicyMarkets(data)
  const featured = markets.slice(0, 6)
  const run = latestCompletedRun(data)
  const averagePci = data.currentPci.length
    ? data.currentPci.reduce((sum, policy) => sum + Number(policy.pci ?? policy.baseline_pci), 0) /
      data.currentPci.length
    : null
  const coverage = buildMarketCoverage(data)

  return (
    <main className="tracker-page">
      <SiteHeader />

      <section className="tracker-hero">
        <div className="tracker-hero-copy">
          <p className="eyebrow">Policy Credibility Index</p>
          <h1>Live odds for climate policy credibility.</h1>
          <p>
            PCIndex tracks official IRA policy updates, maps them to public
            prediction markets, and shows the forecast layer that refreshes as
            new source checks run.
          </p>
          <div className="hero-actions">
            <Link href="/dashboard" className="primary-action">
              Open tracker
            </Link>
            <Link href="/about" className="secondary-action">
              Read about the paper
            </Link>
          </div>
        </div>

        <div className="hero-status">
          <div className="live-chip">
            <span className={data.connected && !data.viewErrors.length ? "live-dot" : "live-dot muted"} />
            {data.connected && !data.viewErrors.length ? "Live policy data" : "Offline preview"}
          </div>
          <div className="hero-kpis">
            <Kpi label="Avg PCI" value={formatScore(averagePci)} />
            <Kpi label="Open forecasts" value={String(data.openForecasts.length)} />
            <Kpi label="Eligible matches" value={String(coverage.matched)} />
            <Kpi label="Near-misses" value={String(coverage.candidates)} />
            <Kpi label="Last update" value={formatDateTime(run?.completed_at ?? run?.started_at)} />
          </div>
        </div>
      </section>

      <SourceHealthStrip sources={data.sourceHealth} />
      <MarketCoveragePanel data={data} compact />

      <section className="tracker-grid-section">
        <div className="section-heading">
          <p>Featured Policy Markets</p>
          <h2>What changed, what can be forecast, and what is waiting.</h2>
        </div>
        <div className="market-card-grid">
          {featured.map((market) => (
            <MarketCard key={market.id} market={market} />
          ))}
        </div>
      </section>

      <section className="tracker-split">
        <PolicyTrend timelines={data.provisionTimelines} policies={data.currentPci} />
        <ActivityList events={data.policyEvents} outcomes={data.resolvedForecasts} />
      </section>

      <section className="performance-strip">
        <div>
          <p>Track Record</p>
          <h2>Forecast performance appears as markets resolve.</h2>
        </div>
        <div className="performance-metrics">
          <Kpi label="Forecasts" value={String(data.forecastPerformance?.forecast_count ?? data.openForecasts.length)} />
          <Kpi label="Resolved" value={String(data.forecastPerformance?.resolved_count ?? data.resolvedForecasts.length)} />
          <Kpi label="Model Brier" value={formatScore(data.forecastPerformance?.model_brier_score)} />
        </div>
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
