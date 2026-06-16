import Link from "next/link"
import { deltaToneClass, formatDelta, formatScore } from "@/components/market/format"
import type { RegistryData } from "@/lib/data"
import { buildPolicyIntelligence } from "@/lib/intelligence"

export function PolicyRegister({ data }: { data: RegistryData }) {
  const policies = buildPolicyIntelligence(data)

  return (
    <ul className="policy-card-grid" aria-label="Policy intelligence">
      {policies.map((policy) => (
        <li key={policy.code}>
          <Link href={`/policies/${policy.code}`} className="policy-card">
            <header className="policy-card-head">
              <span className="policy-code">{policy.code}</span>
              <span className="policy-lane-badge">{policy.lane}</span>
            </header>

            <div>
              <p className="policy-lane">{policy.lane}</p>
              <h3>{policy.name}</h3>
              <p className="policy-question">{policy.question}</p>
            </div>

            <div className="policy-score-grid">
              <ScoreBlock label="Current PCI" value={formatScore(policy.currentPci)} />
              <ScoreBlock
                label="Weekly change"
                value={formatDelta(policy.weeklyDelta)}
                valueClassName={deltaToneClass(policy.weeklyDelta)}
              />
            </div>
          </Link>
        </li>
      ))}
    </ul>
  )
}

function ScoreBlock({
  label,
  value,
  valueClassName,
}: {
  label: string
  value: string
  valueClassName?: string
}) {
  return (
    <div>
      <span>{label}</span>
      <strong className={valueClassName}>{value}</strong>
    </div>
  )
}
