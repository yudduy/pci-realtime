"use client"

import { useMemo, useState } from "react"
import type {
  CurrentPci,
  EvidenceItem,
  PolicyEvent,
  ProvisionTimeline,
  SourceLink,
} from "@/lib/data"
import { formatDate, formatDelta, formatScore } from "@/components/market/format"

type FallbackReference = {
  source: string
  title: string
  note: string
  url: string
}

type FallbackPoint = {
  date: string | null
  value: number | null
}

export function PolicyTrend({
  timelines,
  policies,
  provision,
  events = [],
  evidenceItems = [],
  sourceLinks = [],
  fallbackReferences = [],
  fallbackPoint = null,
}: {
  timelines: ProvisionTimeline[]
  policies: CurrentPci[]
  provision?: string
  events?: PolicyEvent[]
  evidenceItems?: EvidenceItem[]
  sourceLinks?: SourceLink[]
  fallbackReferences?: FallbackReference[]
  fallbackPoint?: FallbackPoint | null
}) {
  const points = useMemo(
    () => buildPoints(timelines, policies, provision, events, evidenceItems, sourceLinks, fallbackPoint),
    [timelines, policies, provision, events, evidenceItems, sourceLinks, fallbackPoint],
  )
  const [activeKey, setActiveKey] = useState<string | null>(null)
  const path = buildPath(points)
  const latest = points.at(-1)
  const first = points[0]
  const active = points.find((point) => point.key === activeKey) ?? latest ?? first

  return (
    <section className="trend-panel policy-trajectory-panel" aria-label="Policy credibility trend">
      <div className="trend-panel-head">
        <div>
          <p>Score trend</p>
          <h2>{provision ? `${provision} PCI trend` : "Policy score movement"}</h2>
        </div>
        <div className="trend-score">
          <span>{latest ? formatScore(latest.value) : "-"}</span>
          <small>{latest ? formatDate(latest.date) : "Baseline"}</small>
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
          <circle
            key={point.key}
            data-testid={`trend-point-${point.key}`}
            tabIndex={0}
            cx={point.x}
            cy={point.y}
            r={point.events.length ? "5" : "4"}
            className={`trend-dot trend-dot-control${active?.key === point.key ? " active" : ""}${point.events.length ? " attributed" : ""}`}
            aria-label={`${formatDate(point.date)} index ${formatScore(point.value)}`}
            onFocus={() => setActiveKey(point.key)}
            onMouseEnter={() => setActiveKey(point.key)}
          >
            <title>{pointTooltip(point)}</title>
          </circle>
        ))}
        <text x="34" y="172" className="trend-axis">
          {first ? formatDate(first.date) : ""}
        </text>
        <text x="620" y="172" textAnchor="end" className="trend-axis">
          {latest ? formatDate(latest.date) : ""}
        </text>
      </svg>
      {active && (
        <TrendAttributionPanel
          point={active}
          fallbackReferences={fallbackReferences}
        />
      )}
    </section>
  )
}

type Point = {
  key: string
  date: string
  value: number
  x: number
  y: number
  events: PolicyEvent[]
  evidence: EvidenceItem[]
}

