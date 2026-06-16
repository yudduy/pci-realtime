import { ExternalLink } from "lucide-react"
import { formatDate } from "@/components/market/format"
import type { RegistryData } from "@/lib/data"
import { buildSourceCitations } from "@/lib/citations"
import { policyCopy, type PolicySourceReference } from "@/lib/policy-copy"

export function SourceCitationPanel({
  data,
  policyCode,
  compact = false,
}: {
  data: RegistryData
  policyCode?: string
  compact?: boolean
}) {
  const citations = buildSourceCitations(data, policyCode)
  const shownCitations = citations.slice(0, compact ? 4 : 6)
  const sourceReferences = policyCode ? policyCopy(policyCode).sourceReferences : []

  return (
    <section className={`source-citation-panel${compact ? " compact" : ""}`}>
      <div className="section-heading">
        <p>Score evidence</p>
        <h2>Links behind this policy score</h2>
      </div>

      <div className="source-citation-digest">
        <div className="source-citation-list">
          {shownCitations.map((citation) => (
            <CitationRow key={citation.id} citation={citation} />
          ))}
          {!shownCitations.length && (
            sourceReferences.length ? (
              sourceReferences.map((reference, index) => (
                <ReferenceRow
                  key={reference.url}
                  code={policyCode ?? null}
                  index={index + 1}
                  reference={reference}
                />
              ))
            ) : (
              <div className="source-citation-empty">
                <strong>Current statutory profile</strong>
                <span>
                  The current PCI profile is grounded in the tracked IRA policy
                  unit and updates when official evidence changes specificity,
                  durability, or enforceability.
                </span>
              </div>
            )
          )}
        </div>
      </div>
    </section>
  )
}

function CitationRow({
  citation,
}: {
  citation: ReturnType<typeof buildSourceCitations>[number]
}) {
  const signal = formatSignal(citation.signal)
  const body = (
    <>
      <div className="source-citation-head">
        <span className="citation-index">[{citation.index}]</span>
        <span>{citation.sourceName}</span>
        {citation.policyCode && <strong>{citation.policyCode}</strong>}
      </div>
      <h3>{citation.title}</h3>
      {citation.snippet && <p>{citation.snippet}</p>}
      {citation.citationQuote && (
        <blockquote className="source-citation-quote">
          {citation.citationQuote}
        </blockquote>
      )}
      {signal && (
        <div className="source-signal">
          <span>Parsed signal</span>
          <strong>{signal}</strong>
        </div>
      )}
      <div className="source-citation-meta">
        <span>{citation.agency ?? citation.sourceType ?? "Official source"}</span>
        <span>{formatDate(citation.publishedAt)}</span>
        {citation.dimension && <span>{citation.dimension}</span>}
        {citation.citationSection && <span>{citation.citationSection}</span>}
        {citation.citationPage && <span>p. {citation.citationPage}</span>}
        {citation.collectedEvidence && <span>Contributor intake</span>}
        {citation.confidence !== null && <span>{Math.round(citation.confidence * 100)}% confidence</span>}
      </div>
    </>
  )

  if (citation.url) {
    return (
      <a href={citation.url} className="source-citation-row">
        {body}
        <ExternalLink className="source-citation-icon" aria-hidden="true" />
      </a>
    )
  }

  return <div className="source-citation-row">{body}</div>
}

function formatSignal(signal: string | null | undefined) {
  if (!signal) return null
  const normalized = signal.trim().replace(/\s*PCI$/i, "")
  if (normalized === "+0.00" || normalized === "0.00" || normalized === "0") {
    return "--"
  }
  return normalized
}

function ReferenceRow({
  code,
  index,
  reference,
}: {
  code: string | null
  index: number
  reference: PolicySourceReference
}) {
  return (
    <a href={reference.url} className="source-citation-row">
      <div className="source-citation-head">
        <span className="citation-index">[{index}]</span>
        <span>{reference.source}</span>
        {code && <strong>{code}</strong>}
      </div>
      <h3>{reference.title}</h3>
      <p>{reference.note}</p>
      <div className="source-citation-meta">
        <span>Score input</span>
        <span>{reference.dimension}</span>
      </div>
      <ExternalLink className="source-citation-icon" aria-hidden="true" />
    </a>
  )
}
