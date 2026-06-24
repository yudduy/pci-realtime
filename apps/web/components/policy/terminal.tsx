"use client"

import Link from "next/link"
import { ChevronDown, ChevronLeft, ChevronRight, FileText, Info, Search, X } from "lucide-react"
import { useEffect, useMemo, useRef, useState } from "react"
import { SiteHeader } from "@/components/layout/site-header"
import {
  deltaToneClass,
  formatDelta,
  formatPciValue,
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
  const infoButtonRef = useRef<HTMLButtonElement>(null)
  const infoCloseRef = useRef<HTMLButtonElement>(null)
  const policies = data.policies
  const visible = useMemo(() => filterPolicies(policies, query), [policies, query])
  const [sort, setSort] = useState<TerminalSort>({ key: "code", dir: 1 })
  const [density, setDensity] = useState<"comfortable" | "compact">("comfortable")
  const sorted = useMemo(() => sortPolicies(visible, sort), [visible, sort])
  const onSort = (key: TerminalSortKey) =>
    setSort((current) =>
      current.key === key
        ? { key, dir: (current.dir * -1) as 1 | -1 }
        : { key, dir: key === "code" ? 1 : -1 },
    )
  const [expandedCode, setExpandedCode] = useState<string | null>(null)
  useEffect(() => {
    const hashCode = window.location.hash.match(/^#policy-(.+)$/)?.[1]
    if (hashCode && policies.some((policy) => policy.code === hashCode)) {
      const frame = window.requestAnimationFrame(() => {
        setExpandedCode(hashCode)
        // "start" + scroll-margin-top lands the row just below the sticky header
        // instead of pulling the hero under it.
        document.getElementById(`policy-${hashCode}`)?.scrollIntoView({
          block: "start",
          behavior: "smooth",
        })
      })
      return () => window.cancelAnimationFrame(frame)
    }
  }, [policies])
  // Dialog: trap focus to the close control, close on Escape, restore focus on exit.
  useEffect(() => {
    if (!infoOpen) return
    const trigger = infoButtonRef.current
    infoCloseRef.current?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setInfoOpen(false)
    }
    window.addEventListener("keydown", onKey)
    return () => {
      window.removeEventListener("keydown", onKey)
      trigger?.focus()
    }
  }, [infoOpen])
  return (
    <div className="tracker-page policy-terminal">
      <SiteHeader />

      <main className="terminal-shell">
        <section className="terminal-hero">
          <div>
            <p className="eyebrow">Daily Staff Desk</p>
            <div className="terminal-title-row">
              <h1>Policy Intelligence Desk</h1>
              <div className="terminal-title-actions">
                <button
                  ref={infoButtonRef}
                  type="button"
                  className="terminal-info-button"
                  onClick={() => setInfoOpen(true)}
                  aria-label="About this desk"
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
          <div className="terminal-controls-meta">
            <p>{visible.length} of {policies.length} policies</p>
            <button
              type="button"
              className="density-toggle"
              onClick={() =>
                setDensity((current) => (current === "comfortable" ? "compact" : "comfortable"))
              }
              aria-pressed={density === "compact"}
            >
              {density === "compact" ? "Comfortable" : "Compact"}
            </button>
          </div>
        </section>

        <section className="terminal-main">
          <div className="terminal-table-wrap policy-accordion-shell">
            <PolicyScoreGuide />
            {density === "compact" ? (
              <PolicyCompareTable policies={sorted} sort={sort} onSort={onSort} />
            ) : (
              <>
                <RegisterHeader sort={sort} onSort={onSort} />
                <PolicyAccordion
                  policies={sorted}
                  expandedCode={expandedCode}
                  onToggle={(code) =>
                    setExpandedCode((current) => (current === code ? null : code))
                  }
                />
              </>
            )}
          </div>
        </section>

        {infoOpen && (
          <div
            className="terminal-info-overlay"
            role="presentation"
            onClick={() => setInfoOpen(false)}
          >
            <div
              className="terminal-info-modal"
              role="dialog"
              aria-modal="true"
              aria-labelledby="terminal-info-title"
              onClick={(event) => event.stopPropagation()}
            >
              <button
                ref={infoCloseRef}
                type="button"
                className="terminal-info-close"
                onClick={() => setInfoOpen(false)}
                aria-label="Close terminal information"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
              <p className="eyebrow">How to read this</p>
              <h2 id="terminal-info-title">How the desk treats evidence</h2>
              <p>
                Staff briefs come first. The derived PCI signal runs from 1 to 5
                and only moves when reviewed primary evidence changes specificity,
                durability, or enforceability.
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
  const [paused, setPaused] = useState(false)
  useEffect(() => {
    if (updates.length <= 1 || paused) return
    const reduceMotion = window.matchMedia?.(
      "(prefers-reduced-motion: reduce)",
    ).matches
    if (reduceMotion) return
    const timer = window.setInterval(() => {
      setActive((value) => (value + 1) % updates.length)
    }, 5200)
    return () => window.clearInterval(timer)
  }, [updates.length, paused])

  if (!updates.length) return null

  const current = updates[active] ?? updates[0]
  const previous = () => setActive((value) => (value === 0 ? updates.length - 1 : value - 1))
  const next = () => setActive((value) => (value + 1) % updates.length)

  return (
    <section
      className="terminal-updates-carousel"
      aria-label="Latest policy updates"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocusCapture={() => setPaused(true)}
      onBlurCapture={() => setPaused(false)}
    >
      <div className="terminal-updates-head">
        <div>
          <p>Latest staff updates</p>
          <h2>Reviewed evidence for decisions</h2>
        </div>
        <div className="terminal-carousel-controls" aria-label="Update carousel controls">
          <button
            type="button"
            onClick={previous}
            disabled={updates.length <= 1}
            aria-label="Previous staff update"
          >
            <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          </button>
          {updates.length > 1 && (
            <span>
              {active + 1} / {updates.length}
            </span>
          )}
          <button
            type="button"
            onClick={next}
            disabled={updates.length <= 1}
            aria-label="Next staff update"
          >
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
            Open cited source
          </a>
        </div>
      </article>

      {updates.length > 1 && (
        <div className="terminal-update-dots" aria-label="Select staff update">
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
      )}
    </section>
  )
}

function PolicyScoreGuide() {
  return (
    <div className="policy-score-guide" aria-label="Policy desk register">
      <div>
        <p>Reviewed desk</p>
        <h2>Policy brief register</h2>
      </div>
    </div>
  )
}

type TerminalSortKey = "code" | "pci" | "move"
type TerminalSort = { key: TerminalSortKey; dir: 1 | -1 }

function sortPolicies(policies: TerminalPolicy[], sort: TerminalSort): TerminalPolicy[] {
  const arr = [...policies]
  arr.sort((a, b) => {
    if (sort.key === "code") return a.code.localeCompare(b.code) * sort.dir
    if (sort.key === "pci") return ((a.currentPci ?? 0) - (b.currentPci ?? 0)) * sort.dir
    return ((policyDelta(a) ?? 0) - (policyDelta(b) ?? 0)) * sort.dir
  })
  return arr
}

function RegisterHeader({
  sort,
  onSort,
}: {
  sort: TerminalSort
  onSort: (key: TerminalSortKey) => void
}) {
  const indicator = (key: TerminalSortKey) =>
    sort.key === key ? (sort.dir === 1 ? " ↑" : " ↓") : ""
  const sortButton = (label: string, sortKey: TerminalSortKey) => (
    <button
      type="button"
      className={`register-sort${sort.key === sortKey ? " active" : ""}`}
      onClick={() => onSort(sortKey)}
      aria-pressed={sort.key === sortKey}
      aria-label={`Sort by ${label.toLowerCase()}`}
    >
      {label}
      {indicator(sortKey)}
    </button>
  )
  return (
    <div className="policy-register-head" role="row">
      {sortButton("Policy", "code")}
      <span className="register-spacer" aria-hidden="true" />
      <div className="register-dims-head" aria-hidden="true">
        <span>Spec</span>
        <span>Dur</span>
        <span>Enf</span>
      </div>
      <span className="register-col-label register-trend-label">Trend</span>
      <div className="register-sort-cluster">
        {sortButton("Derived PCI", "pci")}
        {sortButton("Latest move", "move")}
      </div>
      <span aria-hidden="true" />
    </div>
  )
}

// Dense comparison table (Compact mode): every policy's dimensions are
// column-scannable head-to-head without expanding. The accordion (Comfortable)
// stays for single-policy depth.
function PolicyCompareTable({
  policies,
  sort,
  onSort,
}: {
  policies: TerminalPolicy[]
  sort: TerminalSort
  onSort: (key: TerminalSortKey) => void
}) {
  const indicator = (key: TerminalSortKey) =>
    sort.key === key ? (sort.dir === 1 ? " ↑" : " ↓") : ""
  const ariaSort = (key: TerminalSortKey): "ascending" | "descending" | "none" =>
    sort.key === key ? (sort.dir === 1 ? "ascending" : "descending") : "none"
  const headButton = (label: string, key: TerminalSortKey) => (
    <button
      type="button"
      className={`compare-sort${sort.key === key ? " active" : ""}`}
      onClick={() => onSort(key)}
      aria-label={`Sort by ${label.toLowerCase()}`}
    >
      {label}
      {indicator(key)}
    </button>
  )
  return (
    <div className="policy-compare-wrap">
      <table className="policy-compare-table">
        <thead>
          <tr>
            <th scope="col" aria-sort={ariaSort("code")}>{headButton("Policy", "code")}</th>
            <th scope="col" className="num">Spec</th>
            <th scope="col" className="num">Dur</th>
            <th scope="col" className="num">Enf</th>
            <th scope="col" className="num" aria-sort={ariaSort("pci")}>
              {headButton("Derived PCI", "pci")}
            </th>
            <th scope="col" className="num" aria-sort={ariaSort("move")}>
              {headButton("Move", "move")}
            </th>
            <th scope="col" className="spark-col">Trend</th>
          </tr>
        </thead>
        <tbody>
          {policies.map((policy) => {
            const delta = policyDelta(policy)
            return (
              <tr key={policy.code}>
                <th scope="row" className="compare-policy">
                  <Link href={`/#policy-${policy.code}`}>
                    <strong>{policy.code}</strong>
                    <span>{policy.name}</span>
                  </Link>
                </th>
                <td className="num">{formatScore(policy.specificity)}</td>
                <td className="num">{formatScore(policy.durability)}</td>
                <td className="num">{formatScore(policy.enforceability)}</td>
                <td className="num compare-pci">{formatPciValue(policy.currentPci)}</td>
                <td className="num">
                  <span className={deltaToneClass(delta)}>{formatDelta(delta)}</span>
                </td>
                <td className="spark-col">
                  <RowSpark timeline={policy.timeline} />
                </td>
              </tr>
            )
          })}
          {!policies.length && (
            <tr>
              <td colSpan={7} className="compare-empty">
                No matching policy. Clear search to restore the register.
              </td>
            </tr>
          )}
        </tbody>
      </table>
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
              <span className="register-spacer" aria-hidden="true" />
              <span
                className="policy-row-dims"
                aria-label={`Specificity ${formatScore(policy.specificity)}, durability ${formatScore(policy.durability)}, enforceability ${formatScore(policy.enforceability)} out of 5`}
              >
                <RowDim value={policy.specificity} />
                <RowDim value={policy.durability} />
                <RowDim value={policy.enforceability} />
              </span>
              <RowSpark timeline={policy.timeline} />
              <span className="policy-score-cluster">
                <strong>{formatPciValue(policy.currentPci)}</strong>
                <span className={deltaToneClass(delta)}>{formatDelta(delta)}</span>
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

// A dimension as value + 5-segment micro-gauge, so a column scan across the six
// policies surfaces which provision is weak on a dimension (the same gauge the
// dossier uses, kept in sync for cross-surface consistency).
function RowDim({ value }: { value: number | null }) {
  const filled = value && Number.isFinite(value) ? Math.round(value) : 0
  return (
    <span className="policy-row-dim">
      <span className="policy-row-dim-value">{formatScore(value)}</span>
      <span className="policy-row-dim-gauge" aria-hidden="true">
        {[1, 2, 3, 4, 5].map((step) => (
          <span key={step} className={step <= filled ? "on" : ""} />
        ))}
      </span>
    </span>
  )
}

function RowSpark({ timeline }: { timeline: TerminalPolicyPoint[] }) {
  const points = useMemo(() => {
    const sorted = timeline
      .filter((point) => typeof point.value === "number" && Number.isFinite(point.value))
      .sort((a, b) => dateValue(a.date) - dateValue(b.date))
      .slice(-12)
    const values = sorted.map((point) => Number(point.value))
    const distinct = new Set(values).size
    if (sorted.length < 2 || distinct < 2) return null
    const width = 72
    const height = 26
    const pad = 4
    const step = (width - pad * 2) / (sorted.length - 1)
    // Local min/max scaling so a small move is legible (the big expanded chart
    // keeps the fixed 1–5 domain for cross-policy comparison).
    const min = Math.min(...values)
    const max = Math.max(...values)
    const range = max - min || 1
    return values.map((value, index) => ({
      x: pad + index * step,
      y: height - pad - ((value - min) / range) * (height - pad * 2),
    }))
  }, [timeline])

  // No movement yet — a flat spark would imply a measured trend that isn't there.
  if (!points) return <span className="row-spark-empty" aria-hidden="true">—</span>

  // Neutral stroke: direction/sign is already carried by the coloured delta in
  // the same row, so the spark only needs to show the shape of the trajectory.
  // A faint baseline at the starting value anchors the slope positionally.
  const path = points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`)
    .join(" ")
  const last = points[points.length - 1]
  const baseY = points[0].y.toFixed(1)
  return (
    <svg className="row-spark" viewBox="0 0 72 26" width="72" height="26" aria-hidden="true">
      <line className="row-spark-base" x1="4" x2="68" y1={baseY} y2={baseY} />
      <path d={path} />
      <circle cx={last.x} cy={last.y} r="2.4" />
    </svg>
  )
}

function PolicyScoreTrend({ policy }: { policy: TerminalPolicy }) {
  const { points, domain } = useMemo(
    () => largeTrendSeries(policy.timeline),
    [policy.timeline],
  )
  const distinctValues = useMemo(
    () => new Set(points.map((point) => point.value)).size,
    [points],
  )
  const [activeKey, setActiveKey] = useState<string | null>(null)
  const active = points.find((point) => point.key === activeKey) ?? points.at(-1)

  // A line is only honest with >=3 points that actually move. Otherwise the index
  // is holding at its baseline — label that state rather than draw a flat segment.
  const hasTrend = points.length >= 3 && distinctValues > 1

  if (!hasTrend) {
    const baseline = points[0]
    const latest = points.at(-1) ?? baseline
    return (
      <section className="policy-score-trend" aria-label={`${policy.code} derived PCI signal`}>
        <div className="trend-baseline">
          <div>
            <span>Derived PCI</span>
            <strong>{formatScore(policy.currentPci)}</strong>
          </div>
          <p>
            No staff-relevant evidence movement since the {formatPolicyDate(baseline?.date)}
            baseline. The derived signal moves only after reviewed primary evidence.
          </p>
        </div>
        {latest && <PointAttribution point={latest} policy={policy} />}
      </section>
    )
  }

  const dense = points.length >= 10
  const path = points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`)
    .join(" ")
  // Close the line down to the baseline for a faint area fill (depth without ink).
  const area =
    points.length >= 2
      ? `${path} L ${points.at(-1)!.x} 140 L ${points[0].x} 140 Z`
      : ""
  // Adaptive, labeled y-axis: the line uses the vertical space (a 0.3 move is
  // visible) while the printed bounds keep it honest about absolute level.
  const fmtAxis = (value: number) =>
    Number.isInteger(value) ? String(value) : value.toFixed(1)

  return (
    <section className="policy-score-trend" aria-label={`${policy.code} derived PCI signal trend`}>
      <svg viewBox="0 0 720 168" role="img" aria-label={`${policy.code} derived PCI chart`}>
        <rect className="trend-band" x="44" y="20" width="656" height="120" rx="4" />
        <line x1="44" x2="700" y1="20" y2="20" />
        <line x1="44" x2="700" y1="80" y2="80" />
        <line x1="44" x2="700" y1="140" y2="140" />
        <text className="trend-axis" x="34" y="24" textAnchor="end">{fmtAxis(domain.hi)}</text>
        <text className="trend-axis" x="34" y="84" textAnchor="end">
          {fmtAxis((domain.lo + domain.hi) / 2)}
        </text>
        <text className="trend-axis" x="34" y="144" textAnchor="end">{fmtAxis(domain.lo)}</text>
        {area && <path className="trend-area" d={area} />}
        {path && <path d={path} />}
        {points.map((point, index) => {
          const endpoint = index === 0 || index === points.length - 1
          if (
            dense &&
            !endpoint &&
            active?.key !== point.key &&
            !point.attributions.length
          ) {
            return null
          }
          return (
            <circle
              key={point.key}
              data-testid={`terminal-trend-point-${point.key}`}
              tabIndex={0}
              cx={point.x}
              cy={point.y}
              r={point.attributions.length ? "5" : "4"}
              className={active?.key === point.key ? "active" : ""}
              aria-label={`${formatPolicyDate(point.date)} derived PCI ${formatScore(point.value)}`}
              onFocus={() => setActiveKey(point.key)}
              onMouseEnter={() => setActiveKey(point.key)}
            >
              <title>{`${formatPolicyDate(point.date)} derived PCI ${formatScore(point.value)}`}</title>
            </circle>
          )
        })}
        <text x="44" y="160">
          {points[0] ? formatPolicyDate(points[0].date) : ""}
        </text>
        <text x="700" y="160" textAnchor="end">
          {points.at(-1) ? formatPolicyDate(points.at(-1)?.date) : ""}
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

// Adaptive y-domain (rounded to 0.5, clamped to the valid 1–5 PCI range) padded
// around the data so the trajectory uses the vertical space instead of hugging
// the top of a fixed 1–5 axis. The printed bounds keep the chart honest.
function trendDomain(values: number[]): { lo: number; hi: number } {
  if (!values.length) return { lo: 1, hi: 5 }
  let lo = Math.min(...values)
  let hi = Math.max(...values)
  const pad = Math.max(0.5, (hi - lo) * 0.6)
  lo = Math.max(1, Math.floor((lo - pad) * 2) / 2)
  hi = Math.min(5, Math.ceil((hi + pad) * 2) / 2)
  if (hi - lo < 1) {
    const mid = (hi + lo) / 2
    lo = Math.max(1, Math.min(mid - 0.5, 4))
    hi = Math.min(5, lo + 1)
  }
  return { lo, hi }
}

function largeTrendSeries(points: TerminalPolicyPoint[]): {
  points: LargeTrendPoint[]
  domain: { lo: number; hi: number }
} {
  const sorted = points
    .filter((point) => typeof point.value === "number" && Number.isFinite(point.value))
    .sort((a, b) => dateValue(a.date) - dateValue(b.date))
    .slice(-24)

  if (!sorted.length) return { points: [], domain: { lo: 1, hi: 5 } }
  const xStep = sorted.length === 1 ? 0 : 656 / (sorted.length - 1)
  const domain = trendDomain(sorted.map((point) => Number(point.value)))
  const span = domain.hi - domain.lo || 1

  // The plot band y∈[20,140] maps the adaptive domain; x starts at 44 to clear
  // the y-axis labels.
  const mapped = sorted.map((point, index) => ({
    ...point,
    date: point.date ?? "2022-08-16",
    value: Number(point.value),
    x: 44 + index * xStep,
    y: 140 - ((Number(point.value) - domain.lo) / span) * 120,
  }))
  return { points: mapped, domain }
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
        <span>{formatPolicyDate(point.date)}</span>
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
    <section className="policy-score-breakdown" aria-label={`${policy.code} derived PCI inputs`}>
      <h3>Derived Index Inputs</h3>
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
  if (!value) return "--"
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(value))
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
