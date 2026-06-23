import Link from "next/link"
import { notFound } from "next/navigation"
import { SiteHeader } from "@/components/layout/site-header"
import { formatDate, formatScore } from "@/components/market/format"
import { getRegistryData } from "@/lib/data"
import { buildPolicyDossier } from "@/lib/policy-dossier"

type PolicyPageProps = {
  params: Promise<{ code: string }>
}

export const dynamic = "force-dynamic"

export default async function PolicyPage({ params }: PolicyPageProps) {
  const { code } = await params
  const data = await getRegistryData()
  const dossier = buildPolicyDossier(data, code)
  if (!dossier) notFound()

  const {
    policy,
    theses,
    beliefUpdates,
    latestBrief,
    evidence,
    reviewedLeads,
    marketSignals,
    staffQuestions,
  } = dossier
  const latestUpdate = beliefUpdates[0] ?? null

  return (
    <div className="tracker-page policy-dossier-page">
      <SiteHeader />
      <main className="policy-dossier-shell">
        <section className="policy-dossier-hero">
          <Link href="/" className="policy-dossier-back">All policies</Link>
          <p className="eyebrow">Policy Intelligence Desk</p>
          <h1>{policy.name}</h1>
          <p>{policy.formalName}</p>
          <div className="policy-dossier-metrics" aria-label="Policy status metrics">
            <Metric label="PCI" value={formatScore(policy.currentPci)} />
            <Metric label="Evidence" value={String(policy.evidenceCount)} />
            <Metric label="Theses" value={String(theses.length)} />
            <Metric label="Last refresh" value={formatDate(policy.latestRefreshAt)} />
          </div>
        </section>

        <section className="policy-dossier-grid">
          <article className="policy-dossier-panel policy-dossier-panel-wide">
            <p className="eyebrow">Latest Staff Brief</p>
            <h2>{latestBrief?.title ?? `${policy.code} brief`}</h2>
            <p>{latestBrief?.summary ?? "No generated staff brief is available yet."}</p>
            <dl className="policy-dossier-brief-list">
              <div>
                <dt>What changed</dt>
                <dd>{latestBrief?.what_changed ?? "No verified ledger change in the current window."}</dd>
              </div>
              <div>
                <dt>Why it matters</dt>
                <dd>{latestBrief?.why_it_matters ?? policy.question}</dd>
              </div>
              <div>
                <dt>Decision relevance</dt>
                <dd>{latestBrief?.decision_relevance ?? "No new staff action is suggested by reviewed evidence alone."}</dd>
              </div>
            </dl>
          </article>

          <article className="policy-dossier-panel">
            <p className="eyebrow">Current Belief Move</p>
            {latestUpdate ? (
              <>
                <h2>{percent(latestUpdate.posterior_probability)} now</h2>
                <p>{latestUpdate.rationale}</p>
                <div className="policy-dossier-belief-delta">
                  <span>was {percent(latestUpdate.prior_probability)}</span>
                  <span>{beliefMove(latestUpdate)}</span>
                  <span>{latestUpdate.reliability} reliability</span>
                </div>
              </>
            ) : (
              <p>No approved belief update is available for this policy.</p>
            )}
          </article>
        </section>

        <section className="policy-dossier-section">
          <div className="policy-dossier-section-head">
            <p className="eyebrow">Tracked Theses</p>
            <h2>Beliefs The Desk Is Maintaining</h2>
          </div>
          <div className="policy-dossier-theses">
            {theses.length ? (
              theses.map((thesis) => (
                <article key={thesis.thesis_id} className="policy-dossier-thesis">
                  <h3>{thesis.question}</h3>
                  <div>
                    <span>{percent(thesis.current_probability)}</span>
                    <span>confidence {percent(thesis.confidence)}</span>
                  </div>
                </article>
              ))
            ) : (
              <p>No active theses are published for this policy yet.</p>
            )}
          </div>
        </section>

        <section className="policy-dossier-grid">
          <article className="policy-dossier-panel">
            <p className="eyebrow">Verified Evidence</p>
            <h2>Primary Sources</h2>
            <EvidenceList evidence={evidence} />
          </article>
          <article className="policy-dossier-panel">
            <p className="eyebrow">Reviewed Leads</p>
            <h2>Context, Not PCI Movement</h2>
            <LeadList leads={reviewedLeads} />
          </article>
        </section>

        <section className="policy-dossier-grid">
          <article className="policy-dossier-panel">
            <p className="eyebrow">Market Calibration</p>
            <h2>External Probability Signals</h2>
            {marketSignals.length ? (
              <ul className="policy-dossier-list">
                {marketSignals.slice(0, 4).map((market) => (
                  <li key={`${market.venue}:${market.ticker}`}>
                    <span>{market.title ?? market.ticker}</span>
                    <strong>{market.market_probability === null ? "n/a" : percent(market.market_probability)}</strong>
                  </li>
                ))}
              </ul>
            ) : (
              <p>No linked public market signal is available for this policy.</p>
            )}
          </article>
          <article className="policy-dossier-panel">
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

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function EvidenceList({ evidence }: { evidence: NonNullable<ReturnType<typeof buildPolicyDossier>>["evidence"] }) {
  if (!evidence.length) return <p>No verified policy-evidence citation is available yet.</p>
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

function LeadList({ leads }: { leads: NonNullable<ReturnType<typeof buildPolicyDossier>>["reviewedLeads"] }) {
  if (!leads.length) return <p>No reviewed context leads are published for this policy.</p>
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
  item: NonNullable<ReturnType<typeof buildPolicyDossier>>["evidence"][number],
) {
  const issuer = item.source_name ?? item.agency ?? "Official source"
  const date = formatDate(item.published_at ?? item.created_at)
  const status = item.quote_verified_against_source ? "quote verified" : "reviewed"
  return `${issuer} · ${date} · ${status}`
}

function leadLabel(
  lead: NonNullable<ReturnType<typeof buildPolicyDossier>>["reviewedLeads"][number],
) {
  const classLabel =
    lead.source_class === "official"
      ? "official source"
      : lead.source_class === "news"
        ? "reviewed news lead"
        : lead.source_class === "analysis"
          ? "reviewed analysis"
          : "mixed source"
  const useLabel =
    lead.promotability === "ledger_candidate"
      ? "ready for evidence review"
      : "not used in scoring"
  return `${classLabel}; ${useLabel}`
}

function beliefMove(
  update: NonNullable<ReturnType<typeof buildPolicyDossier>>["beliefUpdates"][number],
) {
  const delta = update.posterior_probability - update.prior_probability
  if (!Number.isFinite(delta) || Math.abs(delta) < 0.005) return "no material move"
  return `${delta > 0 ? "up" : "down"} ${Math.abs(Math.round(delta * 100))} pts`
}

function percent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "n/a"
  return `${Math.round(value * 100)}%`
}
