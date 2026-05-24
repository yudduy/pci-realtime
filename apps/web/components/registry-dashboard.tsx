"use client"

import {
  Activity,
  AlertCircle,
  CheckCircle2,
  ExternalLink,
  Filter,
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

function edgeLabel(edge: number) {
  const sign = edge >= 0 ? "+" : ""
  return `${sign}${Math.round(edge * 100)} pts`
}

function money(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—"
  return `$${Math.round(value).toLocaleString("en-US")}`
}

function sourceTitle(sourceDoc: Record<string, unknown>) {
  return String(sourceDoc.title ?? sourceDoc.url ?? "Source document")
}

function originLabel(value: string | null | undefined) {
  if (!value) return "provision anchor"
  return value.replaceAll("_", " ")
}

function compactOrigin(value: string | null | undefined) {
  return value === "paper_anchor" ? "anchor" : originLabel(value)
}

export function RegistryDashboard({ data }: { data: RegistryData }) {
  const [activeProvision, setActiveProvision] = useState("All")
  const [query, setQuery] = useState("")
  const hasViewErrors = data.viewErrors.length > 0
  const provisionFilters = useMemo(() => {
    const codes = new Set<string>()
    for (const row of data.currentPci) codes.add(row.code)
    for (const row of data.openForecasts) codes.add(row.provision)
    return ["All", ...Array.from(codes).sort()]
  }, [data.currentPci, data.openForecasts])

  const filteredForecasts = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    return data.openForecasts.filter((forecast) => {
      const provisionMatch =
        activeProvision === "All" || forecast.provision === activeProvision
      const queryMatch =
        !normalized ||
        [
          forecast.market_title,
          forecast.market_ticker,
          forecast.provision,
          forecast.shock_type,
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase()
          .includes(normalized)
      return provisionMatch && queryMatch
    })
  }, [activeProvision, query, data.openForecasts])

  const latestRun = data.pipelineRuns[0]
  const counts = runCounts(latestRun, data)

  return (
    <div className="min-h-screen bg-background">
      <Header
        connected={data.connected}
        hasViewErrors={hasViewErrors}
        latestRun={latestRun}
      />

      <main className="mx-auto max-w-7xl px-4 py-5 lg:px-6">
        <ProductStatement
          latestRun={latestRun}
          viewErrors={data.viewErrors}
          counts={counts}
        />
        <ProvisionStrip provisions={data.currentPci} />

        <div className="mt-5 grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
          <section>
            <div className="mb-3 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <h1 className="text-xl font-semibold tracking-normal">
                  Forecast commitments
                </h1>
                <p className="text-sm text-muted-foreground">
                  Timestamped PCI forecasts matched to eligible Kalshi markets.
                </p>
              </div>

              {data.openForecasts.length > 0 && (
                <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-hide">
                  <Filter className="h-4 w-4 shrink-0 text-muted-foreground" />
                  {provisionFilters.map((filter) => (
                    <button
                      key={filter}
                      onClick={() => setActiveProvision(filter)}
                      className={`rounded-full px-3 py-1.5 text-sm transition ${
                        activeProvision === filter
                          ? "bg-foreground text-white"
                          : "bg-card text-muted-foreground ring-1 ring-border hover:text-foreground"
                      }`}
                    >
                      {filter}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {data.openForecasts.length > 0 && (
              <div className="mb-3 flex items-center rounded-lg bg-card px-3 py-2 ring-1 ring-border">
                <Search className="mr-2 h-4 w-4 text-muted-foreground" />
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search ticker, provision, or market"
                  className="w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
                />
              </div>
            )}

            {data.openForecasts.length === 0 ? (
              <EmptyForecastState
                hasBackend={data.connected}
                hasViewErrors={hasViewErrors}
              />
            ) : filteredForecasts.length ? (
              <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                {filteredForecasts.map((forecast) => (
                  <ForecastCard key={forecast.forecast_id} forecast={forecast} />
                ))}
              </div>
            ) : (
              <FilteredEmptyState activeProvision={activeProvision} query={query} />
            )}
          </section>

          <aside className="space-y-4">
            <ProposalPanel proposals={data.tradeProposals} />
            <MarketScanPanel snapshots={data.marketSnapshots} />
            <EventFeed events={data.policyEvents} />
          </aside>
        </div>

        <ResolvedSection resolved={data.resolvedForecasts} />
      </main>
    </div>
  )
}

function Header({
  connected,
  hasViewErrors,
  latestRun,
}: {
  connected: boolean
  hasViewErrors: boolean
  latestRun: PipelineRun | undefined
}) {
  return (
    <header className="sticky top-0 z-40 border-b border-border bg-card/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-4 px-4 lg:px-6">
        <div className="flex shrink-0 items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-foreground text-sm font-bold text-white">
            PCI
          </div>
          <div>
            <div className="text-sm font-semibold leading-4">PCI Forecast Registry</div>
            <div className="text-xs text-muted-foreground">Kalshi-linked commitments</div>
          </div>
        </div>

        <div className="ml-auto flex items-center gap-2">
          <StatusPill
            connected={connected}
            hasViewErrors={hasViewErrors}
            latestRun={latestRun}
          />
        </div>
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
      <span className="rounded-full bg-muted px-3 py-1.5 text-xs font-medium text-muted-foreground">
        Paper anchors only
      </span>
    )
  }

  if (hasViewErrors) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-red-soft px-3 py-1.5 text-xs font-medium text-red">
        <AlertCircle className="h-3.5 w-3.5" />
        Backend view error
      </span>
    )
  }

  if (!latestRun) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-muted px-3 py-1.5 text-xs font-medium text-muted-foreground">
        Backend connected · no registry run yet
      </span>
    )
  }

  const ok = latestRun.status === "success"
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-3 py-1.5 text-xs font-medium ${
        ok ? "bg-green-soft text-green" : "bg-red-soft text-red"
      }`}
    >
      {ok ? <CheckCircle2 className="h-3.5 w-3.5" /> : <AlertCircle className="h-3.5 w-3.5" />}
      {latestRun.run_type === "seed" && latestRun.status === "success" ? (
        <>
          <span className="sm:hidden">Connected</span>
          <span className="hidden sm:inline">
            Backend connected · paper anchors seeded
          </span>
        </>
      ) : (
        `${latestRun.run_type}: ${latestRun.status}`
      )}
    </span>
  )
}

function ProductStatement({
  latestRun,
  viewErrors,
  counts,
}: {
  latestRun: PipelineRun | undefined
  viewErrors: string[]
  counts: RunCounts
}) {
  return (
    <section className="rounded-lg border border-border bg-card px-4 py-3">
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <p className="text-sm font-medium">
          Official policy documents → PCI deltas → eligible Kalshi markets →
          timestamped forecast commitments.
        </p>
        <p className="text-xs text-muted-foreground">
          Last registry update: {latestRun ? compactDate(latestRun.started_at) : "not run"}
        </p>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
        <RunMetric label="Policy events" value={counts.policyEvents} />
        <RunMetric label="Eligible markets" value={counts.eligibleMarkets} />
        <RunMetric label="Forecasts" value={counts.forecasts} />
        <RunMetric label="Trade proposals" value={counts.tradeProposals} />
      </div>
      {viewErrors.length > 0 && (
        <p className="mt-2 text-xs text-red">
          Some Supabase views failed: {viewErrors.join(", ")}
        </p>
      )}
    </section>
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

function RunMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md bg-muted px-3 py-2">
      <div className="text-[10px] font-medium uppercase text-muted-foreground">
        {label}
      </div>
      <div className="mt-0.5 text-lg font-semibold">{value}</div>
    </div>
  )
}

function ProvisionStrip({ provisions }: { provisions: CurrentPci[] }) {
  if (!provisions.length) {
    return (
      <section className="mt-4 rounded-lg border border-dashed border-border bg-card p-6 text-sm text-muted-foreground">
        No provision anchors are loaded. Seed Supabase before using the registry.
      </section>
    )
  }

  return (
    <section className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-6">
      {provisions.map((provision) => (
        <div
          key={provision.code}
          className="rounded-lg border border-border bg-card p-3"
        >
          <div className="flex items-start justify-between gap-2">
            <div>
              <div className="font-semibold">{provision.code}</div>
              <div className="line-clamp-2 min-h-10 text-xs leading-5 text-muted-foreground">
                {provision.name}
              </div>
            </div>
            <DeltaBadge value={provision.delta_this_week} />
          </div>

          <div className="mt-3 flex items-end justify-between">
            <div>
              <div className="text-[10px] font-medium uppercase text-muted-foreground">
                Current PCI
              </div>
              <div className="text-2xl font-semibold">
                {score(provision.pci ?? provision.baseline_pci)}
              </div>
              <div className="text-xs text-muted-foreground">
                OBBBA stress PCI {score(provision.obbba_post_pci)}
              </div>
              <div className="mt-1 truncate whitespace-nowrap text-[10px] text-muted-foreground">
                {compactOrigin(provision.data_origin)} · {provision.week ?? "no week"}
              </div>
            </div>
            <DimensionBars provision={provision} />
          </div>
        </div>
      ))}
    </section>
  )
}

function DimensionBars({ provision }: { provision: CurrentPci }) {
  const rows = [
    ["S", provision.specificity],
    ["D", provision.durability],
    ["E", provision.enforceability],
  ] as const

  return (
    <div className="w-20 space-y-1">
      {rows.map(([label, value]) => (
        <div key={label} className="flex items-center gap-1.5">
          <span className="w-3 text-[10px] text-muted-foreground">{label}</span>
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
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

function ForecastCard({ forecast }: { forecast: Forecast }) {
  const edgePositive = forecast.edge >= 0
  const marketTitle =
    forecast.market_title ?? `${forecast.venue.toUpperCase()} ${forecast.market_ticker}`

  return (
    <article className="rounded-lg border border-border bg-card p-4 transition hover:border-muted-foreground/40 hover:shadow-sm">
      <div className="flex items-start gap-3">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-muted font-semibold">
          {forecast.provision}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span>{forecast.venue.toUpperCase()}</span>
            <span>·</span>
            <span className="truncate">{forecast.market_ticker}</span>
          </div>
          <h2 className="mt-1 line-clamp-2 min-h-11 text-sm font-semibold leading-5">
            {marketTitle}
          </h2>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-2">
        <ProbabilityBox label="Kalshi implied" value={percent(forecast.market_probability)} />
        <ProbabilityBox label="PCI forecast" value={percent(forecast.model_probability)} strong />
        <div
          className={`rounded-lg p-3 ${
            edgePositive ? "bg-green-soft text-green" : "bg-red-soft text-red"
          }`}
        >
          <div className="text-xs font-medium opacity-80">PCI-Kalshi gap</div>
          <div className="mt-1 flex items-center gap-1 text-lg font-semibold">
            {edgePositive ? (
              <TrendingUp className="h-4 w-4" />
            ) : (
              <TrendingDown className="h-4 w-4" />
            )}
            {edgeLabel(forecast.edge)}
          </div>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2 text-xs">
        <Chip>{forecast.shock_type ?? "policy signal"}</Chip>
        <Chip>{forecast.dimension ?? "composite"}</Chip>
        <Chip>{Math.round(forecast.confidence * 100)}% confidence</Chip>
        <Chip>Kalshi close {compactDate(forecast.market_close_time)}</Chip>
      </div>

      <details className="mt-4 rounded-lg bg-muted px-3 py-2 text-sm">
        <summary className="cursor-pointer font-medium">Evidence and rules</summary>
        <div className="mt-2 space-y-2 text-muted-foreground">
          <p>{sourceTitle(forecast.source_doc)}</p>
          {forecast.market_rules && <p>{forecast.market_rules}</p>}
          {forecast.resolution_risk_notes && <p>{forecast.resolution_risk_notes}</p>}
        </div>
      </details>
    </article>
  )
}

function ProbabilityBox({
  label,
  value,
  strong = false,
}: {
  label: string
  value: string
  strong?: boolean
}) {
  return (
    <div className="rounded-lg bg-muted p-3">
      <div className="text-xs font-medium text-muted-foreground">{label}</div>
      <div className={`mt-1 text-lg ${strong ? "font-bold" : "font-semibold"}`}>
        {value}
      </div>
    </div>
  )
}

function ProposalPanel({ proposals }: { proposals: TradeProposal[] }) {
  const ordered = [...proposals].sort((a, b) => {
    const aPending = a.approval_status === "pending_human_approval" ? 0 : 1
    const bPending = b.approval_status === "pending_human_approval" ? 0 : 1
    return aPending - bPending || a.approval_status.localeCompare(b.approval_status)
  })

  return (
    <section className="rounded-lg border border-border bg-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h2 className="font-semibold">Gated trade proposals</h2>
          <p className="text-xs text-muted-foreground">
            Human approval required; execution hidden from public UI
          </p>
        </div>
        <ShieldCheck className="h-5 w-5 text-muted-foreground" />
      </div>

      {ordered.length ? (
        <div className="space-y-3">
          {ordered.map((proposal) => (
            <div key={proposal.proposal_id} className="rounded-lg bg-muted p-3">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium">
                    {proposal.market_ticker}
                  </div>
                  <div className="text-xs text-muted-foreground">{proposal.venue.toUpperCase()}</div>
                </div>
                <span
                  className={`rounded-full px-2 py-1 text-xs font-medium ${
                    proposal.risk_passed
                      ? "bg-green-soft text-green"
                      : "bg-red-soft text-red"
                  }`}
                >
                  {proposal.approval_status.replaceAll("_", " ")}
                </span>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-3">
                <Metric label="Gap" value={edgeLabel(proposal.edge)} />
                <Metric
                  label="Confidence"
                  value={percent(proposal.confidence)}
                />
                <Metric
                  label="Human gate"
                  value={proposal.human_approval_required ? "required" : "none"}
                />
                <Metric label="Risk gate" value={proposal.risk_passed ? "passed" : "blocked"} />
                <Metric
                  label="Execution"
                  value={
                    proposal.public_execution_status === "backend_enabled_after_approval"
                      ? "backend gated"
                      : "public unavailable"
                  }
                />
              </div>
              {proposal.rejection_reasons.length > 0 && (
                <div className="mt-2 text-xs text-red">
                  {proposal.rejection_reasons.join(", ")}
                </div>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-lg bg-muted p-4 text-sm text-muted-foreground">
          No proposals are pending approval.
        </div>
      )}
    </section>
  )
}

function MarketScanPanel({ snapshots }: { snapshots: MarketSnapshot[] }) {
  return (
    <section className="rounded-lg border border-border bg-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h2 className="font-semibold">Market scan</h2>
          <p className="text-xs text-muted-foreground">
            Read-only rows from the latest policy-market scan
          </p>
        </div>
        <Search className="h-5 w-5 text-muted-foreground" />
      </div>

      {snapshots.length ? (
        <div className="space-y-3">
          {snapshots.slice(0, 5).map((market) => (
            <div key={`${market.venue}:${market.ticker}`} className="rounded-lg bg-muted p-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-xs font-medium text-muted-foreground">
                    {market.venue.toUpperCase()} · {market.ticker}
                  </div>
                  <div className="mt-1 line-clamp-2 text-sm font-medium">
                    {market.title ?? market.event_ticker ?? "Policy market"}
                  </div>
                </div>
                <span className="rounded-full bg-card px-2 py-1 text-xs font-medium text-muted-foreground">
                  {market.status ?? "unknown"}
                </span>
              </div>

              <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                <Metric label="Implied" value={percent(market.market_probability)} />
                <Metric label="Spread" value={percent(market.bid_ask_spread)} />
                <Metric label="Liquidity" value={money(market.liquidity_dollars)} />
              </div>
              <div className="mt-2 flex flex-wrap gap-2 text-xs">
                {market.policy_relevant && <Chip>policy relevant</Chip>}
                {market.query_name && <Chip>{market.query_name}</Chip>}
                <Chip>close {compactDate(market.close_time)}</Chip>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-lg bg-muted p-4 text-sm text-muted-foreground">
          No eligible policy markets in the latest scan. Unrelated or ambiguous
          markets are rejected before publication.
        </div>
      )}
    </section>
  )
}

function EventFeed({ events }: { events: PolicyEvent[] }) {
  return (
    <section className="rounded-lg border border-border bg-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-semibold">Official policy events scored</h2>
        <Activity className="h-5 w-5 text-muted-foreground" />
      </div>
      {events.length ? (
        <div className="space-y-3">
          {events.map((event) => (
            <a
              key={event.event_id}
              href={event.url ?? undefined}
              className="block rounded-lg bg-muted p-3 transition hover:bg-border/50"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-xs font-medium text-muted-foreground">
                    {event.provision} · {event.week}
                  </div>
                  <div className="mt-1 line-clamp-2 text-sm font-medium">
                    {event.title ?? event.agency ?? "Policy event"}
                  </div>
                </div>
                {event.url && <ExternalLink className="h-4 w-4 shrink-0" />}
              </div>
              <div className="mt-2">
                <DeltaBadge value={event.pci_delta} />
              </div>
            </a>
          ))}
        </div>
      ) : (
        <div className="rounded-lg bg-muted p-4 text-sm text-muted-foreground">
          No scored policy events are published yet.
        </div>
      )}
    </section>
  )
}

function ResolvedSection({ resolved }: { resolved: ResolvedForecast[] }) {
  return (
    <section className="mt-5 rounded-lg border border-border bg-card p-4">
      <h2 className="font-semibold">Resolved track record</h2>
      {resolved.length ? (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="text-xs text-muted-foreground">
              <tr>
                <th className="py-2">Market</th>
                <th>Provision</th>
                <th>PCI forecast</th>
                <th>Kalshi implied</th>
                <th>Outcome</th>
                <th>Brier</th>
              </tr>
            </thead>
            <tbody>
              {resolved.map((row) => (
                <tr key={row.forecast_id} className="border-t border-border">
                  <td className="max-w-sm truncate py-3">{row.market_title}</td>
                  <td>{row.provision}</td>
                  <td>{percent(row.model_probability)}</td>
                  <td>{percent(row.market_probability)}</td>
                  <td>{row.result}</td>
                  <td>{row.brier_score.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="mt-3 rounded-lg bg-muted p-4 text-sm text-muted-foreground">
          No resolved forecast commitments yet; demo outcomes are not shown.
        </div>
      )}
    </section>
  )
}

function EmptyForecastState({
  hasBackend,
  hasViewErrors,
}: {
  hasBackend: boolean
  hasViewErrors: boolean
}) {
  const message = !hasBackend
    ? "Supabase is not configured; seed and connect the registry backend to load anchors."
    : hasViewErrors
      ? "Supabase is configured, but one or more public views failed to load."
      : "No official PCI event has matched a clean Kalshi market yet."

  return (
    <div className="flex min-h-[360px] items-center justify-center rounded-lg border border-dashed border-border bg-card p-8 text-center">
      <div>
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-muted">
          <Search className="h-5 w-5 text-muted-foreground" />
        </div>
        <h2 className="mt-4 text-lg font-semibold">
          No live forecast commitments yet
        </h2>
        <p className="mt-2 max-w-md text-sm text-muted-foreground">
          {message}
        </p>
      </div>
    </div>
  )
}

function FilteredEmptyState({
  activeProvision,
  query,
}: {
  activeProvision: string
  query: string
}) {
  return (
    <div className="rounded-lg border border-dashed border-border bg-card p-8 text-center">
      <h2 className="text-lg font-semibold">No commitments match this filter</h2>
      <p className="mt-2 text-sm text-muted-foreground">
        Active filter: {activeProvision}
        {query.trim() ? ` · "${query.trim()}"` : ""}
      </p>
    </div>
  )
}

function DeltaBadge({ value }: { value: number | null | undefined }) {
  const numeric = value ?? 0
  const positive = numeric > 0
  const neutral = numeric === 0
  return (
    <span
      className={`rounded-full px-2 py-1 text-xs font-medium ${
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

function Chip({ children }: { children: ReactNode }) {
  return (
    <span className="rounded-full bg-muted px-2 py-1 text-muted-foreground">
      {children}
    </span>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-muted-foreground">{label}</div>
      <div className="font-semibold">{value}</div>
    </div>
  )
}
