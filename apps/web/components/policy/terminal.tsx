"use client"

import Link from "next/link"
import { Search } from "lucide-react"
import { useMemo, useState } from "react"
import { SiteHeader } from "@/components/layout/site-header"
import { SourceHealthStrip } from "@/components/market/source-health"
import {
  deltaToneClass,
  formatDate,
  formatDateTime,
  formatDelta,
  formatScore,
} from "@/components/market/format"
import type { SourceHealth } from "@/lib/data"

type TerminalPolicy = {
  code: string
  name: string
  formalName: string
  lane: string
  question: string
  currentPci: number | null
  weeklyDelta: number | null
  specificity: number | null
  durability: number | null
  enforceability: number | null
  updatedAt: string | null
  latestEvidenceAt: string | null
  latestEvidenceTitle: string | null
  latestEvidenceSource: string | null
  evidenceAnchorCount: number
  eventCount: number
  attributionDrivers: string[]
  latestRefreshAt: string | null
}

type PolicyTerminalData = {
  policies: TerminalPolicy[]
  sourceHealth: SourceHealth[]
  connected: boolean
  viewErrors: string[]
  sourceMapCount: number
  evidenceAnchors: number
  averagePci: number | null
  lastSourceRefresh: string | null
  policyEventCount: number
}

export function PolicyTerminal({ data }: { data: PolicyTerminalData }) {
  const [query, setQuery] = useState("")
  const policies = data.policies
  const visible = useMemo(() => filterPolicies(policies, query), [policies, query])
  const [selectedCode, setSelectedCode] = useState<string | null>(null)
  const selected =
    visible.find((policy) => policy.code === selectedCode) ??
    visible[0] ??
    policies[0]
  const registryState = formatRegistryState(data.lastSourceRefresh)

  return (
    <div className="tracker-page policy-terminal">
      <SiteHeader />

      <main className="terminal-shell">
        <section className="terminal-hero">
          <div>
            <p className="eyebrow">Policy Intelligence</p>
            <h1>Climate policy intelligence terminal</h1>
            <p>
              PCIndex continuously parses official policy sources, normalizes
              evidence by policy unit, and turns the stream into credibility,
              trajectory, and attribution.
            </p>
          </div>
          <div className="terminal-status">
            <span className={data.connected && !data.viewErrors.length ? "status-live" : "status-muted"}>
              Registry state
            </span>
            <span>{registryState}</span>
          </div>
        </section>

        <section className="terminal-tape" aria-label="Terminal state">
          <TapeItem label="Registry state" value={registryState} />
          <TapeItem label="Source coverage" value={`${data.sourceMapCount} feeds`} />
          <TapeItem label="Tracked policies" value={String(policies.length)} />
          <TapeItem label="Cited evidence" value={String(data.evidenceAnchors)} />
          <TapeItem label="Weekly moves" value={String(data.policyEventCount)} />
        </section>

        <section className="terminal-kpis" aria-label="Registry summary">
          <Kpi label="Avg PCI" value={formatScore(data.averagePci)} />
          <Kpi label="Tracked policies" value={String(policies.length)} />
          <Kpi label="Source coverage" value={String(data.sourceMapCount)} />
          <Kpi label="Cited evidence" value={String(data.evidenceAnchors)} />
          <Kpi label="Score dimensions" value="3" />
        </section>

        <SourceHealthStrip sources={data.sourceHealth} />

        <section className="terminal-controls">
          <label className="tracker-search">
            <Search className="h-4 w-4" aria-hidden="true" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search policy, agency, or document"
            />
          </label>
          <p>
            {visible.length} of {policies.length} policy units shown
          </p>
        </section>

        <section className="terminal-main">
          <div className="terminal-table-wrap">
            <div className="section-heading">
              <p>Policy Register</p>
              <h2>Current credibility state</h2>
            </div>
            <PolicyTable
              policies={visible}
              selectedCode={selected?.code ?? null}
              onSelect={setSelectedCode}
            />
          </div>
          <PolicyPreview policy={selected} />
        </section>

      </main>
    </div>
  )
}

