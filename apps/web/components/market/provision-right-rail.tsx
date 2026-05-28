import { formatScore } from "@/components/market/format"
import type { ProvisionView } from "@/lib/provision-view"

export function ProvisionRightRail({ view }: { view: ProvisionView }) {
  const policy = view.policy
  const current = policy?.pci ?? view.baselinePci
  const stress = policy?.obbba_post_pci ?? view.stressPci

  return (
    <aside className="provision-rail" aria-label="Provision score breakdown">
      <section className="provision-rail-block">
        <p className="provision-rail-eyebrow">Score</p>
        <div className="provision-rail-score">
          <strong>{formatScore(current)}</strong>
          <span>/ 5 policy credibility</span>
        </div>
        <div className="provision-rail-stress">
          Stress {formatScore(stress)} <small>post-OBBBA</small>
        </div>
      </section>

      <section className="provision-rail-block">
        <p className="provision-rail-eyebrow">Decomposition</p>
        <RailDimension
          label="Specificity"
          value={policy?.specificity ?? view.baselineDimensions.specificity}
        />
        <RailDimension
          label="Durability"
          value={policy?.durability ?? view.baselineDimensions.durability}
        />
        <RailDimension
          label="Enforceability"
          value={policy?.enforceability ?? view.baselineDimensions.enforceability}
        />
      </section>

      <section className="provision-rail-block">
        <p className="provision-rail-eyebrow">Market eligibility</p>
        <RailFact label="Eligible markets" value={String(view.eligibleMarkets.length)} />
        <RailFact label="Near-miss" value={String(view.nearMissMarkets.length)} />
        <RailFact
          label="Open forecasts"
          value={String(view.openForecasts.length)}
        />
        <RailFact
          label="Resolved"
          value={String(view.resolvedForecasts.length)}
        />
      </section>

      <section className="provision-rail-block">
        <p className="provision-rail-eyebrow">Evidence</p>
        <RailFact label="Scored events" value={String(view.events.length)} />
        <RailFact label="Citations" value={String(view.provenance.citations.length)} />
      </section>
    </aside>
  )
}

function RailDimension({ label, value }: { label: string; value: number | null }) {
  const score = value ?? 0
  const width = `${Math.max(4, Math.min(100, (score / 5) * 100))}%`
  return (
    <div className="provision-rail-dim">
      <div>
        <span>{label}</span>
        <strong>{formatScore(score)}</strong>
      </div>
      <div className="provision-rail-bar">
        <div style={{ width }} />
      </div>
    </div>
  )
}

function RailFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="provision-rail-fact">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}