function buildPoints(
  timelines: ProvisionTimeline[],
  policies: CurrentPci[],
  provision?: string,
  events: PolicyEvent[] = [],
  evidenceItems: EvidenceItem[] = [],
  sourceLinks: SourceLink[] = [],
  fallbackPoint: FallbackPoint | null = null,
): Point[] {
  if (provision) {
    const rows = timelines.filter((row) => row.provision === provision)
    if (rows.length) {
      return scalePoints(
        rows.map((row) => {
          const pointEvents = eventsForTimelineRow(row, events)
          return {
            key: `${row.provision}-${row.week}`,
            date: row.week_start,
            value: Number(row.pci),
            events: pointEvents,
            evidence: evidenceForEvents(pointEvents, evidenceItems, sourceLinks),
          }
        }),
      )
    }
  } else {
    const rows = averageTimeline(timelines)
    if (rows.length) {
      return scalePoints(
        rows.map((row) => ({
          key: row.key,
          date: row.week_start,
          value: Number(row.pci),
          events: [],
          evidence: [],
        })),
      )
    }
  }

  if (timelines.length) {
    return scalePoints(
      timelines.map((row) => ({
        key: `${row.provision}-${row.week}`,
        date: row.week_start,
        value: Number(row.pci),
        events: [],
        evidence: [],
      })),
    )
  }

  const current = provision
    ? policies.find((policy) => policy.code === provision)
    : null
  const currentValue = fallbackPoint?.value ?? current?.pci ?? current?.baseline_pci ?? null
  if (currentValue !== null && currentValue !== undefined && Number.isFinite(Number(currentValue))) {
    return scalePoints([
      {
        key: `${provision ?? current?.code ?? "policy"}-current`,
        date: fallbackPoint?.date ?? current?.week_start ?? current?.updated_at ?? "2022-08-16",
        value: Number(currentValue),
        events: [],
        evidence: [],
      },
    ])
  }

  return scalePoints(
    policies.map((policy) => ({
      key: `${policy.code}-${policy.week ?? "current"}`,
      date: policy.week_start ?? policy.updated_at ?? "2022-08-16",
      value: Number(policy.pci ?? policy.baseline_pci),
      events: [],
      evidence: [],
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
      key: row.date,
      week_start: row.date,
      pci: row.values.reduce((sum, value) => sum + value, 0) / row.values.length,
      events: [],
      evidence: [],
    }))
    .sort((a, b) => new Date(a.week_start).getTime() - new Date(b.week_start).getTime())
}

function scalePoints(rows: {
  key: string
  date: string
  value: number
  events: PolicyEvent[]
  evidence: EvidenceItem[]
}[]): Point[] {
  const sorted = rows
    .filter((row) => Number.isFinite(row.value))
    .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
    .slice(-20)

  if (!sorted.length) return []

  const xStep = sorted.length === 1 ? 0 : 586 / (sorted.length - 1)
  return sorted.map((row, index) => ({
    key: row.key,
    date: row.date,
    value: row.value,
    x: 34 + index * xStep,
    y: 158 - ((row.value - 1) / 4) * 132,
    events: row.events,
    evidence: row.evidence,
  }))
}

function buildPath(points: Point[]) {
  if (!points.length) return ""
  return points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ")
}

function eventsForTimelineRow(row: ProvisionTimeline, events: PolicyEvent[]) {
  const ids = new Set(row.source_event_ids)
  const linked = ids.size
    ? events.filter((event) => ids.has(event.event_id))
    : []
  if (linked.length) return linked

  return events.filter(
    (event) =>
      event.provision === row.provision &&
      (event.week === row.week || event.week_start === row.week_start),
  )
}

function evidenceForEvents(
  events: PolicyEvent[],
  evidenceItems: EvidenceItem[],
  sourceLinks: SourceLink[],
) {
  const eventIds = new Set(events.map((event) => event.event_id))
  const evidenceIds = new Set(
    sourceLinks
      .filter((link) => link.target_table === "policy_events" && eventIds.has(link.target_id))
      .map((link) => link.evidence_id),
  )
  return evidenceItems.filter((item) => evidenceIds.has(item.evidence_id))
}

function TrendAttributionPanel({
  point,
  fallbackReferences,
}: {
  point: Point
  fallbackReferences: FallbackReference[]
}) {
  return (
    <div className="trend-attribution-panel" aria-live="polite">
      <div className="trend-attribution-head">
        <div>
          <span>Selected point</span>
          <strong>{formatDate(point.date)}</strong>
        </div>
        <div>
          <span>Index</span>
          <strong>{formatScore(point.value)}</strong>
        </div>
      </div>

      {point.events.length ? (
        <div className="trend-attribution-list">
          {point.events.map((event) => (
            <TrendEvent key={event.event_id} event={event} evidence={point.evidence} />
          ))}
        </div>
      ) : (
        <div className="trend-carried-state">
          <strong>Current scoring state</strong>
          <p>
            This point reflects the latest source set until a scored evidence
            event changes this policy unit.
          </p>
          <div className="trend-reference-list">
            {fallbackReferences.slice(0, 2).map((reference) => (
              <a href={reference.url} key={reference.url}>
                <span>{reference.source}</span>
                <strong>{reference.title}</strong>
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function TrendEvent({
  event,
  evidence,
}: {
  event: PolicyEvent
  evidence: EvidenceItem[]
}) {
  const citations = evidence.filter((item) => item.provision === event.provision).slice(0, 2)
  const body = (
    <>
      <div className="trend-event-head">
        <span>{event.agency ?? event.doc_source ?? "Policy source"}</span>
        <strong>{formatDelta(event.pci_delta)}</strong>
      </div>
      <h3>{event.title ?? "Policy evidence update"}</h3>
      {event.rationale && <p>{event.rationale}</p>}
      {citations.map((citation) => (
        <blockquote key={citation.evidence_id}>
          {citation.citation_quote ?? citation.snippet ?? citation.source_title}
        </blockquote>
      ))}
    </>
  )

  if (event.url) {
    return (
      <a href={event.url} className="trend-event-card">
        {body}
      </a>
    )
  }
  return <div className="trend-event-card">{body}</div>
}

function pointTooltip(point: Point) {
  const event = point.events[0]
  if (!event) return `${formatDate(point.date)}: current scoring state`
  return `${formatDate(point.date)}: ${event.title ?? event.rationale ?? "policy evidence update"}`
}
