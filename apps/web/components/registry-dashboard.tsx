"use client"

import {
  AlertCircle,
  CheckCircle2,
  ExternalLink,
  Search,
  ShieldCheck,
} from "lucide-react"
import { useMemo, useState } from "react"
import type {
  CurrentPci,
  Forecast,
  MarketSnapshot,
  PolicyEvent,
  RegistryData,
  ResolvedForecast,
  TradeProposal,
} from "@/lib/data"
import { policyCopy } from "@/lib/policy-copy"

type BrowseFilter = "all" | "forecasts" | "policies" | "markets" | "resolved"
type FeedKind = "forecast" | "policy" | "market" | "resolved"

type FeedRow = {
  id: string
  kind: FeedKind
  provision: string
  title: string
  subtitle: string
  tag: string
  status: string
  primaryLabel: string
  primaryValue: string
  secondaryLabel: string
  secondaryValue: string
  volume: string
  closes: string
  searchText: string
  forecast?: Forecast
  policy?: CurrentPci
  market?: MarketSnapshot
  resolved?: ResolvedForecast
}

function percent(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-"
  return `${Math.round(value * 100)}%`
}

function score(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-"
  return value.toFixed(value % 1 === 0 ? 0 : 2)
}

function money(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-"
  return `$${Math.round(value).toLocaleString("en-US")}`
}

function compactDate(value: string | null | undefined) {
  if (!value) return "-"
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
  }).format(new Date(value))
}

function edgeText(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "No edge"
  const sign = value >= 0 ? "+" : ""
  return `${sign}${Math.round(value * 100)} pts edge`
}

function sourceTitle(sourceDoc: Record<string, unknown>) {
  return String(sourceDoc.title ?? sourceDoc.url ?? "Official source")
}

function runCount(data: RegistryData, key: string, fallback: number) {
  const value = data.pipelineRuns[0]?.metadata?.[key]
  return typeof value === "number" && Number.isFinite(value) ? value : fallback
}

