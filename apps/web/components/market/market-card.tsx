"use client"

import type { PolicyMarket } from "@/lib/market-model"
import {
  formatCents,
  formatCompactMoney,
  formatDate,
  formatEdge,
  formatKind,
  formatScore,
} from "@/components/market/format"

export function MarketCard({
  market,
  active = false,
  onSelect,
}: {
  market: PolicyMarket
  active?: boolean
  onSelect?: (id: string) => void
}) {
  const primaryWidth = valueWidth(market.primaryValue, market.kind === "policy" ? 5 : 1)
  const secondaryWidth = valueWidth(market.secondaryValue, market.kind === "policy" ? 5 : 1)

  return (
    <button
      type="button"
      onClick={() => onSelect?.(market.id)}
      className={`market-card ${active ? "market-card-active" : ""}`}
    >
      <div className="market-card-head">
        <div className="market-icon">{market.provision || market.kind.slice(0, 2).toUpperCase()}</div>
        <div className="market-card-title-wrap">
          <div className="market-card-meta">
            <span>{formatKind(market.kind)}</span>
            <span>{market.lane}</span>
            {market.ticker && <span>{market.ticker}</span>}
            {market.sourceCount > 0 && <span>{market.sourceCount} sources</span>}
          </div>
          <h3>{market.title}</h3>
        </div>
      </div>

      <div className="market-odds">
        <OddsBar
          label={market.primaryLabel}
          value={market.kind === "policy" ? formatScore(market.primaryValue) : formatCents(market.primaryValue)}
          width={primaryWidth}
          tone="yes"
        />
        <OddsBar
          label={market.secondaryLabel}
          value={market.kind === "policy" ? formatScore(market.secondaryValue) : formatCents(market.secondaryValue)}
          width={secondaryWidth}
          tone="no"
        />
      </div>

      <div className="market-card-foot">
        <span>{market.status}</span>
        <span>{market.edge !== null ? formatEdge(market.edge) : market.volume ? `${formatCompactMoney(market.volume)} vol` : "Tracked"}</span>
        <span>{formatDate(market.closeTime ?? market.updatedAt)}</span>
      </div>
    </button>
  )
}

function OddsBar({
  label,
  value,
  width,
  tone,
}: {
  label: string
  value: string
  width: string
  tone: "yes" | "no"
}) {
  return (
    <div className="odds-bar">
      <div className={`odds-fill odds-${tone}`} style={{ width }} />
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function valueWidth(value: number | null, max: number) {
  if (value === null || Number.isNaN(value)) return "4%"
  return `${Math.max(4, Math.min(100, (value / max) * 100))}%`
}