function PolicyTable({
  policies,
  selectedCode,
  onSelect,
}: {
  policies: TerminalPolicy[]
  selectedCode: string | null
  onSelect: (code: string) => void
}) {
  return (
    <div className="policy-table-wrap">
      <table className="policy-table">
        <thead>
          <tr>
            <th>Policy Unit</th>
            <th>Current PCI</th>
            <th>Weekly Change</th>
            <th>Dimensions</th>
            <th>Latest Evidence</th>
            <th>Score Inputs</th>
            <th>Trajectory</th>
          </tr>
        </thead>
        <tbody>
          {policies.map((policy) => (
            <tr
              key={policy.code}
              className={policy.code === selectedCode ? "selected" : ""}
            >
              <td data-label="Policy unit">
                <span className="mobile-cell-label">Policy unit</span>
                <button type="button" onClick={() => onSelect(policy.code)}>
                  <strong>{policy.code}</strong>
                  <span>{policy.name}</span>
                </button>
              </td>
              <td data-label="Current PCI">
                <span className="mobile-cell-label">Current PCI</span>
                <span>{formatScore(policy.currentPci)}</span>
              </td>
              <td data-label="Weekly change">
                <span className="mobile-cell-label">Weekly change</span>
                <span className={deltaToneClass(policy.weeklyDelta)}>
                  {formatDelta(policy.weeklyDelta)}
                </span>
              </td>
              <td data-label="Dimensions">
                <span className="mobile-cell-label">Dimensions</span>
                <span className="dimension-triplet">
                  S {formatScore(policy.specificity)} / D {formatScore(policy.durability)} / E{" "}
                  {formatScore(policy.enforceability)}
                </span>
              </td>
              <td data-label="Latest evidence">
                <span className="mobile-cell-label">Latest evidence</span>
                <span className="evidence-cell">
                  <strong>{evidenceSource(policy)}</strong>
                  <span>{evidenceTitle(policy)}</span>
                </span>
              </td>
              <td data-label="Score inputs">
                <span className="mobile-cell-label">Score inputs</span>
                <span className="dimension-triplet">
                  {scoreBasis(policy)}
                </span>
              </td>
              <td data-label="Trajectory">
                <span className="mobile-cell-label">Trajectory</span>
                <span>{trajectoryLabel(policy)}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {!policies.length && (
        <div className="market-empty">No matching policy. Clear search to restore the register.</div>
      )}
    </div>
  )
}

function PolicyPreview({ policy }: { policy: TerminalPolicy | undefined }) {
  if (!policy) {
    return <aside className="policy-preview">No policy selected.</aside>
  }

  return (
    <aside className="policy-preview">
      <div className="preview-head">
        <span className="policy-code">{policy.code}</span>
        <span className="policy-lane-badge">{policy.lane}</span>
      </div>
      <h2>{policy.name}</h2>
      <p>{policy.formalName}</p>

      <div className="preview-score-grid">
        <Kpi label="Current PCI" value={formatScore(policy.currentPci)} />
        <Kpi
          label="Weekly change"
          value={formatDelta(policy.weeklyDelta)}
          valueClassName={deltaToneClass(policy.weeklyDelta)}
        />
        <Kpi label="Cited evidence" value={String(policy.evidenceAnchorCount)} />
        <Kpi label="Trajectory" value={trajectoryLabel(policy)} />
      </div>

      <section>
        <h3>Attribution</h3>
        <p>{evidenceTitle(policy)}</p>
        <small>{evidenceSource(policy)} / {formatPolicyDate(evidenceDate(policy))}</small>
        <ul className="policy-driver-list">
          {policy.attributionDrivers.slice(0, 3).map((driver) => (
            <li key={driver}>{driver}</li>
          ))}
        </ul>
      </section>

      <section>
        <h3>PCI components</h3>
        <p>
          Specificity {formatScore(policy.specificity)}, durability{" "}
          {formatScore(policy.durability)}, enforceability{" "}
          {formatScore(policy.enforceability)}.
        </p>
      </section>

      <section>
        <h3>Policy basis</h3>
        <p>{policy.formalName}</p>
      </section>

      <Link href={`/policies/${policy.code}`} className="primary-action compact">
        Open policy dossier
      </Link>
    </aside>
  )
}

function Kpi({
  label,
  value,
  valueClassName,
}: {
  label: string
  value: string
  valueClassName?: string
}) {
  return (
    <div className="kpi-chip">
      <span>{label}</span>
      <strong className={valueClassName}>{value}</strong>
    </div>
  )
}

function TapeItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
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

function evidenceTitle(policy: TerminalPolicy) {
  return policy.latestEvidenceTitle ?? `${policy.formalName} statutory baseline`
}

function evidenceSource(policy: TerminalPolicy) {
  return policy.latestEvidenceSource ?? "PCI policy registry"
}

function evidenceDate(policy: TerminalPolicy) {
  return policy.latestEvidenceAt ?? policy.updatedAt ?? policy.latestRefreshAt
}

function scoreBasis(policy: TerminalPolicy) {
  if (policy.eventCount > 0) {
    return `${policy.eventCount} weekly ${policy.eventCount === 1 ? "move" : "moves"} / ${policy.evidenceAnchorCount} citations`
  }
  return `${policy.evidenceAnchorCount} cited sources`
}

function formatRegistryState(value: string | null | undefined) {
  return value ? `Updated ${formatDateTime(value)}` : "Current policy registry"
}

function formatPolicyDate(value: string | null | undefined) {
  const formatted = formatDate(value)
  return formatted === "-" ? "Current registry" : formatted
}

function trajectoryLabel(policy: TerminalPolicy) {
  const value = policy.weeklyDelta
  if (value === null || value === undefined || Number.isNaN(value) || value === 0) {
    return "stable"
  }
  return value > 0 ? "strengthening" : "weakening"
}