export function RegistryDashboard({ data }: { data: RegistryData }) {
  const [activeFilter, setActiveFilter] = useState<BrowseFilter>("all")
  const [query, setQuery] = useState("")
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const feed = useMemo(() => buildFeed(data), [data])
  const visibleFeed = useMemo(
    () => filterFeed(feed, activeFilter, query),
    [feed, activeFilter, query],
  )
  const selected = feed.find((row) => row.id === selectedId) ?? visibleFeed[0] ?? feed[0]
  const counts = {
    moves: runCount(data, "policy_events", data.policyEvents.length),
    forecasts: runCount(data, "forecasts", data.openForecasts.length),
    markets: runCount(data, "markets", data.marketSnapshots.length),
    trades: runCount(data, "trade_proposals", data.tradeProposals.length),
  }

  return (
    <div className="min-h-screen bg-[#f7f8fb] text-[#111827]">
      <header className="sticky top-0 z-40 border-b border-[#e6e8ef] bg-white/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-[1440px] items-center gap-4 px-4 lg:px-6">
          <div className="flex min-w-fit items-center gap-2">
            <div className="grid h-9 w-9 place-items-center rounded-md bg-[#1f6feb] text-sm font-black text-white">
              PCI
            </div>
            <div className="leading-tight">
              <div className="font-semibold">Policy Markets</div>
              <div className="hidden text-xs text-[#6b7280] sm:block">Read-only registry</div>
            </div>
          </div>

          <label className="mx-auto flex h-10 w-full max-w-xl items-center rounded-full border border-[#d9dee8] bg-[#f2f4f8] px-3">
            <Search className="mr-2 h-4 w-4 shrink-0 text-[#6b7280]" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search policy, market, or ticker"
              className="w-full bg-transparent text-sm outline-none placeholder:text-[#6b7280]"
            />
          </label>

          <BackendStatus connected={data.connected} errors={data.viewErrors} />
        </div>
      </header>

      <main className="mx-auto grid max-w-[1440px] grid-cols-1 gap-4 px-4 py-4 lg:grid-cols-[184px_minmax(0,1fr)_376px] lg:px-6">
        <aside className="lg:sticky lg:top-20 lg:self-start">
          <div className="mb-2 px-1 text-xs font-semibold uppercase tracking-wide text-[#6b7280]">
            Browse
          </div>
          <div className="space-y-1">
            <BrowseButton label="Top" active={activeFilter === "all"} onClick={() => setActiveFilter("all")} />
            <BrowseButton label="Forecasts" count={data.openForecasts.length} active={activeFilter === "forecasts"} onClick={() => setActiveFilter("forecasts")} />
            <BrowseButton label="Policies" count={data.currentPci.length} active={activeFilter === "policies"} onClick={() => setActiveFilter("policies")} />
            <BrowseButton label="Kalshi" count={data.marketSnapshots.length} active={activeFilter === "markets"} onClick={() => setActiveFilter("markets")} />
            <BrowseButton label="Resolved" count={data.resolvedForecasts.length} active={activeFilter === "resolved"} onClick={() => setActiveFilter("resolved")} />
          </div>

          <div className="mt-6 rounded-lg border border-[#e6e8ef] bg-white p-3 text-sm">
            <div className="mb-3 font-semibold">Pipeline</div>
            <div className="space-y-2 text-[#4b5563]">
              <SideMetric label="Moves" value={counts.moves} />
              <SideMetric label="Markets" value={counts.markets} />
              <SideMetric label="Forecasts" value={counts.forecasts} />
              <SideMetric label="Trade proposals" value={counts.trades} />
            </div>
          </div>
        </aside>

        <section className="min-w-0">
          <div className="mb-3 flex flex-col justify-between gap-2 sm:flex-row sm:items-end">
            <div>
              <h1 className="text-2xl font-bold tracking-normal">Featured policy markets</h1>
              <p className="mt-1 text-sm text-[#6b7280]">
                Plain-language IRA provisions, public market matches, and model odds.
              </p>
            </div>
            <div className="text-sm text-[#6b7280]">
              {visibleFeed.length} markets
            </div>
          </div>

          <div className="overflow-hidden rounded-xl border border-[#e1e5ee] bg-white">
            {visibleFeed.length ? (
              <div className="divide-y divide-[#eef1f6]">
                {visibleFeed.map((row) => (
                  <button
                    key={row.id}
                    onClick={() => setSelectedId(row.id)}
                    className={`grid w-full grid-cols-1 gap-3 px-4 py-4 text-left transition hover:bg-[#f8fafc] md:grid-cols-[minmax(0,1fr)_280px] ${
                      selected?.id === row.id ? "bg-[#f4f8ff]" : "bg-white"
                    }`}
                  >
                    <MarketRowText row={row} />
                    <MarketRowPrices row={row} />
                  </button>
                ))}
              </div>
            ) : (
              <div className="p-8 text-sm text-[#6b7280]">
                No matching markets. Clear the search or change the browse filter.
              </div>
            )}
          </div>
        </section>

        <aside className="lg:sticky lg:top-20 lg:self-start">
          <MarketDetails
            row={selected}
            proposals={data.tradeProposals}
            events={data.policyEvents}
          />
        </aside>
      </main>
    </div>
  )
}

