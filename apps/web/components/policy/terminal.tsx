"use client"

import Link from "next/link"
import { ChevronDown, ChevronLeft, ChevronRight, FileText, Info, Search, X } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { SiteHeader } from "@/components/layout/site-header"
import {
  deltaToneClass,
  formatDate,
  formatDelta,
  formatScore,
} from "@/components/market/format"
import type { PolicyHeadline } from "@/lib/headlines"
import type { PolicySourceReference } from "@/lib/policy-copy"

export type TerminalPolicy = {
  code: string
  name: string
  formalName: string
  lane: string
  question: string
  currentPci: number | null
  scoreDelta: number | null
  specificity: number | null
  durability: number | null
  enforceability: number | null
  updatedAt: string | null
  latestEvidenceAt: string | null
  latestEvidenceTitle: string | null
  latestEvidenceSource: string | null
  evidenceAnchorCount: number
  attributionDrivers: string[]
  sourceReferences: PolicySourceReference[]
  latestRefreshAt: string | null
  timeline: TerminalPolicyPoint[]
}

type TerminalPolicyPoint = {
  key: string
  date: string | null
  value: number | null
  delta: number | null
  attributions: TerminalPointAttribution[]
}

type TerminalPointAttribution = {
  source: string
  title: string
  rationale: string | null
  url: string | null
  delta: number
  quotes: string[]
}

export type PolicyTerminalData = {
  policies: TerminalPolicy[]
  connected: boolean
  viewErrors: string[]
  lastSourceRefresh: string | null
  recentUpdates: PolicyHeadline[]
}

