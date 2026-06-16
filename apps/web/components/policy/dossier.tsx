import Link from "next/link"
import { PolicyTrend } from "@/components/market/policy-trend"
import { SiteHeader } from "@/components/layout/site-header"
import { formatDate, formatScore } from "@/components/market/format"
import { SourceCitationPanel } from "@/components/policy/source-citations"
import type { PolicyEvent, RegistryData } from "@/lib/data"
import type { PolicyIntelligence } from "@/lib/intelligence"

export function PolicyDossier({
  data,
  policy,
}: {
  data: RegistryData
  policy: PolicyIntelligence
}) {
  const events = data.policyEvents
    .filter((event) => event.provision === policy.code)
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())

  return (
    <main className="tracker-page policy-detail-page">
      <SiteHeader />

      <section className="policy-detail-hero">
        <nav aria-label="Breadcrumbs" className="policy-breadcrumb">
          <Link href="/dashboard">Terminal</Link>
          <span aria-hidden="true">/</span>
          <span>{policy.code}</span>
        </nav>

        <div className="policy-detail-grid">
          <div>
            <div className="preview-head">
              <span className="policy-code">{policy.code}</span>
              <span className="policy-lane-badge">{policy.lane}</span>
            </div>
            <h1>{policy.name}</h1>
            <p>{policy.formalName}</p>
          </div>

          <div className="detail-score-board">
            <Metric label="Current PCI" value={formatScore(policy.currentPci)} />
            <Metric label="Cited evidence" value={String(policy.evidenceAnchorCount)} />
            <Metric label="Last update" value={formatPolicyDate(policy.latestEvidenceAt ?? policy.updatedAt ?? policy.latestRefreshAt)} />
          </div>
        </div>
      </section>

      <section className="policy-detail-layout">
        <div className="policy-detail-main">
          <section className="terminal-panel">
            <p className="eyebrow">What changed</p>
            <h2>Latest official evidence</h2>
            {events.length ? (
              <div className="evidence-timeline">
                {events.slice(0, 5).map((event) => (
                  <EventRow key={event.event_id} event={event} />
                ))}
              </div>
            ) : (
              <div className="evidence-row">
                <strong>{policy.formalName} current statutory profile</strong>
                <span>{baselineSourceLine(policy)}</span>
                <p>
                  This policy unit is measured through the current PCI dimensions
                  and official source references; weekly movement is attributed when
                  new material changes specificity, durability, or enforceability.
                </p>
                <ul className="policy-driver-list">
                  {policy.attributionDrivers.map((driver) => (
                    <li key={driver}>{driver}</li>
                  ))}
                </ul>
              </div>
            )}
          </section>

          <section className="terminal-panel">
            <p className="eyebrow">PCI breakdown</p>
            <h2>Specificity, durability, enforceability</h2>
            <div className="dimension-grid">
              <Dimension label="Specificity" value={policy.specificity} />
              <Dimension label="Durability" value={policy.durability} />
              <Dimension label="Enforceability" value={policy.enforceability} />
            </div>
            <div className="policy-context-note">
              <strong>Policy intelligence context</strong>
              <span>{policy.evidenceAnchorCount} cited sources</span>
              <p>
                PCI is a score that moves week to week. Each move is attributed
                to source material that changes specificity, durability, or
                enforceability; zero-delta material still remains useful context.
              </p>
            </div>
          </section>

          <SourceCitationPanel data={data} policyCode={policy.code} compact />
        </div>

        <aside className="policy-detail-side">
          <PolicyTrend
            timelines={data.provisionTimelines}
            policies={data.currentPci}
            provision={policy.code}
          />

          <section className="terminal-panel compact-panel">
            <h3>Policy basis</h3>
            <p>{policy.formalName}</p>
            <p>
              The displayed PCI is the average of specificity, durability, and
              enforceability for this tracked IRA policy unit.
            </p>
          </section>
        </aside>
      </section>
    </main>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function Dimension({ label, value }: { label: string; value: number | null }) {
  const width = `${Math.max(0, Math.min(100, ((value ?? 0) / 5) * 100))}%`
  return (
    <div className="dimension-card">
      <div>
        <span>{label}</span>
        <strong>{formatScore(value)}</strong>
      </div>
      <div className="dimension-bar">
        <span style={{ width }} />
      </div>
    </div>
  )
}

function EventRow({ event }: { event: PolicyEvent }) {
  const body = (
    <>
      <strong>{event.title ?? "Official policy update"}</strong>
      <span>
        {event.agency ?? "Official source"} / {formatDate(event.created_at)}
      </span>
      {event.rationale && <p>{event.rationale}</p>}
    </>
  )

  if (event.url) {
    return (
      <a href={event.url} className="evidence-row">
        {body}
      </a>
    )
  }
  return <div className="evidence-row">{body}</div>
}

function baselineSourceLine(policy: PolicyIntelligence) {
  const date = formatPolicyDate(policy.updatedAt ?? policy.latestRefreshAt)
  return date === "Baseline" ? "PCI policy registry" : `PCI policy registry / ${date}`
}

function formatPolicyDate(value: string | null | undefined) {
  const date = formatDate(value)
  return date === "-" ? "Baseline" : date
}
