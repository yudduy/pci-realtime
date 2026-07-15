import type { TerminalDataStatus } from "@/lib/terminal-data"

export function DataStatus({ status }: { status: TerminalDataStatus }) {
  const className = `data-status data-status-${status.mode}`

  if (status.mode === "degraded") {
    return (
      <div
        className={className}
        data-testid="data-status"
        data-mode={status.mode}
        role="status"
      >
        <details>
          <summary>
            PARTIAL DATA — {status.viewErrors.length} sources failing
          </summary>
          <div className="data-status-errors">
            <strong>Unavailable registry views</strong>
            <ul>
              {status.viewErrors.map((error) => (
                <li key={error}>{error}</li>
              ))}
            </ul>
          </div>
        </details>
      </div>
    )
  }

  return (
    <div
      className={className}
      data-testid="data-status"
      data-mode={status.mode}
      role="status"
    >
      <span>{statusText(status)}</span>
    </div>
  )
}

function statusText(status: TerminalDataStatus) {
  if (status.mode === "disconnected") {
    return "DISCONNECTED — showing paper baselines (Aug 2022)"
  }
  if (status.mode === "stale") {
    return `STALE — last source refresh ${formatStatusDate(status.lastSourceRefresh)} (${status.staleDays ?? 0} days ago)`
  }
  return `Updated ${formatStatusDate(status.lastSourceRefresh)}`
}

function formatStatusDate(value: string | null) {
  if (!value) return "—"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "—"
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(date)
}