export function PolicyTerminal({ data }: { data: PolicyTerminalData }) {
  const [query, setQuery] = useState("")
  const [infoOpen, setInfoOpen] = useState(false)
  const policies = data.policies
  const visible = useMemo(() => filterPolicies(policies, query), [policies, query])
  const [expandedCode, setExpandedCode] = useState<string | null>(null)
  useEffect(() => {
    const hashCode = window.location.hash.match(/^#policy-(.+)$/)?.[1]
    if (hashCode && policies.some((policy) => policy.code === hashCode)) {
      const frame = window.requestAnimationFrame(() => {
        setExpandedCode(hashCode)
        document.getElementById(`policy-${hashCode}`)?.scrollIntoView({
          block: "center",
          behavior: "smooth",
        })
      })
      return () => window.cancelAnimationFrame(frame)
    }
  }, [policies])
  return (
    <div className="tracker-page policy-terminal">
      <SiteHeader />

      <main className="terminal-shell">
        <section className="terminal-hero">
          <div>
            <p className="eyebrow">Policy Intelligence Ledger</p>
            <div className="terminal-title-row">
              <h1>Climate policy intelligence</h1>
              <div className="terminal-title-actions">
                <button
                  type="button"
                  className="terminal-info-button"
                  onClick={() => setInfoOpen(true)}
                  aria-label="About this terminal"
                >
                  <Info className="h-4 w-4" aria-hidden="true" />
                </button>
                <Link
                  href="/about"
                  className="terminal-info-button"
                  aria-label="Read about the paper"
                  title="Read about the paper"
                >
                  <FileText className="h-4 w-4" aria-hidden="true" />
                </Link>
              </div>
            </div>
          </div>
        </section>

        <UpdateCarousel updates={data.recentUpdates} />

        <section className="terminal-controls">
          <label className="tracker-search">
            <Search className="h-4 w-4" aria-hidden="true" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search policy, agency, or document"
            />
          </label>
          <p>{visible.length} of {policies.length} policies</p>
        </section>

        <section className="terminal-main">
          <div className="terminal-table-wrap policy-accordion-shell">
            <PolicyScoreGuide />
            <PolicyAccordion
              policies={visible}
              expandedCode={expandedCode}
              onToggle={(code) =>
                setExpandedCode((current) => (current === code ? null : code))
              }
            />
          </div>
        </section>

        {infoOpen && (
          <div className="terminal-info-overlay" role="presentation">
            <div
              className="terminal-info-modal"
              role="dialog"
              aria-modal="true"
              aria-labelledby="terminal-info-title"
            >
              <button
                type="button"
                className="terminal-info-close"
                onClick={() => setInfoOpen(false)}
                aria-label="Close terminal information"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
              <p className="eyebrow">How to read this</p>
              <h2 id="terminal-info-title">How to read policy scores</h2>
              <p>
                Scores run from 1 to 5. Higher means the policy signal is more
                specific, durable, and enforceable. Movement shows the latest
                change: green improves, red weakens, and -- means no measured move.
              </p>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

function UpdateCarousel({
  updates,
}: {
  updates: PolicyHeadline[]
}) {
  const [active, setActive] = useState(0)
  useEffect(() => {
    if (updates.length <= 1) return
    const timer = window.setInterval(() => {
      setActive((value) => (value + 1) % updates.length)
    }, 5200)
    return () => window.clearInterval(timer)
  }, [updates.length])

  if (!updates.length) return null

  const current = updates[active] ?? updates[0]
  const previous = () => setActive((value) => (value === 0 ? updates.length - 1 : value - 1))
  const next = () => setActive((value) => (value + 1) % updates.length)

  return (
    <section className="terminal-updates-carousel" aria-label="Latest policy updates">
      <div className="terminal-updates-head">
        <div>
          <p>Latest policy updates</p>
          <h2>Evidence moving the index</h2>
        </div>
        <div className="terminal-carousel-controls" aria-label="Update carousel controls">
          <button type="button" onClick={previous} aria-label="Previous PCI update">
            <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          </button>
          <span>
            {active + 1} / {updates.length}
          </span>
          <button type="button" onClick={next} aria-label="Next PCI update">
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      </div>

      <article className="terminal-update-card" key={current.id} aria-live="polite">
        <div className="terminal-update-meta">
          <span className="policy-code">{current.code}</span>
          <span>{current.source}</span>
          <span>{formatPolicyDate(current.date)}</span>
        </div>
        <h3>{current.title}</h3>
        <div className="terminal-update-foot">
          <span>{current.policyName ?? "Tracked policy"}</span>
          <strong className={deltaToneClass(current.delta)}>
            {formatDelta(current.delta)}
          </strong>
          <a href={current.href} target="_blank" rel="noreferrer">
            View source
          </a>
        </div>
      </article>

      <div className="terminal-update-dots" aria-label="Select PCI update">
        {updates.map((update, index) => (
          <button
            key={update.id}
            type="button"
            className={index === active ? "active" : ""}
            onClick={() => setActive(index)}
            aria-label={`Show update for ${update.code}`}
            aria-pressed={index === active}
          />
        ))}
      </div>
    </section>
  )
}

function PolicyScoreGuide() {
  return (
    <div className="policy-score-guide" aria-label="How to read policy scores">
      <div>
        <p>Policy register</p>
        <h2>Tracked policies</h2>
      </div>
    </div>
  )
}

function PolicyAccordion({
  policies,
  expandedCode,
  onToggle,
}: {
  policies: TerminalPolicy[]
  expandedCode: string | null
  onToggle: (code: string) => void
}) {
  return (
    <div className="policy-accordion-list">
      {policies.map((policy) => {
        const expanded = policy.code === expandedCode
        const delta = policyDelta(policy)
        return (
          <article
            key={policy.code}
            id={`policy-${policy.code}`}
            className={`policy-accordion-item${expanded ? " expanded" : ""}`}
          >
            <button
              type="button"
              className="policy-accordion-trigger"
              aria-expanded={expanded}
              aria-controls={`policy-panel-${policy.code}`}
              onClick={() => onToggle(policy.code)}
            >
              <span className="policy-accordion-title">
                <strong>{policy.code}</strong>
                <span className="policy-accordion-name">{policy.name}</span>
                <span className="policy-accordion-context">
                  {policy.latestEvidenceSource ?? policy.lane}
                  {policy.latestEvidenceAt ? ` / ${formatPolicyDate(policy.latestEvidenceAt)}` : ""}
                </span>
              </span>
              <span className="policy-score-cluster">
                <span className="policy-score-label">Score</span>
                <strong>{formatScore(policy.currentPci)}</strong>
                <span className={deltaToneClass(delta)}>
                  <span className="policy-score-label">Move</span>
                  {formatDelta(delta)}
                </span>
              </span>
              <ChevronDown className="policy-accordion-icon h-4 w-4" aria-hidden="true" />
            </button>

            <div
              id={`policy-panel-${policy.code}`}
              className="policy-accordion-panel"
              aria-hidden={!expanded}
            >
              <div className="policy-accordion-body">
                {expanded && (
                  <>
                    <PolicyScoreTrend policy={policy} />
                    <div className="policy-score-support">
                      <ScoreBreakdown policy={policy} />
                    </div>
                  </>
                )}
              </div>
            </div>
          </article>
        )
      })}
      {!policies.length && (
        <div className="market-empty">No matching policy. Clear search to restore the register.</div>
      )}
    </div>
  )
}

function PolicyScoreTrend({ policy }: { policy: TerminalPolicy }) {
  const points = useMemo(() => largeTrendPoints(policy.timeline), [policy.timeline])
  const [activeKey, setActiveKey] = useState<string | null>(null)
  const active = points.find((point) => point.key === activeKey) ?? points.at(-1)
  const path = points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`)
    .join(" ")

  if (points.length <= 1) {
    return (
      <section className="policy-score-trend" aria-label={`${policy.code} PCI score trend`}>
        {points[0] && <PointAttribution point={points[0]} policy={policy} />}
      </section>
    )
  }

  return (
    <section className="policy-score-trend" aria-label={`${policy.code} PCI score trend`}>
      <svg viewBox="0 0 720 220" role="img" aria-label={`${policy.code} PCI score chart`}>
        <line x1="24" x2="696" y1="38" y2="38" />
        <line x1="24" x2="696" y1="110" y2="110" />
        <line x1="24" x2="696" y1="182" y2="182" />
        {path && <path d={path} />}
        {points.map((point) => (
          <circle
            key={point.key}
            data-testid={`terminal-trend-point-${point.key}`}
            tabIndex={0}
            cx={point.x}
            cy={point.y}
            r={point.attributions.length ? "5" : "4"}
            className={active?.key === point.key ? "active" : ""}
            aria-label={`${formatDate(point.date)} score ${formatScore(point.value)}`}
            onFocus={() => setActiveKey(point.key)}
            onMouseEnter={() => setActiveKey(point.key)}
          >
            <title>{`${formatDate(point.date)} score ${formatScore(point.value)}`}</title>
          </circle>
        ))}
        <text x="24" y="208">
          {points[0] ? formatDate(points[0].date) : ""}
        </text>
        <text x="696" y="208" textAnchor="end">
          {points.at(-1) ? formatDate(points.at(-1)?.date) : ""}
        </text>
      </svg>

      {active && <PointAttribution point={active} policy={policy} />}
    </section>
  )
}

type LargeTrendPoint = TerminalPolicyPoint & {
  x: number
  y: number
  value: number
  date: string
}

function largeTrendPoints(points: TerminalPolicyPoint[]): LargeTrendPoint[] {
  const sorted = points
    .filter((point) => typeof point.value === "number" && Number.isFinite(point.value))
    .sort((a, b) => dateValue(a.date) - dateValue(b.date))
    .slice(-24)

  if (!sorted.length) return []
  const values = sorted.map((point) => Number(point.value))
  const min = Math.min(...values, 1)
  const max = Math.max(...values, 5)
  const range = max - min || 1
  const xStep = sorted.length === 1 ? 0 : 672 / (sorted.length - 1)

  return sorted.map((point, index) => ({
    ...point,
    date: point.date ?? "2022-08-16",
    value: Number(point.value),
    x: 24 + index * xStep,
    y: 190 - ((Number(point.value) - min) / range) * 160,
  }))
}

function PointAttribution({
  point,
  policy,
}: {
  point: LargeTrendPoint
  policy: TerminalPolicy
}) {
  return (
    <div className="policy-point-attribution">
      <div className="policy-point-meta">
        <span>{formatDate(point.date)}</span>
        <em className={deltaToneClass(point.delta)}>{formatDelta(point.delta)}</em>
      </div>

      {point.attributions.length ? (
        <div className="policy-source-stack">
          {point.attributions.map((source) => (
            <a
              key={`${source.title}-${source.source}`}
              href={source.url ?? undefined}
              className="policy-source-card"
            >
              <strong>{source.title}</strong>
              {source.quotes.slice(0, 1).map((quote) => (
                <blockquote key={quote}>{quote}</blockquote>
              ))}
            </a>
          ))}
        </div>
      ) : (
        <FallbackAttribution policy={policy} />
      )}
    </div>
  )
}

function FallbackAttribution({ policy }: { policy: TerminalPolicy }) {
  return (
    <div className="policy-source-stack">
      {policy.sourceReferences.slice(0, 2).map((reference) => (
        <a href={reference.url} key={reference.url} className="policy-source-card">
          <strong>{reference.title}</strong>
          <p>{reference.note}</p>
        </a>
      ))}
    </div>
  )
}

function ScoreBreakdown({ policy }: { policy: TerminalPolicy }) {
  return (
    <section className="policy-score-breakdown" aria-label={`${policy.code} score breakdown`}>
      <h3>Scoring</h3>
      <ScorePart label="Specificity" value={policy.specificity} />
      <ScorePart label="Durability" value={policy.durability} />
      <ScorePart label="Enforceability" value={policy.enforceability} />
    </section>
  )
}

function ScorePart({
  label,
  value,
}: {
  label: string
  value: number | null
}) {
  const width = `${Math.max(0, Math.min(100, ((value ?? 0) / 5) * 100))}%`
  return (
    <div className="policy-score-part">
      <div>
        <span>{label}</span>
        <strong>{formatScore(value)}</strong>
      </div>
      <div className="policy-score-bar">
        <span style={{ width }} />
      </div>
    </div>
  )
}

function filterPolicies(policies: TerminalPolicy[], query: string) {
  const normalized = query.trim().toLowerCase()
  if (!normalized) return policies
  return policies.filter((policy) =>
    [
      policy.code,
      policy.name,
      policy.formalName,
      policy.lane,
      policy.latestEvidenceSource,
      policy.latestEvidenceTitle,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase()
      .includes(normalized),
  )
}

function formatPolicyDate(value: string | null | undefined) {
  const formatted = formatDate(value)
  return formatted === "-" ? "--" : formatted
}

function policyDelta(policy: TerminalPolicy) {
  const values = policy.timeline
    .filter((point) => typeof point.value === "number" && Number.isFinite(point.value))
    .sort((a, b) => dateValue(a.date) - dateValue(b.date))
    .map((point) => Number(point.value))
  if (values.length >= 2) {
    return values.at(-1)! - values.at(-2)!
  }
  return policy.scoreDelta
}

function dateValue(value: string | null | undefined) {
  if (!value) return 0
  const date = new Date(value).getTime()
  return Number.isNaN(date) ? 0 : date
}
