"use client"

import {
  Activity,
  AlertCircle,
  CheckCircle2,
  Clock3,
  ExternalLink,
  Search,
  ShieldCheck,
  TrendingDown,
  TrendingUp,
} from "lucide-react"
import { useMemo, useState } from "react"
import type { ReactNode } from "react"
import type {
  CurrentPci,
  Forecast,
  MarketSnapshot,
  PipelineRun,
  PolicyEvent,
  RegistryData,
  ResolvedForecast,
  TradeProposal,
} from "@/lib/data"

type BoardTab = "all" | "forecasts" | "watchlist" | "markets" | "resolved"

function percent(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—"
  return `${Math.round(value * 100)}%`
}

function score(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—"
  return value.toFixed(2)
}

function compactDate(value: string | null | undefined) {
  if (!value) return "—"
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value))
}

function shortDate(value: string | null | undefined) {
  if (!value) return "—"
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
  }).format(new Date(value))
}

function edgeLabel(edge: number | null | undefined) {
  if (edge === null || edge === undefined || Number.isNaN(edge)) return "—"
  const sign = edge >= 0 ? "+" : ""
  return `${sign}${Math.round(edge * 100)} pts`
}

function money(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—"
  return `$${Math.round(value).toLocaleString("en-US")}`
}

function compactOrigin(value: string | null | undefined) {
  if (!value) return "anchor"
  return value === "paper_anchor" ? "anchor" : value.replaceAll("_", " ")
}

function sourceTitle(sourceDoc: Record<string, unknown>) {
  return String(sourceDoc.title ?? sourceDoc.url ?? "Source document")
}

export function RegistryDashboard({ data }: { data: RegistryData }) {
  const [activeProvision, setActiveProvision] = useState("All")
  const [activeTab, setActiveTab] = useState<BoardTab>("all")
  const [query, setQuery] = useState("")

  const latestRun = data.pipelineRuns[0]
  const counts = runCounts(latestRun, data)
  const provisions = useMemo(
    () => ["All", ...data.currentPci.map((row) => row.code).sort()],
    [data.currentPci],
  )

  const openForecasts = useMemo(
    () =>
      data.openForecasts.filter((forecast) =>
        filterForecast(forecast, activeProvision, query),
      ),
    [data.openForecasts, activeProvision, query],
  )
  const provisionWatchlist = useMemo(
    () =>
      data.currentPci.filter((provision) =>
        filterProvision(provision, activeProvision, query),
      ),
    [data.currentPci, activeProvision, query],
  )
  const marketSnapshots = useMemo(
    () =>
      data.marketSnapshots.filter((market) =>
        filterMarket(market, activeProvision, query),
      ),
    [data.marketSnapshots, activeProvision, query],
  )

  return (
    <div className="min-h-screen bg-background">
      <MarketHeader
        connected={data.connected}
        hasViewErrors={data.viewErrors.length > 0}
        latestRun={latestRun}
        query={query}
        setQuery={setQuery}
      />

      <main className="mx-auto grid max-w-[1440px] grid-cols-1 gap-5 px-4 py-4 lg:grid-cols-[220px_minmax(0,1fr)_340px] lg:px-6">
        <LeftRail
          activeProvision={activeProvision}
          setActiveProvision={setActiveProvision}
          provisions={provisions}
          counts={counts}
        />

        <section className="min-w-0">
          <MarketBoardTop latestRun={latestRun} counts={counts} />
          <Tabs
            activeTab={activeTab}
            setActiveTab={setActiveTab}
            forecastCount={data.openForecasts.length}
            marketCount={data.marketSnapshots.length}
            resolvedCount={data.resolvedForecasts.length}
          />

          {(activeTab === "all" || activeTab === "watchlist") && (
            <ProvisionMarketGrid provisions={provisionWatchlist} />
          )}

          {(activeTab === "all" || activeTab === "forecasts") && (
            <ForecastGrid forecasts={openForecasts} />
          )}

          {(activeTab === "all" || activeTab === "markets") && (
            <MarketSnapshotGrid snapshots={marketSnapshots} />
          )}

          {(activeTab === "all" || activeTab === "resolved") && (
            <ResolvedGrid resolved={data.resolvedForecasts} />
          )}
        </section>

        <RightRail
          latestRun={latestRun}
          counts={counts}
          proposals={data.tradeProposals}
          events={data.policyEvents}
          viewErrors={data.viewErrors}
        />
      </main>
    </div>
  )
}

