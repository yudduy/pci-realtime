import Link from "next/link"
import { formatScore } from "@/components/market/format"
import { POLICIES } from "@/lib/policy-copy"
import type { RegistryData } from "@/lib/data"

export function ProvisionGrid({ data }: { data: RegistryData }) {
  const cards = POLICIES.map((policy) => {
    const current = data.currentPci.find((row) => row.code === policy.code)
    const eligible = data.marketSnapshots.filter((snapshot) => snapshotMatches(snapshot, policy.code))
    const nearMiss = data.marketDiscoveryCandidates.filter(
      (candidate) =>
        candidate.matched_provisions.includes(policy.code) && !candidate.eligible_snapshot,
    )
    const events = data.policyEvents.filter((event) => event.provision === policy.code)
    const citations = new Set(
      data.sourceLinks
        .filter((link) => events.some((event) => event.event_id === link.target_id))
        .map((link) => link.evidence_id),
    )
    return {
      policy,
      current: current?.pci ?? policy.baseline,
      stress: current?.obbba_post_pci ?? policy.stress,
      delta: current?.delta_this_week ?? 0,
      specificity: current?.specificity ?? policy.specificity,
      durability: current?.durability ?? policy.durability,
      enforceability: current?.enforceability ?? policy.enforceability,
      eligible: eligible.length,
      nearMiss: nearMiss.length,
      events: events.length,
      citations: citations.size,
      latestEvent: events[0],
    }
  })

  return (
    <ul className="provision-grid" aria-label="Tracked provisions">
      {cards.map(({ policy, current, stress, delta, specificity, durability, enforceability, eligible, nearMiss, events, citations, latestEvent }) => {
        const eligibilityState =
          eligible > 0
            ? { label: "Eligible public market", tone: "positive" }
            : nearMiss > 0
              ? { label: "Near-miss market", tone: "warning" }
              : { label: "No eligible public market", tone: "muted" }

        return (
          <li key={policy.code} className="provision-grid-item">
            <Link
              href={`/markets/${policy.code}`}
              className="provision-card"
              aria-label={`${policy.code} — ${policy.question} — ${eligibilityState.label}, score ${formatScore(current)} of 5`}
            >
              <header className="provision-card-head">
                <span className="provision-card-code">{policy.code}</span>
                <span className={`provision-state provision-state-${eligibilityState.tone}`}>
                  {eligibilityState.label}
                </span>
              </header>
              <h3>{policy.question}</h3>
              <p className="provision-card-formal">{policy.lane}</p>

              <div className="provision-card-scores" aria-label="Score summary">
                <ScorePill label="Score" value={formatScore(current)} delta={delta} tone="primary" />
                <ScorePill label="Stress" value={formatScore(stress)} tone="muted" />
              </div>

              <ul className="provision-card-dims" aria-label="Policy score decomposition">
                <DimChip label="Spec" value={specificity} />
                <DimChip label="Dur" value={durability} />
                <DimChip label="Enf" value={enforceability} />
              </ul>

              <dl className="provision-card-facts">
                <Fact label="Eligible" value={eligible} />
                <Fact label="Near-miss" value={nearMiss} />
                <Fact label="Events" value={events} />
                <Fact label="Citations" value={citations} />
              </dl>

              {latestEvent && (
                <p className="provision-card-event">
                  {delta !== 0 ? `${delta >= 0 ? "+" : ""}${delta.toFixed(2)} from: ` : "Latest: "}
                  {latestEvent.title ?? "Policy update"}
                </p>
              )}
            </Link>
          </li>
        )
      })}
    </ul>
  )
}

function snapshotMatches(snapshot: RegistryData["marketSnapshots"][number], code: string) {
  const candidates = [snapshot.query_name, snapshot.title, snapshot.subtitle, snapshot.ticker, snapshot.event_ticker]
  return candidates.some((value) => typeof value === "string" && value.toUpperCase().includes(code.toUpperCase()))
}

function ScorePill({
  label,
  value,
  delta,
  tone,
}: {
  label: string
  value: string
  delta?: number
  tone: "primary" | "muted"
}) {
  return (
    <div className={`provision-score provision-score-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      {delta !== undefined && delta !== 0 && (
        <small>
          {delta >= 0 ? "+" : ""}
          {delta.toFixed(2)}
        </small>
      )}
    </div>
  )
}

function Fact({ label, value }: { label: string; value: number | string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  )
}

function DimChip({ label, value }: { label: string; value: number }) {
  return (
    <li>
      <span>{label}</span>
      <strong>{value.toFixed(1)}</strong>
    </li>
  )
}
