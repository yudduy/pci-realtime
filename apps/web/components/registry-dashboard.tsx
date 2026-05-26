"use client"

import { Search } from "lucide-react"
import { useMemo, useState } from "react"
import { SiteHeader } from "@/components/layout/site-header"
import { ActivityList } from "@/components/market/activity-list"
import { formatDateTime, formatScore } from "@/components/market/format"
import { MarketCard } from "@/components/market/market-card"
import { MarketDetail } from "@/components/market/market-detail"
import { MarketTable } from "@/components/market/market-table"
import { PolicyTrend } from "@/components/market/policy-trend"
import { SourceHealthStrip } from "@/components/market/source-health"
import {
  buildPolicyMarkets,
  latestCompletedRun,
  type PolicyMarket,
  type PolicyMarketKind,
} from "@/lib/market-model"
import {
  type RegistryData,
} from "@/lib/data"

type BrowseFilter = "all" | PolicyMarketKind

const filterLabels: Record<BrowseFilter, string> = {
  all: "All",
  forecast: "Forecasts",
  policy: "Policy moves",
  market: "Markets",
  resolved: "Resolved",
}

export function RegistryDashboard({ data }: { data: RegistryData }) {
  const [activeFilter, setActiveFilter] = useState<BrowseFilter>("all")
  const [query, setQuery] = useState("")
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const markets = useMemo(() => buildPolicyMarkets(data), [data])
  const visibleMarkets = useMemo(
    () => filterMarkets(markets, activeFilter, query),
    [markets, activeFilter, query],
  )
  const selected =
    visibleMarkets.find((market) => market.id === selectedId) ??
    visibleMarkets[0] ??
    markets[0]
  const run = latestCompletedRun(data)
  const averagePci = data.currentPci.length
    ? data.currentPci.reduce((sum, policy) => sum + Number(policy.pci ?? policy.baseline_pci), 0) /
      data.currentPci.length
    : null

  const filters = buildFilters(markets)

  return (
    <div className="tracker-page tracker-dashboard">
      <SiteHeader />

      <main className="dashboard-shell">
        <section className="dashboard-top">
          <div>
            <p className="eyebrow">Policy Market Tracker</p>
            <h1>IRA credibility markets</h1>
            <p>
              Plain-language policy questions, public Kalshi matches, model
              odds, and review-gated proposal status.
            </p>
          </div>
          <div className="dashboard-status">
            <span className={data.connected && !data.viewErrors.length ? "status-live" : "status-muted"}>
              {data.connected && !data.viewErrors.length ? "Live" : "Preview"}
            </span>
            <span>{formatDateTime(run?.completed_at ?? run?.started_at)}</span>
          </div>
        </section>

        <section className="dashboard-kpis">
          <Kpi label="Avg PCI" value={formatScore(averagePci)} />
          <Kpi label="Policy questions" value={String(data.currentPci.length)} />
          <Kpi label="Matched markets" value={String(data.marketSnapshots.length)} />
          <Kpi label="Candidates" value={String(data.marketDiscoveryCandidates.length)} />
          <Kpi label="Open forecasts" value={String(data.openForecasts.length)} />
        </section>

        <SourceHealthStrip sources={data.sourceHealth} />

        <section className="dashboard-controls">
          <label className="tracker-search">
            <Search className="h-4 w-4" aria-hidden="true" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search policy, market, or ticker"
            />
          </label>
          <div className="filter-row" aria-label="Tracker filters">
            {filters.map((filter) => (
              <button
                type="button"
                key={filter.key}
                onClick={() => setActiveFilter(filter.key)}
                className={activeFilter === filter.key ? "active" : ""}
              >
                {filterLabels[filter.key]}
                <span>{filter.count}</span>
              </button>
            ))}
          </div>
        </section>

        <section className="dashboard-featured">
          {visibleMarkets.slice(0, 3).map((market) => (
            <MarketCard
              key={market.id}
              market={market}
              active={selected?.id === market.id}
              onSelect={setSelectedId}
            />
          ))}
        </section>

        <section className="dashboard-main">
          <div className="dashboard-table-column">
            <div className="section-heading">
              <p>Tracker</p>
              <h2>{visibleMarkets.length} live rows</h2>
            </div>
            <MarketTable
              markets={visibleMarkets}
              selectedId={selected?.id ?? null}
              onSelect={setSelectedId}
            />
          </div>
          <MarketDetail market={selected} data={data} />
        </section>

        <section className="tracker-split">
          <PolicyTrend
            timelines={data.provisionTimelines}
            policies={data.currentPci}
            provision={selected?.provision || undefined}
          />
          <ActivityList events={data.policyEvents} outcomes={data.resolvedForecasts} />
        </section>
      </main>
    </div>
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

function filterMarkets(markets: PolicyMarket[], activeFilter: BrowseFilter, query: string) {
  const normalized = query.trim().toLowerCase()
  return markets.filter((market) => {
    if (activeFilter !== "all" && market.kind !== activeFilter) return false
    if (!normalized) return true
    return market.searchText.toLowerCase().includes(normalized)
  })
}

function buildFilters(markets: PolicyMarket[]) {
  const filters: { key: BrowseFilter; count: number }[] = [
    { key: "all", count: markets.length },
    { key: "forecast", count: markets.filter((market) => market.kind === "forecast").length },
    { key: "policy", count: markets.filter((market) => market.kind === "policy").length },
    { key: "market", count: markets.filter((market) => market.kind === "market").length },
    { key: "resolved", count: markets.filter((market) => market.kind === "resolved").length },
  ]

  return filters.filter((filter) => filter.key === "all" || filter.count > 0)
}
