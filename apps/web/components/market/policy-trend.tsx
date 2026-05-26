import type { CurrentPci, ProvisionTimeline } from "@/lib/data"
import { formatDate, formatScore } from "@/components/market/format"

export function PolicyTrend({
  timelines,
  policies,
  provision,
}: {
  timelines: ProvisionTimeline[]
  policies: CurrentPci[]
  provision?: string
}) {
  const points = buildPoints(timelines, policies, provision)
  const path = buildPath(points)
  const latest = points.at(-1)
  const first = points[0]

  return (
    <section className="trend-panel" aria-label="Policy credibility trend">
      <div className="trend-panel-head">
        <div>
          <p>Policy Credibility Index</p>
          <h2>{provision ? `${provision} trend` : "Live policy trend"}</h2>
        </div>
        <div className="trend-score">
          <span>{latest ? formatScore(latest.value) : "-"}</span>
          <small>{latest ? formatDate(latest.date) : "No data"}</small>
        </div>
      </div>
      <svg viewBox="0 0 640 180" role="img" aria-label="PCI trend chart">
        <defs>
          <linearGradient id="trendFill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#2563eb" stopOpacity="0.24" />
            <stop offset="100%" stopColor="#2563eb" stopOpacity="0" />
          </linearGradient>
        </defs>
        <line x1="34" x2="620" y1="32" y2="32" className="trend-grid" />
        <line x1="34" x2="620" y1="90" y2="90" className="trend-grid" />
        <line x1="34" x2="620" y1="148" y2="148" className="trend-grid" />
        {path && <path d={`${path} L 620 158 L 34 158 Z`} fill="url(#trendFill)" />}
        {path && <path d={path} className="trend-line" />}
        {points.map((point) => (
          <circle key={`${point.date}-${point.value}`} cx={point.x} cy={point.y} r="3.5" className="trend-dot" />
        ))}
        <text x="34" y="172" className="trend-axis">
          {first ? formatDate(first.date) : ""}
        </text>
        <text x="620" y="172" textAnchor="end" className="trend-axis">
          {latest ? formatDate(latest.date) : ""}
        </text>
      </svg>
    </section>
  )
}

type Point = {
  date: string
  value: number
  x: number
  y: number
}

function buildPoints(
  timelines: ProvisionTimeline[],
  policies: CurrentPci[],
  provision?: string,
): Point[] {
  const rows = provision
    ? timelines.filter((row) => row.provision === provision)
    : averageTimeline(timelines)

  if (rows.length) {
    return scalePoints(rows.map((row) => ({ date: row.week_start, value: Number(row.pci) })))
  }

  return scalePoints(
    policies.map((policy) => ({
      date: policy.week_start ?? policy.updated_at ?? "2022-08-16",
      value: Number(policy.pci ?? policy.baseline_pci),
    })),
  )
}

function averageTimeline(timelines: ProvisionTimeline[]) {
  const byWeek = new Map<string, { date: string; values: number[] }>()
  for (const row of timelines) {
    const existing = byWeek.get(row.week) ?? { date: row.week_start, values: [] }
    existing.values.push(Number(row.pci))
    byWeek.set(row.week, existing)
  }

  return [...byWeek.values()]
    .map((row) => ({
      week_start: row.date,
      pci: row.values.reduce((sum, value) => sum + value, 0) / row.values.length,
    }))
    .sort((a, b) => new Date(a.week_start).getTime() - new Date(b.week_start).getTime())
}

function scalePoints(rows: { date: string; value: number }[]): Point[] {
  const sorted = rows
    .filter((row) => Number.isFinite(row.value))
    .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
    .slice(-20)

  if (!sorted.length) return []

  const xStep = sorted.length === 1 ? 0 : 586 / (sorted.length - 1)
  return sorted.map((row, index) => ({
    date: row.date,
    value: row.value,
    x: 34 + index * xStep,
    y: 158 - ((row.value - 1) / 4) * 132,
  }))
}

function buildPath(points: Point[]) {
  if (!points.length) return ""
  return points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ")
}