function MarketHeader({
  connected,
  hasViewErrors,
  latestRun,
  query,
  setQuery,
}: {
  connected: boolean
  hasViewErrors: boolean
  latestRun: PipelineRun | undefined
  query: string
  setQuery: (value: string) => void
}) {
  return (
    <header className="sticky top-0 z-40 border-b border-border bg-card/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-[1440px] items-center gap-3 px-4 lg:px-6">
        <div className="flex shrink-0 items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue text-sm font-black text-white">
            PCI
          </div>
          <div className="leading-tight">
            <div className="font-semibold">Policy Markets</div>
            <div className="hidden text-xs text-muted-foreground sm:block">
              Credibility forecasts
            </div>
          </div>
        </div>

        <div className="mx-auto flex h-10 w-full max-w-xl items-center rounded-full border border-border bg-muted px-3">
          <Search className="mr-2 h-4 w-4 shrink-0 text-muted-foreground" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search provisions, markets, tickers"
            className="w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          />
        </div>

        <StatusPill
          connected={connected}
          hasViewErrors={hasViewErrors}
          latestRun={latestRun}
        />
      </div>
    </header>
  )
}

function StatusPill({
  connected,
  hasViewErrors,
  latestRun,
}: {
  connected: boolean
  hasViewErrors: boolean
  latestRun: PipelineRun | undefined
}) {
  if (!connected) {
    return (
      <span className="hidden rounded-full bg-muted px-3 py-1.5 text-xs font-medium text-muted-foreground md:inline-flex">
        Offline
      </span>
    )
  }

  if (hasViewErrors) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-red-soft px-3 py-1.5 text-xs font-semibold text-red">
        <AlertCircle className="h-3.5 w-3.5" />
        View error
      </span>
    )
  }

  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-blue-soft px-3 py-1.5 text-xs font-semibold text-blue">
      <CheckCircle2 className="h-3.5 w-3.5" />
      <span className="hidden sm:inline">
        {latestRun ? "Live backend" : "Connected"}
      </span>
      <span className="sm:hidden">Live</span>
    </span>
  )
}

type RunCounts = {
  policyEvents: number
  eligibleMarkets: number
  forecasts: number
  tradeProposals: number
}

function metadataNumber(metadata: Record<string, unknown>, key: string) {
  const value = metadata[key]
  return typeof value === "number" && Number.isFinite(value) ? value : null
}

function runCounts(latestRun: PipelineRun | undefined, data: RegistryData): RunCounts {
  const metadata = latestRun?.metadata ?? {}
  return {
    policyEvents: metadataNumber(metadata, "policy_events") ?? data.policyEvents.length,
    eligibleMarkets: metadataNumber(metadata, "markets") ?? data.marketSnapshots.length,
    forecasts: metadataNumber(metadata, "forecasts") ?? data.openForecasts.length,
    tradeProposals:
      metadataNumber(metadata, "trade_proposals") ?? data.tradeProposals.length,
  }
}

function LeftRail({
  activeProvision,
  setActiveProvision,
  provisions,
  counts,
}: {
  activeProvision: string
  setActiveProvision: (value: string) => void
  provisions: string[]
  counts: RunCounts
}) {
  return (
    <aside className="space-y-4 lg:sticky lg:top-20 lg:self-start">
      <section className="rounded-xl border border-border bg-card p-3">
        <div className="mb-2 px-1 text-xs font-semibold uppercase text-muted-foreground">
          Markets
        </div>
        <div className="space-y-1">
          {provisions.map((provision) => (
            <button
              key={provision}
              onClick={() => setActiveProvision(provision)}
              className={`flex w-full items-center justify-between rounded-md px-3 py-2 text-sm font-medium transition ${
                activeProvision === provision
                  ? "bg-blue text-white"
                  : "text-foreground hover:bg-muted"
              }`}
            >
              <span>{provision}</span>
              {provision !== "All" && <span className="text-xs opacity-65">PCI</span>}
            </button>
          ))}
        </div>
      </section>

      <section className="rounded-xl border border-border bg-card p-3">
        <div className="mb-2 px-1 text-xs font-semibold uppercase text-muted-foreground">
          Live counts
        </div>
        <div className="grid grid-cols-2 gap-2">
          <MiniStat label="Events" value={counts.policyEvents} />
          <MiniStat label="Markets" value={counts.eligibleMarkets} />
          <MiniStat label="Forecasts" value={counts.forecasts} />
          <MiniStat label="Proposals" value={counts.tradeProposals} />
        </div>
      </section>
    </aside>
  )
}

function MiniStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg bg-muted p-2">
      <div className="text-[10px] font-semibold uppercase text-muted-foreground">
        {label}
      </div>
      <div className="mt-1 text-lg font-bold">{value}</div>
    </div>
  )
}

function MarketBoardTop({
  latestRun,
  counts,
}: {
  latestRun: PipelineRun | undefined
  counts: RunCounts
}) {
  return (
    <section className="mb-4 rounded-xl border border-border bg-card px-4 py-3">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-black tracking-normal">Featured markets</h1>
          <div className="mt-1 text-sm text-muted-foreground">
            PCI-backed IRA odds · official sources only · no synthetic markets
          </div>
        </div>
        <div className="grid grid-cols-3 gap-2">
          <div className="rounded-lg bg-muted px-3 py-2">
            <div className="text-[10px] font-bold uppercase text-muted-foreground">
              Last run
            </div>
            <div className="mt-1 whitespace-nowrap text-sm font-bold">
              {latestRun ? shortDate(latestRun.started_at) : "pending"}
            </div>
          </div>
          <div className="rounded-lg bg-muted px-3 py-2">
            <div className="text-[10px] font-bold uppercase text-muted-foreground">
              Forecasts
            </div>
            <div className="mt-1 text-sm font-bold">{counts.forecasts}</div>
          </div>
          <div className="rounded-lg bg-muted px-3 py-2">
            <div className="text-[10px] font-bold uppercase text-muted-foreground">
              Markets
            </div>
            <div className="mt-1 text-sm font-bold">{counts.eligibleMarkets}</div>
          </div>
        </div>
      </div>
    </section>
  )
}

