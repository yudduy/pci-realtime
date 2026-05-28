import type { Metadata } from "next"
import { SiteHeader } from "@/components/layout/site-header"
import { MarketCoveragePanel } from "@/components/market/market-coverage"
import { ProvisionGrid } from "@/components/market/provision-grid"
import { SourceHealthStrip } from "@/components/market/source-health"
import { getRegistryData } from "@/lib/data"

export const dynamic = "force-dynamic"

export const metadata: Metadata = {
  title: "Markets · PCIndex",
  description: "All tracked IRA provisions and their public market coverage.",
}

export default async function MarketsPage() {
  const data = await getRegistryData()
  return (
    <main className="tracker-page">
      <SiteHeader />
      <section className="markets-index-head">
        <div>
          <p className="eyebrow">All tracked provisions</p>
          <h1>Markets</h1>
          <p className="markets-index-sub">
            Six IRA climate provisions, weekly scoring, and public market coverage. Pick one to inspect.
          </p>
        </div>
      </section>
      <SourceHealthStrip sources={data.sourceHealth} />
      <section className="landing-grid-section">
        <ProvisionGrid data={data} />
      </section>
      <section className="landing-coverage-section">
        <MarketCoveragePanel data={data} />
      </section>
    </main>
  )
}
