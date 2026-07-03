import Link from "next/link"
import { notFound } from "next/navigation"
import { SiteHeader } from "@/components/layout/site-header"
import { deltaToneClass, formatDate, formatDelta, formatPciValue, formatScore } from "@/components/market/format"
import { getRegistryData } from "@/lib/data"
import { buildPolicyDossier } from "@/lib/policy-dossier"

type PolicyPageProps = {
  params: Promise<{ code: string }>
}

type PolicyDossierData = NonNullable<ReturnType<typeof buildPolicyDossier>>

export const dynamic = "force-dynamic"

export default async function PolicyPage({ params }: PolicyPageProps) {
  const { code } = await params
  const data = await getRegistryData()
  const dossier = buildPolicyDossier(data, code)
  if (!dossier) notFound()

  const {
    policy,
    weeklyMove,
    evidence,
    reviewedLeads,
    staffQuestions,
  } = dossier
  // Same threshold formatDelta rounds at, so we never render "+0.00 this week".
  const move = weeklyMove && Math.abs(weeklyMove) >= 0.005 ? weeklyMove : 0

  return (
    <div className="tracker-page policy-dossier-page">
      <SiteHeader />
      <main className="policy-dossier-shell">
        <section className="policy-dossier-hero">
          <Link href="/" className="policy-dossier-back">All policies</Link>
          <p className="eyebrow">Policy Intelligence Desk</p>
          <h1>{policy.name}</h1>
          <p>{policy.formalName}</p>
          <div className="policy-dossier-metrics" aria-label="Policy credibility breakdown">
            <Metric
              label="Derived PCI"
              value={formatPciValue(policy.currentPci)}
              sub={move ? `${formatDelta(move)} this week` : "No move this week"}
              subClassName={deltaToneClass(move)}
              scaleValue={policy.currentPci}
              primary
            />
            <Metric label="Specificity" value={formatScore(policy.specificity)} gauge={policy.specificity} />
            <Metric label="Durability" value={formatScore(policy.durability)} gauge={policy.durability} />
            <Metric label="Enforceability" value={formatScore(policy.enforceability)} gauge={policy.enforceability} />
          </div>
          <p className="policy-dossier-meta-caption">
            <span>
              {policy.evidenceCount} verified {policy.evidenceCount === 1 ? "source" : "sources"}
            </span>
            {policy.latestRefreshAt ? (
              <span>Refreshed {formatDate(policy.latestRefreshAt)}</span>
            ) : null}
          </p>
        </section>

        <section className="policy-dossier-grid">
          <article className="policy-dossier-panel">
            <p className="eyebrow">Verified Evidence</p>
            <h2>Primary Sources</h2>
            <EvidenceList evidence={evidence} />
          </article>
          <article className="policy-dossier-panel">
            <p className="eyebrow">Reviewed Leads</p>
            <h2>Reviewed Watchlist</h2>
            <LeadList leads={reviewedLeads} />
          </article>
          <article className="policy-dossier-panel policy-dossier-panel-full">
            <p className="eyebrow">Staff Q&A</p>
            <h2>Answers From The Ledger</h2>
            <div className="policy-dossier-qa">
              {staffQuestions.map((item) => (
                <article key={item.question}>
                  <h3>{item.question}</h3>
                  <p>{item.answer}</p>
                  {item.citations.length ? (
                    <div className="policy-dossier-citations">
                      {item.citations.map((citation) =>
                        citation.href ? (
                          <a key={citation.label} href={citation.href}>{citation.label}</a>
                        ) : (
                          <span key={citation.label}>{citation.label}</span>
                        ),
                      )}
                    </div>
                  ) : null}
                </article>
              ))}
            </div>
          </article>
        </section>
      </main>
    </div>
  )
}

function Metric({
  label,
  value,
  sub,
  subClassName,
  primary,
  gauge,
  scaleValue,
}: {
  label: string
  value: string
  sub?: string
  subClassName?: string
  primary?: boolean
  gauge?: number | null
  scaleValue?: number | null
}) {
  return (
    <div className={primary ? "policy-dossier-metric-primary" : undefined}>
      <span>{label}</span>
      <strong>{value}</strong>
      {typeof gauge === "number" && Number.isFinite(gauge) ? (
        <div className="policy-dossier-gauge" aria-hidden="true">
          {[1, 2, 3, 4, 5].map((step) => (
            <span key={step} className={step <= Math.round(gauge) ? "on" : ""} />
          ))}
        </div>
      ) : null}
      {typeof scaleValue === "number" && Number.isFinite(scaleValue) ? (
        // Continuous 1–5 position bar — balances the strip (PCI is derived/continuous,
        // so a bar, not discrete pips) and shares the dimension gauges' baseline.
        <div className="policy-dossier-pci-bar" aria-hidden="true">
          <span style={{ width: `${Math.max(0, Math.min(100, ((scaleValue - 1) / 4) * 100))}%` }} />
        </div>
      ) : null}
      {sub ? (
        <div className={`policy-dossier-metric-sub ${subClassName ?? ""}`.trim()}>{sub}</div>
      ) : null}
    </div>
  )
}

function EvidenceList({ evidence }: { evidence: PolicyDossierData["evidence"] }) {
  if (!evidence.length)
    return (
      <p className="policy-dossier-empty">
        Monitoring official sources — no verified citation in this window yet.
      </p>
    )
  return (
    <ul className="policy-dossier-list">
      {evidence.slice(0, 5).map((item) => (
        <li key={item.evidence_id}>
          <span className="policy-dossier-item-copy">
            <b>{item.source_title ?? item.snippet ?? item.evidence_id}</b>
            <small>{evidenceMeta(item)}</small>
          </span>
          {item.canonical_url || item.url ? (
            <a href={item.canonical_url ?? item.url ?? "#"}>Open source</a>
          ) : (
            <strong>{item.quote_verified_against_source ? "verified" : "reviewed"}</strong>
          )}
        </li>
      ))}
    </ul>
  )
}

function LeadList({ leads }: { leads: PolicyDossierData["reviewedLeads"] }) {
  if (!leads.length)
    return (
      <p className="policy-dossier-empty">
        Monitoring — no reviewed context leads in this window yet.
      </p>
    )
  return (
    <ul className="policy-dossier-list">
      {leads.slice(0, 5).map((lead) => (
        <li key={lead.candidate_id}>
          <span className="policy-dossier-item-copy">
            <b>{lead.title}</b>
            <small>{lead.why_it_matters ?? "Reviewed context for staff monitoring."}</small>
          </span>
          <strong>{leadLabel(lead)}</strong>
        </li>
      ))}
    </ul>
  )
}

function evidenceMeta(
  item: PolicyDossierData["evidence"][number],
) {
  const issuer = item.source_name ?? item.agency ?? "Official source"
  const date = formatDate(item.published_at ?? item.created_at)
  const status = item.quote_verified_against_source ? "quote verified" : "reviewed"
  return `${issuer} · ${date} · ${status}`
}

function leadLabel(
  lead: PolicyDossierData["reviewedLeads"][number],
) {
  let classLabel: string
  switch (lead.source_class) {
    case "official":
      classLabel = "official source"
      break
    case "news":
      classLabel = "reviewed news lead"
      break
    case "analysis":
      classLabel = "reviewed analysis"
      break
    default:
      classLabel = "mixed source"
  }

  const useLabel =
    lead.promotability === "ledger_candidate"
      ? "ready for evidence review"
      : "not used in scoring"
  return `${classLabel}; ${useLabel}`
}