function Tabs({
  activeTab,
  setActiveTab,
  forecastCount,
  marketCount,
  resolvedCount,
}: {
  activeTab: BoardTab
  setActiveTab: (value: BoardTab) => void
  forecastCount: number
  marketCount: number
  resolvedCount: number
}) {
  const tabs: Array<[BoardTab, string, number | null]> = [
    ["all", "All", null],
    ["forecasts", "Forecasts", forecastCount],
    ["watchlist", "Watchlist", null],
    ["markets", "Market scan", marketCount],
    ["resolved", "Resolved", resolvedCount],
  ]

  return (
    <div className="mb-3 flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
      {tabs.map(([value, label, count]) => (
        <button
          key={value}
          onClick={() => setActiveTab(value)}
          className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
            activeTab === value
              ? "bg-blue text-white"
              : "bg-card text-muted-foreground ring-1 ring-border hover:text-foreground"
          }`}
        >
          {label}
          {count !== null && <span className="ml-1 opacity-70">{count}</span>}
        </button>
      ))}
    </div>
  )
}

function ForecastGrid({ forecasts }: { forecasts: Forecast[] }) {
  if (!forecasts.length) {
    return (
      <MarketSection title="Forecast markets" subtitle="Real commitments only">
        <EmptyMarketCard />
      </MarketSection>
    )
  }

  return (
    <MarketSection title="Forecast markets" subtitle="Timestamped PCI commitments">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {forecasts.map((forecast) => (
          <ForecastCard key={forecast.forecast_id} forecast={forecast} />
        ))}
      </div>
    </MarketSection>
  )
}

function ProvisionMarketGrid({ provisions }: { provisions: CurrentPci[] }) {
  return (
    <MarketSection
      title="All markets"
      subtitle="Six tracked IRA provision contracts"
    >
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {provisions.map((provision) => (
          <ProvisionCard key={provision.code} provision={provision} />
        ))}
      </div>
    </MarketSection>
  )
}

function MarketSnapshotGrid({ snapshots }: { snapshots: MarketSnapshot[] }) {
  if (!snapshots.length) {
    return (
      <MarketSection title="Eligible Kalshi markets" subtitle="Latest scan output">
        <div className="rounded-lg border border-dashed border-border bg-card p-6 text-sm text-muted-foreground">
          No eligible policy markets in the latest scan. Unrelated or ambiguous
          contracts are rejected before publication.
        </div>
      </MarketSection>
    )
  }

  return (
    <MarketSection title="Eligible Kalshi markets" subtitle="Read-only market data">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {snapshots.map((market) => (
          <SnapshotCard key={`${market.venue}:${market.ticker}`} market={market} />
        ))}
      </div>
    </MarketSection>
  )
}

function ResolvedGrid({ resolved }: { resolved: ResolvedForecast[] }) {
  if (!resolved.length) {
    return (
      <MarketSection title="Resolved track record" subtitle="Brier score appears here">
        <div className="rounded-lg border border-dashed border-border bg-card p-6 text-sm text-muted-foreground">
          No resolved forecast commitments yet.
        </div>
      </MarketSection>
    )
  }

  return (
    <MarketSection title="Resolved track record" subtitle="Forecast accuracy">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {resolved.map((row) => (
          <ResolvedCard key={row.forecast_id} row={row} />
        ))}
      </div>
    </MarketSection>
  )
}

function MarketSection({
  title,
  subtitle,
  children,
}: {
  title: string
  subtitle: string
  children: ReactNode
}) {
  return (
    <section className="mb-5">
      <div className="mb-3 flex items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold">{title}</h2>
          <p className="text-sm text-muted-foreground">{subtitle}</p>
        </div>
      </div>
      {children}
    </section>
  )
}

function EmptyMarketCard() {
  return (
    <div className="rounded-xl border border-dashed border-border bg-card p-6">
      <div className="flex items-start gap-3">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-muted">
          <Search className="h-5 w-5 text-muted-foreground" />
        </div>
        <div>
          <h3 className="font-bold">No published forecasts yet</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Waiting for a scored policy event and a clean eligible market.
          </p>
        </div>
      </div>
    </div>
  )
}

function ForecastCard({ forecast }: { forecast: Forecast }) {
  const title =
    forecast.market_title ?? `${forecast.venue.toUpperCase()} ${forecast.market_ticker}`
  const positive = forecast.edge >= 0

  return (
    <article className="market-card">
      <div className="p-4">
        <CardTopline
          left={`${forecast.provision} · ${forecast.venue.toUpperCase()}`}
          right={forecast.market_ticker}
        />
        <h3 className="market-title">{title}</h3>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <OddsButton label="Market" value={percent(forecast.market_probability)} />
          <OddsButton label="PCI model" value={percent(forecast.model_probability)} strong />
        </div>
        <div
          className={`mt-3 inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold ${
            positive ? "bg-green-soft text-green" : "bg-red-soft text-red"
          }`}
        >
          {positive ? <TrendingUp className="h-3.5 w-3.5" /> : <TrendingDown className="h-3.5 w-3.5" />}
          {edgeLabel(forecast.edge)}
        </div>
        <details className="mt-3 rounded-md bg-muted p-3 text-sm">
          <summary className="cursor-pointer font-semibold">Reasoning trace</summary>
          <p className="mt-2 text-muted-foreground">{sourceTitle(forecast.source_doc)}</p>
          {forecast.market_rules && (
            <p className="mt-2 text-muted-foreground">{forecast.market_rules}</p>
          )}
        </details>
      </div>
    </article>
  )
}

function ProvisionCard({ provision }: { provision: CurrentPci }) {
  const stressDelta = (provision.obbba_post_pci ?? provision.baseline_pci) - provision.baseline_pci
  const current = provision.pci ?? provision.baseline_pci

  return (
    <article className="market-card">
      <div className="flex items-center gap-3 border-b border-border bg-muted/50 p-3">
        <div className="flex h-11 w-12 shrink-0 items-center justify-center rounded-lg bg-blue text-xs font-black text-white">
          {provision.code}
        </div>
        <div className="min-w-0">
          <div className="truncate text-xs font-bold uppercase text-muted-foreground">
            {compactOrigin(provision.data_origin)}
          </div>
          <div className="truncate text-sm font-semibold">{provision.name}</div>
        </div>
      </div>
      <div className="p-4">
        <h3 className="market-title">
          Will {provision.code} credibility improve after the next official update?
        </h3>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <OddsButton label="Current PCI" value={score(current)} strong />
          <OddsButton label="OBBBA stress" value={score(provision.obbba_post_pci)} />
        </div>
        <div className="mt-3">
          <DimensionBars provision={provision} />
        </div>
        <div className="mt-3 flex items-center justify-between border-t border-border pt-3">
          <span className="text-xs font-semibold text-muted-foreground">Awaiting market match</span>
          <DeltaBadge value={stressDelta} />
        </div>
      </div>
    </article>
  )
}

function SnapshotCard({ market }: { market: MarketSnapshot }) {
  return (
    <article className="market-card">
      <div className="p-4">
        <CardTopline
          left={`${market.venue.toUpperCase()} · ${market.status ?? "open"}`}
          right={market.ticker}
        />
        <h3 className="market-title">
          {market.title ?? market.subtitle ?? market.event_ticker ?? "Policy market"}
        </h3>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <OddsButton label="Yes" value={percent(market.yes_ask ?? market.market_probability)} strong />
          <OddsButton label="No" value={percent(market.yes_bid ? 1 - market.yes_bid : null)} />
        </div>
        <div className="mt-3 grid grid-cols-3 gap-2 border-t border-border pt-3 text-xs">
          <Metric label="Spread" value={percent(market.bid_ask_spread)} />
          <Metric label="Liquidity" value={money(market.liquidity_dollars)} />
          <Metric label="Close" value={compactDate(market.close_time)} />
        </div>
      </div>
    </article>
  )
}

function ResolvedCard({ row }: { row: ResolvedForecast }) {
  return (
    <article className="market-card">
      <div className="p-4">
        <CardTopline left={`${row.provision} · ${row.result}`} right={row.market_ticker} />
        <h3 className="market-title">{row.market_title ?? row.market_ticker}</h3>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <OddsButton label="PCI forecast" value={percent(row.model_probability)} strong />
          <OddsButton label="Market" value={percent(row.market_probability)} />
        </div>
        <div className="mt-3 border-t border-border pt-3 text-sm text-muted-foreground">
          Brier score <span className="font-bold text-foreground">{row.brier_score.toFixed(3)}</span>
        </div>
      </div>
    </article>
  )
}

function CardTopline({ left, right }: { left: string; right: string | null | undefined }) {
  return (
    <div className="mb-2 flex items-center justify-between gap-2 text-xs font-semibold text-muted-foreground">
      <span className="truncate uppercase">{left}</span>
      {right && <span className="truncate">{right}</span>}
    </div>
  )
}

function OddsButton({
  label,
  value,
  strong = false,
}: {
  label: string
  value: string
  strong?: boolean
}) {
  return (
    <div className={`odds-button ${strong ? "odds-button-strong" : ""}`}>
      <div className="text-[11px] font-bold uppercase">{label}</div>
      <div className="mt-1 text-base font-black">{value}</div>
    </div>
  )
}

function DimensionBars({ provision }: { provision: CurrentPci }) {
  const rows = [
    ["Specificity", provision.specificity],
    ["Durability", provision.durability],
    ["Enforceability", provision.enforceability],
  ] as const

  return (
    <div className="space-y-2">
      {rows.map(([label, value]) => (
        <div key={label}>
          <div className="mb-1 flex justify-between text-xs">
            <span className="text-muted-foreground">{label}</span>
            <span className="font-semibold">{score(value)}</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-foreground"
              style={{
                width: `${Math.max(0, Math.min(100, ((value ?? 0) / 5) * 100))}%`,
              }}
            />
          </div>
        </div>
      ))}
    </div>
  )
}

function RightRail({
  latestRun,
  counts,
  proposals,
  events,
  viewErrors,
}: {
  latestRun: PipelineRun | undefined
  counts: RunCounts
  proposals: TradeProposal[]
  events: PolicyEvent[]
  viewErrors: string[]
}) {
  return (
    <aside className="space-y-4 lg:sticky lg:top-20 lg:self-start">
      <RailCard title="System status" icon={<Activity className="h-4 w-4" />}>
        <div className="space-y-3">
          <StatusRow label="Last run" value={latestRun ? compactDate(latestRun.started_at) : "pending"} />
          <StatusRow label="Policy events" value={String(counts.policyEvents)} />
          <StatusRow label="Forecasts" value={String(counts.forecasts)} />
          <StatusRow label="Trade proposals" value={String(counts.tradeProposals)} />
          {viewErrors.length > 0 && (
            <div className="rounded-md bg-red-soft p-2 text-xs font-semibold text-red">
              {viewErrors.join(", ")}
            </div>
          )}
        </div>
      </RailCard>

      <RailCard title="Gated execution" icon={<ShieldCheck className="h-4 w-4" />}>
        {proposals.length ? (
          <div className="space-y-2">
            {proposals.slice(0, 4).map((proposal) => (
              <div key={proposal.proposal_id} className="rounded-md bg-muted p-2">
                <div className="truncate text-sm font-bold">{proposal.market_ticker}</div>
                <div className="mt-1 flex justify-between text-xs text-muted-foreground">
                  <span>{edgeLabel(proposal.edge)}</span>
                  <span>{proposal.approval_status.replaceAll("_", " ")}</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptySmall>No proposals pending approval.</EmptySmall>
        )}
      </RailCard>

      <RailCard title="Official event feed" icon={<Clock3 className="h-4 w-4" />}>
        {events.length ? (
          <div className="space-y-2">
            {events.slice(0, 5).map((event) => (
              <a
                key={event.event_id}
                href={event.url ?? undefined}
                className="block rounded-md bg-muted p-2 text-sm hover:bg-border/60"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-bold">{event.provision}</span>
                  {event.url && <ExternalLink className="h-3.5 w-3.5" />}
                </div>
                <div className="mt-1 line-clamp-2 text-muted-foreground">
                  {event.title ?? event.agency ?? "Policy event"}
                </div>
              </a>
            ))}
          </div>
        ) : (
          <EmptySmall>No scored official events yet.</EmptySmall>
        )}
      </RailCard>
    </aside>
  )
}

function RailCard({
  title,
  icon,
  children,
}: {
  title: string
  icon: ReactNode
  children: ReactNode
}) {
  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-bold">{title}</h2>
        <span className="text-muted-foreground">{icon}</span>
      </div>
      {children}
    </section>
  )
}

function StatusRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-bold">{value}</span>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-muted-foreground">{label}</div>
      <div className="truncate font-bold">{value}</div>
    </div>
  )
}

function DeltaBadge({ value }: { value: number | null | undefined }) {
  const numeric = value ?? 0
  const positive = numeric > 0
  const neutral = numeric === 0
  return (
    <span
      className={`rounded-full px-2.5 py-1 text-xs font-bold ${
        neutral
          ? "bg-muted text-muted-foreground"
          : positive
            ? "bg-green-soft text-green"
            : "bg-red-soft text-red"
      }`}
    >
      {neutral ? "flat" : `${positive ? "+" : ""}${numeric.toFixed(2)}`}
    </span>
  )
}

function EmptySmall({ children }: { children: ReactNode }) {
  return <div className="rounded-md bg-muted p-3 text-sm text-muted-foreground">{children}</div>
}

function filterForecast(forecast: Forecast, provision: string, query: string) {
  if (provision !== "All" && forecast.provision !== provision) return false
  const normalized = query.trim().toLowerCase()
  if (!normalized) return true
  return [
    forecast.market_title,
    forecast.market_ticker,
    forecast.provision,
    forecast.shock_type,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase()
    .includes(normalized)
}

function filterProvision(provision: CurrentPci, activeProvision: string, query: string) {
  if (activeProvision !== "All" && provision.code !== activeProvision) return false
  const normalized = query.trim().toLowerCase()
  if (!normalized) return true
  return [provision.code, provision.name, provision.primary_channel]
    .filter(Boolean)
    .join(" ")
    .toLowerCase()
    .includes(normalized)
}

function filterMarket(market: MarketSnapshot, provision: string, query: string) {
  const normalized = [query.trim().toLowerCase(), provision === "All" ? "" : provision.toLowerCase()]
    .filter(Boolean)
    .join(" ")
  if (!normalized) return true
  return [market.ticker, market.event_ticker, market.title, market.subtitle, market.resolution_text]
    .filter(Boolean)
    .join(" ")
    .toLowerCase()
    .includes(normalized)
}
