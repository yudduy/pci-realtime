export function formatPercent(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-"
  return `${Math.round(value * 100)}%`
}

export function formatCents(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-"
  return `${Math.round(value * 100)}c`
}

export function formatScore(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-"
  return value.toFixed(value % 1 === 0 ? 0 : 2)
}

export function formatDelta(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value) || value === 0) {
    return "--"
  }
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}`
}

export function deltaToneClass(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value) || value === 0) {
    return "delta-value delta-neutral"
  }
  return value > 0 ? "delta-value delta-positive" : "delta-value delta-negative"
}

export function formatMoney(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-"
  return `$${Math.round(value).toLocaleString("en-US")}`
}

export function formatCompactMoney(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-"
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `$${Math.round(value / 1_000)}K`
  return formatMoney(value)
}

export function formatDate(value: string | null | undefined) {
  if (!value) return "-"
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
  }).format(new Date(value))
}

export function formatDateTime(value: string | null | undefined) {
  if (!value) return "-"
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value))
}

export function formatEdge(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-"
  const sign = value >= 0 ? "+" : ""
  return `${sign}${Math.round(value * 100)} pts`
}

export function formatKind(kind: string) {
  if (kind === "forecast") return "Forecast"
  if (kind === "policy") return "Policy"
  if (kind === "market") return "Market"
  if (kind === "resolved") return "Resolved"
  return kind
}
