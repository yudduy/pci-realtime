import type { Metadata } from "next"
import Link from "next/link"
import { notFound } from "next/navigation"
import { SiteHeader } from "@/components/layout/site-header"
import { EvidenceTimeline } from "@/components/market/evidence-timeline"
import { MarketCoveragePanel } from "@/components/market/market-coverage"
import { MethodologyPanel } from "@/components/market/methodology-panel"
import { PolicyTrend } from "@/components/market/policy-trend"
import { ProvisionHero } from "@/components/market/provision-hero"
import { ProvisionRightRail } from "@/components/market/provision-right-rail"
import { ProvisionTabs } from "@/components/market/provision-tabs"
import { SubMarketList } from "@/components/market/sub-market-list"
import { TraceTimeline } from "@/components/provenance/trace-timeline"
import { POLICIES } from "@/lib/policy-copy"
import { getRegistryData } from "@/lib/data"
import { getProvisionView } from "@/lib/provision-view"

export const dynamic = "force-dynamic"

type Params = { params: Promise<{ code: string }> }

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { code } = await params
  const known = POLICIES.find((policy) => policy.code === code)
  if (!known) return { title: "Provision · PCIndex" }
  return {
    title: `${code} ${known.name} · PCIndex`,
    description: known.question,
  }
}

export default async function ProvisionPage({ params }: Params) {
  const { code } = await params
  const data = await getRegistryData()
  const view = getProvisionView(data, code)
  if (!view) notFound()

  return (
    <main className="provision-page">
      <SiteHeader />

      <ProvisionHero view={view} />

      <div className="provision-shell">
        <div className="provision-main">
          <section className="provision-chart-card">
            <header className="provision-chart-head">
              <div>
                <p>Weekly policy score</p>
                <h2>{view.code} trend</h2>
              </div>
              <Link href="/markets" className="provision-back">
                ← All markets
              </Link>
            </header>
            <PolicyTrend
              timelines={view.timelines.length ? view.timelines : data.provisionTimelines}
              policies={data.currentPci}
              provision={view.code}
            />
          </section>

          <ProvisionTabs
            initialId="evidence"
            tabs={[
              {
                id: "evidence",
                label: "Evidence",
                count: view.events.length,
                content: <EvidenceTimeline events={view.events} provisionCode={view.code} />,
              },
              {
                id: "markets",
                label: "Markets",
                count: view.marketSubrows.length,
                content: (
                  <div className="provision-markets-block">
                    <MarketCoveragePanel data={data} selectedProvision={view.code} compact />
                    <SubMarketList rows={view.marketSubrows} />
                  </div>
                ),
              },
              {
                id: "methodology",
                label: "Methodology",
                content: <MethodologyPanel view={view} />,
              },
              {
                id: "trace",
                label: "Trace",
                content: <TraceTimeline steps={view.provenance.traceSteps} />,
              },
            ]}
          />
        </div>

        <ProvisionRightRail view={view} />
      </div>
    </main>
  )
}
