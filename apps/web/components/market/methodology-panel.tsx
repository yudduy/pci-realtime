import { formatScore } from "@/components/market/format"
import type { ProvisionView } from "@/lib/provision-view"

export function MethodologyPanel({ view }: { view: ProvisionView }) {
  const current = view.policy
  return (
    <div className="methodology-panel">
      <section>
        <h3>How {view.code} is scored</h3>
        <p>
          PCI for {view.code} is the weekly average of three independent dimensions, each scored 1–5 from official
          policy sources. Scores are sticky week-over-week and clipped to the [1, 5] range. Stress score reflects the
          post-OBBBA snapshot.
        </p>
      </section>
      <section className="methodology-breakdown">
        <DimensionLine
          label="Specificity"
          description="How clear are the eligibility rules?"
          current={current?.specificity ?? view.baselineDimensions.specificity}
          baseline={view.baselineDimensions.specificity}
        />
        <DimensionLine
          label="Durability"
          description="Does the commitment survive across investment horizons?"
          current={current?.durability ?? view.baselineDimensions.durability}
          baseline={view.baselineDimensions.durability}
        />
        <DimensionLine
          label="Enforceability"
          description="Is implementation assigned to an agency process?"
          current={current?.enforceability ?? view.baselineDimensions.enforceability}
          baseline={view.baselineDimensions.enforceability}
        />
      </section>
      <section className="methodology-formula">
        <h4>Weekly update rule</h4>
        <pre>
{`PCI[p, t] = clip(
  PCI[p, t-1] + Σ_doc (Δspec + Δdur + Δenf) / 3,
  1.0,
  5.0
)`}
        </pre>
        <p>
          Each scored official document changes specificity, durability, or enforceability by dimension-level deltas
          in [-2, +2]. Stress score is computed against the post-OBBBA anchor and does not advance week-over-week.
        </p>
      </section>
    </div>
  )
}

function DimensionLine({
  label,
  description,
  current,
  baseline,
}: {
  label: string
  description: string
  current: number | null
  baseline: number
}) {
  const value = current ?? baseline
  const width = `${Math.max(0, Math.min(100, (value / 5) * 100))}%`
  return (
    <div className="methodology-line">
      <div>
        <strong>{label}</strong>
        <span>{description}</span>
      </div>
      <div className="methodology-bar-wrap">
        <div className="methodology-bar">
          <div style={{ width }} />
        </div>
        <em>{formatScore(value)}</em>
      </div>
    </div>
  )
}
