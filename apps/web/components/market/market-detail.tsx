import type { PolicyMarket, RegistryData } from "@/lib/data"
import {
  formatCents,
  formatCompactMoney,
  formatDate,
  formatEdge,
  formatKind,
  formatPercent,
  formatScore,
} from "@/components/market/format"
import { PolicyTrend } from "@/components/market/policy-trend"

export function MarketDetail({
  market,
  data,
}: {
  market: PolicyMarket | undefined
  data: RegistryData
}) {
  if (!market) {
    return <aside className="detail-panel detail-empty">Select a policy market to inspect the source and trend.</aside>
  }

  const relatedEvents = data.policyEvents
    .filter((event) => event.provision === market.provision)
    .slice(0, 3)
  const proposals = data.tradeProposals
    .filter(
      (proposal) =>
        proposal.forecast_id === market.forecast?.forecast_id ||
        proposal.market_ticker === market.forecast?.market_ticker ||
        proposal.market_ticker === market.market?.ticker,
    )
    .slice(0, 2)

  return (
    <aside className="detail-panel">
      <div className="detail-hero">
        <div className="detail-meta">
          <span>{formatKind(market.kind)}</span>
          <span>{market.lane}</span>
        </div>
        <h2>{market.title}</h2>
        <p>{market.subtitle}</p>
        <div className="detail-odds">
          <DetailPrice
            label={market.primaryLabel}
            value={market.kind === "policy" ? formatScore(market.primaryValue) : formatCents(market.primaryValue)}
          />
          <DetailPrice
            label={market.secondaryLabel}
            value={market.kind === "policy" ? formatScore(market.secondaryValue) : formatCents(market.secondaryValue)}
            muted
          />
        </div>
      </div>

      <PolicyTrend
        timelines={data.provisionTimelines}
        policies={data.currentPci}
        provision={market.provision || undefined}
      />

      <section className="detail-section">
        <h3>Market Facts</h3>
        <div className="detail-facts">
          <Fact label="Status" value={market.status} />
          <Fact label="Edge" value={formatEdge(market.edge)} />
          <Fact label="Confidence" value={formatPercent(market.confidence)} />
          <Fact label="Liquidity" value={formatCompactMoney(market.liquidity)} />
          <Fact label="Volume" value={formatCompactMoney(market.volume)} />
          <Fact label="Close" value={formatDate(market.closeTime)} />
        </div>
      </section>

      {market.policy && (
        <section className="detail-section">
          <h3>PCI Breakdown</h3>
          <Breakdown label="Specific" value={market.policy.specificity} />
          <Breakdown label="Durable" value={market.policy.durability} />
          <Breakdown label="Enforced" value={market.policy.enforceability} />
          <p>{market.policy.obbba_summary}</p>
        </section>
      )}

      {market.forecast && (
        <section className="detail-section">
          <h3>Forecast Basis</h3>
          <p>{sourceTitle(market.forecast.source_doc)}</p>
          {market.forecast.market_rules && <p>{market.forecast.market_rules}</p>}
          {market.forecast.resolution_risk_notes && <p>{market.forecast.resolution_risk_notes}</p>}
        </section>
      )}

      {market.market?.resolution_text && (
        <section className="detail-section">
          <h3>Resolution Rules</h3>
          <p>{market.market.resolution_text}</p>
        </section>
      )}

      {(proposals.length > 0 || relatedEvents.length > 0) && (
        <section className="detail-section">
          {proposals.length > 0 && (
            <>
              <h3>Trade Gate</h3>
              <div className="detail-stack">
                {proposals.map((proposal) => (
                  <div key={proposal.proposal_id} className="proposal-row">
                    <strong>{proposal.market_ticker}</strong>
                    <span>
                      {proposal.approval_status.replaceAll("_", " ")} / {formatEdge(proposal.edge)}
                    </span>
                  </div>
                ))}
              </div>
            </>
          )}

          {relatedEvents.length > 0 && (
            <>
              <h3>Latest Policy Moves</h3>
              <div className="detail-stack">
                {relatedEvents.map((event) => (
                  <a key={event.event_id} href={event.url ?? undefined} className="proposal-row">
                    <strong>{event.title ?? event.agency ?? "Policy event"}</strong>
                    <span>{formatDate(event.created_at)} / {event.agency ?? event.provision}</span>
                  </a>
                ))}
              </div>
            </>
          )}
        </section>
      )}
    </aside>
  )
}

function DetailPrice({
  label,
  value,
  muted = false,
}: {
  label: string
  value: string
  muted?: boolean
}) {
  return (
    <div className={muted ? "detail-price detail-price-muted" : "detail-price"}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function Breakdown({
  label,
  value,
}: {
  label: string
  value: number | null | undefined
}) {
  const width = `${Math.max(0, Math.min(100, ((value ?? 0) / 5) * 100))}%`
  return (
    <div className="breakdown-line">
      <div>
        <span>{label}</span>
        <strong>{formatScore(value)}</strong>
      </div>
      <div>
        <span style={{ width }} />
      </div>
    </div>
  )
}

function sourceTitle(sourceDoc: Record<string, unknown>) {
  return String(sourceDoc.title ?? sourceDoc.url ?? "Official source")
}
