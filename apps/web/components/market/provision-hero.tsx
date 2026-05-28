import Link from "next/link"
import { formatScore } from "@/components/market/format"
import type { ProvisionView } from "@/lib/provision-view"

export function ProvisionHero({ view }: { view: ProvisionView }) {
  const current = view.policy?.pci ?? view.baselinePci
  const stress = view.policy?.obbba_post_pci ?? view.stressPci
  const delta = view.policy?.delta_this_week ?? 0
  const eligibleState = view.eligibleMarkets.length > 0
    ? "Eligible public market"
    : view.nearMissMarkets.length > 0
      ? "Near-miss market"
      : view.coverage.scanned > 0
        ? "No eligible public market"
        : "Source scan stale"
  const stateTone = eligibleState === "Eligible public market"
    ? "positive"
    : eligibleState === "Near-miss market"
      ? "warning"
      : "muted"

  return (
    <section className="provision-hero" aria-label={`${view.code} provision overview`}>
      <nav aria-label="Breadcrumbs" className="provision-breadcrumb">
        <Link href="/markets">Markets</Link>
        <span aria-hidden="true">·</span>
        <span>{view.lane}</span>
      </nav>

      <div className="provision-hero-grid">
        <div className="provision-hero-main">
          <div className="provision-hero-meta">
            <span className="provision-code">{view.code}</span>
            <span className="provision-lane">{view.lane}</span>
            <span className={`provision-state provision-state-${stateTone}`}>{eligibleState}</span>
          </div>
          <h1>{view.question}</h1>
          <p className="provision-formal">{view.formalName}</p>
        </div>

        <aside className="provision-hero-stats" aria-label="Provision score summary">
          <Stat
            label="Policy score"
            value={formatScore(current)}
            sub={delta ? `${delta >= 0 ? "+" : ""}${delta.toFixed(2)} this week` : "Stable"}
            tone="primary"
          />
          <Stat
            label="Stress score"
            value={formatScore(stress)}
            sub="Post-OBBBA snapshot"
            tone="muted"
          />
          <Stat
            label="Eligible markets"
            value={String(view.eligibleMarkets.length)}
            sub={view.nearMissMarkets.length ? `${view.nearMissMarkets.length} near-miss` : "Tracked"}
            tone="muted"
          />
          <Stat
            label="Public events"
            value={String(view.events.length)}
            sub={view.events[0] ? `Latest ${formatRelative(view.events[0].created_at)}` : "Scan pending"}
            tone="muted"
          />
        </aside>
      </div>
    </section>
  )
}

function Stat({
  label,
  value,
  sub,
  tone,
}: {
  label: string
  value: string
  sub: string
  tone: "primary" | "muted"
}) {
  return (
    <div className={`provision-stat provision-stat-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{sub}</small>
    </div>
  )
}

function formatRelative(iso: string | null | undefined) {
  if (!iso) return "—"
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return "—"
  const diffHours = (Date.now() - then) / 36e5
  if (diffHours < 1) return "just now"
  if (diffHours < 24) return `${Math.round(diffHours)}h ago`
  return `${Math.round(diffHours / 24)}d ago`
}