function buildFeed(data: RegistryData): FeedRow[] {
  const forecasts = data.openForecasts.map((forecast): FeedRow => {
    const copy = policyCopy(forecast.provision, forecast.provision_name)
    const title =
      forecast.market_title ?? `${forecast.venue.toUpperCase()} ${forecast.market_ticker}`

    return {
      id: `forecast:${forecast.forecast_id}`,
      kind: "forecast",
      provision: forecast.provision,
      title,
      subtitle: `${copy.name} · ${forecast.market_ticker}`,
      tag: "Forecast",
      status: edgeText(forecast.edge),
      primaryLabel: "Market",
      primaryValue: percent(forecast.market_probability),
      secondaryLabel: "Model",
      secondaryValue: percent(forecast.model_probability),
      volume: "Forecast",
      closes: compactDate(forecast.market_close_time),
      searchText: [title, copy.name, forecast.market_ticker, forecast.provision].join(" "),
      forecast,
    }
  })

  const policies = data.currentPci.map((policy): FeedRow => {
    const copy = policyCopy(policy.code, policy.name)
    return {
      id: `policy:${policy.code}`,
      kind: "policy",
      provision: policy.code,
      title: copy.question,
      subtitle: `${copy.name} · ${copy.formalName}`,
      tag: copy.lane,
      status: "No clean market yet",
      primaryLabel: "PCI",
      primaryValue: score(policy.pci ?? policy.baseline_pci),
      secondaryLabel: "Stress",
      secondaryValue: score(policy.obbba_post_pci),
      volume: "Paper anchor",
      closes: compactDate(policy.updated_at),
      searchText: [policy.code, policy.name, copy.name, copy.formalName, copy.lane].join(" "),
      policy,
    }
  })

  const markets = data.marketSnapshots.map((market): FeedRow => {
    const title = market.title ?? market.subtitle ?? market.event_ticker ?? market.ticker
    return {
      id: `market:${market.venue}:${market.ticker}`,
      kind: "market",
      provision: market.query_name ?? "",
      title,
      subtitle: `${market.venue.toUpperCase()} · ${market.ticker}`,
      tag: market.status ?? "Market",
      status: market.policy_relevant ? "Policy relevant" : "Watch only",
      primaryLabel: "Yes",
      primaryValue: percent(market.yes_ask ?? market.market_probability),
      secondaryLabel: "No",
      secondaryValue: percent(market.yes_bid ? 1 - market.yes_bid : null),
      volume: market.volume ? `${money(market.volume)} Vol` : money(market.liquidity_dollars),
      closes: compactDate(market.close_time),
      searchText: [title, market.ticker, market.event_ticker, market.query_name].join(" "),
      market,
    }
  })

  const resolved = data.resolvedForecasts.map((row): FeedRow => {
    const copy = policyCopy(row.provision, row.provision_name)
    return {
      id: `resolved:${row.forecast_id}`,
      kind: "resolved",
      provision: row.provision,
      title: row.market_title ?? row.market_ticker,
      subtitle: `${copy.name} · ${row.market_ticker}`,
      tag: "Resolved",
      status: row.result,
      primaryLabel: "Model",
      primaryValue: percent(row.model_probability),
      secondaryLabel: "Market",
      secondaryValue: percent(row.market_probability),
      volume: `Brier ${row.brier_score.toFixed(3)}`,
      closes: compactDate(row.resolved_at),
      searchText: [row.market_title, row.market_ticker, copy.name, row.result].join(" "),
      resolved: row,
    }
  })

  return [...forecasts, ...markets, ...policies, ...resolved]
}

function filterFeed(feed: FeedRow[], activeFilter: BrowseFilter, query: string) {
  const normalized = query.trim().toLowerCase()
  return feed.filter((row) => {
    if (activeFilter === "forecasts" && row.kind !== "forecast") return false
    if (activeFilter === "policies" && row.kind !== "policy") return false
    if (activeFilter === "markets" && row.kind !== "market") return false
    if (activeFilter === "resolved" && row.kind !== "resolved") return false
    if (!normalized) return true
    return row.searchText.toLowerCase().includes(normalized)
  })
}

function BackendStatus({
  connected,
  errors,
}: {
  connected: boolean
  errors: string[]
}) {
  if (!connected) {
    return (
      <span className="hidden rounded-full bg-[#f2f4f8] px-3 py-1.5 text-xs font-medium text-[#6b7280] md:inline-flex">
        Offline
      </span>
    )
  }

  if (errors.length) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-[#fff1f2] px-3 py-1.5 text-xs font-semibold text-[#dc2626]">
        <AlertCircle className="h-3.5 w-3.5" />
        View error
      </span>
    )
  }

  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-[#eef6ff] px-3 py-1.5 text-xs font-semibold text-[#1f6feb]">
      <CheckCircle2 className="h-3.5 w-3.5" />
      Live
    </span>
  )
}

function BrowseButton({
  label,
  count,
  active,
  onClick,
}: {
  label: string
  count?: number
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={`flex w-full items-center justify-between rounded-md px-3 py-2 text-sm font-medium transition ${
        active ? "bg-[#111827] text-white" : "text-[#374151] hover:bg-white"
      }`}
    >
      <span>{label}</span>
      {count !== undefined && <span className="text-xs opacity-70">{count}</span>}
    </button>
  )
}

function SideMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center justify-between">
      <span>{label}</span>
      <span className="font-semibold text-[#111827]">{value}</span>
    </div>
  )
}

function MarketRowText({ row }: { row: FeedRow }) {
  return (
    <div className="flex min-w-0 gap-3">
      <div className="grid h-12 w-12 shrink-0 place-items-center rounded-md bg-[#eef2ff] text-xs font-black text-[#1f6feb]">
        {row.provision || row.kind.toUpperCase().slice(0, 2)}
      </div>
      <div className="min-w-0">
        <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-[#6b7280]">
          <span className="rounded-full bg-[#f2f4f8] px-2 py-0.5 font-medium text-[#374151]">
            {row.tag}
          </span>
          <span>{row.subtitle}</span>
        </div>
        <div className="line-clamp-2 text-base font-semibold leading-snug text-[#111827]">
          {row.title}
        </div>
        <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-[#6b7280]">
          <span>{row.volume}</span>
          <span>{row.closes}</span>
          <span>{row.status}</span>
        </div>
      </div>
    </div>
  )
}

function MarketRowPrices({ row }: { row: FeedRow }) {
  return (
    <div className="grid grid-cols-2 gap-2 self-center">
      <ReadOnlyPrice label={row.primaryLabel} value={row.primaryValue} blue />
      <ReadOnlyPrice label={row.secondaryLabel} value={row.secondaryValue} />
    </div>
  )
}

function ReadOnlyPrice({
  label,
  value,
  blue = false,
}: {
  label: string
  value: string
  blue?: boolean
}) {
  return (
    <div
      className={`rounded-md px-3 py-2 text-center ${
        blue ? "bg-[#eef6ff] text-[#1f6feb]" : "bg-[#f2f4f8] text-[#374151]"
      }`}
    >
      <div className="text-[11px] font-semibold uppercase">{label}</div>
      <div className="mt-0.5 text-lg font-black">{value}</div>
    </div>
  )
}

function MarketDetails({
  row,
  proposals,
  events,
}: {
  row: FeedRow | undefined
  proposals: TradeProposal[]
  events: PolicyEvent[]
}) {
  if (!row) {
    return (
      <div className="rounded-xl border border-[#e1e5ee] bg-white p-4 text-sm text-[#6b7280]">
        Waiting for registry data.
      </div>
    )
  }

  const relatedEvents = events
    .filter((event) => event.provision === row.provision)
    .slice(0, 3)
  const relatedProposals = proposals
    .filter(
      (proposal) =>
        proposal.market_ticker === row.forecast?.market_ticker ||
        proposal.market_ticker === row.market?.ticker ||
        proposal.forecast_id === row.forecast?.forecast_id,
    )
    .slice(0, 3)

  return (
    <div className="rounded-xl border border-[#e1e5ee] bg-white">
      <div className="border-b border-[#eef1f6] p-4">
        <div className="mb-2 flex items-center justify-between gap-2">
          <span className="rounded-full bg-[#f2f4f8] px-2.5 py-1 text-xs font-semibold text-[#374151]">
            {row.tag}
          </span>
          <span className="text-xs font-medium text-[#6b7280]">Read-only</span>
        </div>
        <h2 className="text-xl font-bold leading-tight">{row.title}</h2>
        <p className="mt-2 text-sm text-[#6b7280]">{row.subtitle}</p>
        <div className="mt-4 grid grid-cols-2 gap-2">
          <ReadOnlyPrice label={row.primaryLabel} value={row.primaryValue} blue />
          <ReadOnlyPrice label={row.secondaryLabel} value={row.secondaryValue} />
        </div>
      </div>

      <div className="space-y-5 p-4">
        <PolicyExplanation row={row} />

        <section>
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
            <ShieldCheck className="h-4 w-4 text-[#1f6feb]" />
            Trade gate
          </div>
          {relatedProposals.length ? (
            <div className="space-y-2">
              {relatedProposals.map((proposal) => (
                <div key={proposal.proposal_id} className="rounded-md bg-[#f7f8fb] p-3 text-sm">
                  <div className="font-semibold">{proposal.market_ticker}</div>
                  <div className="mt-1 text-[#6b7280]">
                    {edgeText(proposal.edge)} · {proposal.approval_status.replaceAll("_", " ")}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="rounded-md bg-[#f7f8fb] p-3 text-sm text-[#6b7280]">
              No backend trade proposal for this market.
            </p>
          )}
        </section>

        <section>
          <div className="mb-2 text-sm font-semibold">Latest policy moves</div>
          {relatedEvents.length ? (
            <div className="space-y-2">
              {relatedEvents.map((event) => (
                <a
                  key={event.event_id}
                  href={event.url ?? undefined}
                  className="block rounded-md bg-[#f7f8fb] p-3 text-sm hover:bg-[#eef1f6]"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="line-clamp-2 font-medium">
                      {event.title ?? event.agency ?? "Policy event"}
                    </span>
                    {event.url && <ExternalLink className="h-3.5 w-3.5 shrink-0" />}
                  </div>
                  <div className="mt-1 text-xs text-[#6b7280]">
                    {compactDate(event.created_at)} · {event.agency ?? row.provision}
                  </div>
                </a>
              ))}
            </div>
          ) : (
            <p className="rounded-md bg-[#f7f8fb] p-3 text-sm text-[#6b7280]">
              No policy move attached yet.
            </p>
          )}
        </section>
      </div>
    </div>
  )
}

function PolicyExplanation({ row }: { row: FeedRow }) {
  if (row.forecast) {
    return (
      <section className="text-sm">
        <div className="mb-2 font-semibold">Forecast basis</div>
        <p className="text-[#4b5563]">{sourceTitle(row.forecast.source_doc)}</p>
        {row.forecast.market_rules && (
          <p className="mt-2 text-[#6b7280]">{row.forecast.market_rules}</p>
        )}
      </section>
    )
  }

  if (row.market) {
    return (
      <section className="text-sm">
        <div className="mb-2 font-semibold">Market data</div>
        <div className="grid grid-cols-3 gap-2">
          <SmallDatum label="Spread" value={percent(row.market.bid_ask_spread)} />
          <SmallDatum label="Liquidity" value={money(row.market.liquidity_dollars)} />
          <SmallDatum label="Close" value={compactDate(row.market.close_time)} />
        </div>
        {row.market.resolution_text && (
          <p className="mt-3 text-[#6b7280]">{row.market.resolution_text}</p>
        )}
      </section>
    )
  }

  if (row.resolved) {
    return (
      <section className="text-sm">
        <div className="mb-2 font-semibold">Outcome</div>
        <div className="grid grid-cols-3 gap-2">
          <SmallDatum label="Result" value={row.resolved.result} />
          <SmallDatum label="Settled" value={score(row.resolved.settlement_value)} />
          <SmallDatum label="Brier" value={row.resolved.brier_score.toFixed(3)} />
        </div>
      </section>
    )
  }

  const policy = row.policy
  if (!policy) return null

  return (
    <section className="text-sm">
      <div className="mb-2 font-semibold">PCI breakdown</div>
      <div className="space-y-2">
        <BreakdownLine label="Specific" value={policy.specificity} />
        <BreakdownLine label="Durable" value={policy.durability} />
        <BreakdownLine label="Enforced" value={policy.enforceability} />
      </div>
      <p className="mt-3 text-[#6b7280]">{policy.obbba_summary}</p>
    </section>
  )
}

function BreakdownLine({
  label,
  value,
}: {
  label: string
  value: number | null | undefined
}) {
  const width = `${Math.max(0, Math.min(100, ((value ?? 0) / 5) * 100))}%`
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs">
        <span className="text-[#6b7280]">{label}</span>
        <span className="font-semibold">{score(value)}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-[#eef1f6]">
        <div className="h-full rounded-full bg-[#111827]" style={{ width }} />
      </div>
    </div>
  )
}

function SmallDatum({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-[#f7f8fb] p-2">
      <div className="text-[11px] font-semibold uppercase text-[#6b7280]">{label}</div>
      <div className="mt-1 truncate font-semibold">{value}</div>
    </div>
  )
}
