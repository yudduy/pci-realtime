import { formatCents, formatCompactMoney, formatDate } from "@/components/market/format"
import type { SubMarketRow } from "@/lib/provision-view"

export function SubMarketList({ rows }: { rows: SubMarketRow[] }) {
  if (!rows.length) {
    return (
      <p className="sub-market-empty" role="status">
        No eligible market or near-miss candidate is attached to this provision yet. The next scheduled scan will
        update this list.
      </p>
    )
  }

  return (
    <ul className="sub-market-list">
      {rows.map((row) => (
        <SubMarketRowItem key={row.id} row={row} />
      ))}
    </ul>
  )
}

function SubMarketRowItem({ row }: { row: SubMarketRow }) {
  const eligible = row.source === "snapshot"
  return (
    <li className={`sub-market-row ${eligible ? "eligible" : "near-miss"}`}>
      <div className="sub-market-row-head">
        <div className="sub-market-title">
          <strong>{row.title}</strong>
          <span>
            {row.venue.toUpperCase()} · {row.ticker}
          </span>
        </div>
        <div className="sub-market-pricing" aria-label="Market pricing">
          {row.yes !== null ? (
            <span className="sub-market-yes">Yes {formatCents(row.yes)}</span>
          ) : (
            <span className="sub-market-yes muted">Yes —</span>
          )}
          {row.no !== null ? (
            <span className="sub-market-no">No {formatCents(row.no)}</span>
          ) : (
            <span className="sub-market-no muted">No —</span>
          )}
        </div>
      </div>

      <dl className="sub-market-facts">
        <FactPill label="Status" value={row.status} />
        <FactPill label="Liquidity" value={formatCompactMoney(row.liquidity)} />
        <FactPill label="Volume" value={formatCompactMoney(row.volume)} />
        <FactPill label="Close" value={formatDate(row.closeTime)} />
      </dl>

      {!eligible && row.rejectionReasons.length > 0 && (
        <ul className="sub-market-rejections" aria-label="Rejection reasons">
          {row.rejectionReasons.map((reason) => (
            <li key={reason}>{humanizeReason(reason)}</li>
          ))}
        </ul>
      )}

      {row.url && (
        <a href={row.url} className="sub-market-source" rel="noopener noreferrer">
          View market source
        </a>
      )}
    </li>
  )
}

function FactPill({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  )
}

function humanizeReason(reason: string) {
  return reason.replaceAll("_", " ")
}
