import type { EvidenceItem, PolicyEvent, RegistryData } from "@/lib/data"
import type { PolicyMarket } from "@/lib/market-model"
import {
  formatCents,
  formatCompactMoney,
  formatDate,
  formatEdge,
  formatKind,
  formatPercent,
  formatScore,
} from "@/components/market/format"
import { MarketCoveragePanel } from "@/components/market/market-coverage"
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
  const citations = citationsForMarket(market, data, relatedEvents)
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

      {market.kind === "policy" && (
        <MarketCoveragePanel data={data} selectedProvision={market.provision} compact />
      )}

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

      {citations.length > 0 && (
        <section className="detail-section">
          <h3>Why This Moved</h3>
          <div className="citation-list">
            {citations.slice(0, 4).map((citation, index) => (
              <CitationRow key={citation.evidence_id} citation={citation} index={index + 1} />
            ))}
          </div>
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

      <section className="detail-section">
        <h3>Trace</h3>
        <details className="trace-drawer">
          <summary>Evidence path</summary>
          <ol>
            <li>{citations.length ? "Fetched public source documents" : "Waiting for cited public sources"}</li>
            <li>{relatedEvents.length ? "Extracted policy evidence" : "No scored policy move yet"}</li>
            <li>{market.policy || market.forecast ? "Updated PCI dimensions" : "PCI link pending"}</li>
            <li>
              {market.market || market.forecast
                ? "Matched public market data"
                : data.marketDiscoveryCandidates.length
                  ? "No eligible market after public venue scan"
                  : "Public market scan pending"}
            </li>
            <li>{market.forecast ? "Published model odds" : "Forecast pending"}</li>
            <li>{proposals.length ? "Proposal gate recorded" : "No public execution path"}</li>
          </ol>
        </details>
      </section>
    </aside>
  )
}

function CitationRow({
  citation,
  index,
}: {
  citation: EvidenceItem
  index: number
}) {
  const source = citation.source_name ?? "Official source"
  const title = citation.source_title ?? citation.snippet ?? source
  const body = (
    <>
      <span>[{index}] {source}</span>
      <strong>{title}</strong>
      {citation.snippet && <em>{citation.snippet}</em>}
    </>
  )

  if (citation.url) {
    return (
      <a href={citation.url} className="citation-row">
        {body}
      </a>
    )
  }

  return <div className="citation-row">{body}</div>
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

function citationsForMarket(
  market: PolicyMarket,
  data: RegistryData,
  relatedEvents: PolicyEvent[],
): EvidenceItem[] {
  const evidenceIds = new Set<string>()
  const targetIds = new Set<string>()

  if (market.forecast?.forecast_id) targetIds.add(`forecasts:${market.forecast.forecast_id}`)
  if (market.market?.venue && market.market.ticker) {
    targetIds.add(`market_snapshots:${market.market.venue}:${market.market.ticker}`)
  }
  for (const event of relatedEvents) targetIds.add(`policy_events:${event.event_id}`)

  for (const link of data.sourceLinks) {
    if (targetIds.has(`${link.target_table}:${link.target_id}`)) {
      evidenceIds.add(link.evidence_id)
    }
  }

  const citations = data.evidenceItems.filter((item) => evidenceIds.has(item.evidence_id))
  if (citations.length) return citations

  return relatedEvents
    .map((event) => data.policyEvents.find((item) => item.event_id === event.event_id))
    .filter((event): event is NonNullable<typeof event> => Boolean(event))
    .map((event) => ({
      evidence_id: `fallback:${event.event_id}`,
      source_doc_id: event.doc_id ?? null,
      provision: event.provision,
      provision_name: event.provision_name,
      evidence_type: "policy_event",
      snippet: event.rationale,
      normalized_signal: `${event.pci_delta > 0 ? "+" : ""}${event.pci_delta.toFixed(2)} PCI`,
      score_dimension: "pci",
      confidence: event.confidence,
      extractor_version: event.prompt_version ?? null,
      created_at: event.created_at,
      source: event.doc_source ?? null,
      source_name: event.agency ?? "Official source",
      source_type: "official_text",
      source_title: event.title,
      agency: event.agency,
      url: event.url,
      published_at: event.week_start,
      fetched_at: event.created_at,
    }))
}
