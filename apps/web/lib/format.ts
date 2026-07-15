export function formatScore(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-"
  return value.toFixed(value % 1 === 0 ? 0 : 2)
}

export function formatDelta(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value) || value === 0) {
    return "--"
  }
  // Arrow + sign so direction never relies on color alone (WCAG 1.4.1).
  const arrow = value > 0 ? "▲" : "▼"
  const sign = value > 0 ? "+" : "−"
  return `${arrow} ${sign}${Math.abs(value).toFixed(2)}`
}

export function deltaToneClass(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value) || value === 0) {
    return "delta-value delta-neutral"
  }
  return value > 0 ? "delta-value delta-positive" : "delta-value delta-negative"
}

export function formatDate(value: string | null | undefined) {
  if (!value) return "-"
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  }).format(new Date(value))
}
