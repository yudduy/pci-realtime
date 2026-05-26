"use client"

import { useMemo, useState } from "react"
import type { PolicyMarket } from "@/lib/market-model"
import {
  formatCents,
  formatCompactMoney,
  formatDate,
  formatEdge,
  formatKind,
  formatScore,
} from "@/components/market/format"

type SortKey = "market" | "probability" | "edge" | "liquidity" | "close"

export function MarketTable({
  markets,
  selectedId,
  onSelect,
}: {
  markets: PolicyMarket[]
  selectedId: string | null
  onSelect: (id: string) => void
}) {
  const [sortKey, setSortKey] = useState<SortKey>("probability")
  const [descending, setDescending] = useState(true)

  const sorted = useMemo(() => {
    return [...markets].sort((a, b) => {
      const value = compareValue(a, b, sortKey)
      return descending ? -value : value
    })
  }, [markets, sortKey, descending])

  function changeSort(next: SortKey) {
    if (sortKey === next) {
      setDescending((value) => !value)
      return
    }
    setSortKey(next)
    setDescending(next !== "market")
  }

  return (
    <div className="market-table-wrap">
      <table className="market-table">
        <thead>
          <tr>
            <Sortable label="Market" active={sortKey === "market"} onClick={() => changeSort("market")} />
            <Sortable label="Probability" active={sortKey === "probability"} onClick={() => changeSort("probability")} />
            <Sortable label="Model" active={false} onClick={() => undefined} />
            <Sortable label="Edge" active={sortKey === "edge"} onClick={() => changeSort("edge")} />
            <Sortable label="Liquidity" active={sortKey === "liquidity"} onClick={() => changeSort("liquidity")} />
            <Sortable label="Close" active={sortKey === "close"} onClick={() => changeSort("close")} />
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((market) => (
            <tr
              key={market.id}
              className={selectedId === market.id ? "selected" : ""}
              onClick={() => onSelect(market.id)}
            >
              <td>
                <div className="table-market">
                  <span className="table-icon">{market.provision || market.kind.slice(0, 2).toUpperCase()}</span>
                  <div>
                    <div className="table-title">{market.title}</div>
                    <div className="table-subtitle">
                      {formatKind(market.kind)} / {market.lane}
                    </div>
                  </div>
                </div>
              </td>
              <td>{market.kind === "policy" ? formatScore(market.primaryValue) : formatCents(market.primaryValue)}</td>
              <td>{market.kind === "policy" ? formatScore(market.secondaryValue) : formatCents(market.secondaryValue)}</td>
              <td>{formatEdge(market.edge)}</td>
              <td>{formatCompactMoney(market.liquidity ?? market.volume)}</td>
              <td>{formatDate(market.closeTime ?? market.updatedAt)}</td>
              <td>
                <span className="table-status">{market.status}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {!sorted.length && (
        <div className="market-empty">
          No matching policy markets. Clear search or pick another filter.
        </div>
      )}
    </div>
  )
}

function Sortable({
  label,
  active,
  onClick,
}: {
  label: string
  active: boolean
  onClick: () => void
}) {
  return (
    <th>
      <button type="button" onClick={onClick} className={active ? "active" : ""}>
        {label}
      </button>
    </th>
  )
}

function compareValue(a: PolicyMarket, b: PolicyMarket, key: SortKey) {
  if (key === "market") return a.title.localeCompare(b.title)
  if (key === "probability") return numeric(a.primaryValue) - numeric(b.primaryValue)
  if (key === "edge") return numeric(a.edge) - numeric(b.edge)
  if (key === "liquidity") return numeric(a.liquidity ?? a.volume) - numeric(b.liquidity ?? b.volume)
  return timeValue(a.closeTime ?? a.updatedAt) - timeValue(b.closeTime ?? b.updatedAt)
}

function numeric(value: number | null | undefined) {
  return value === null || value === undefined || Number.isNaN(value) ? -Infinity : value
}

function timeValue(value: string | null | undefined) {
  if (!value) return -Infinity
  return new Date(value).getTime()
}
