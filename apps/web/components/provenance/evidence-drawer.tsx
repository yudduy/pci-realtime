"use client"

import { ExternalLink, X } from "lucide-react"
import { formatDateTime, formatPercent } from "@/components/market/format"
import type { ProvenanceCitation } from "@/lib/provenance"

export function EvidenceDrawer({
  citation,
  onClose,
}: {
  citation: ProvenanceCitation | null
  onClose: () => void
}) {
  if (!citation) return null

  const metadataRows = [
    ["Evidence type", citation.evidenceType],
    ["Dimension", citation.scoreDimension],
    ["Confidence", formatPercent(citation.confidence)],
    ["Extractor", citation.extractorVersion],
    ["Section", citation.sectionTitle],
    ["Chunk", citation.chunkId],
    ["Chunk hash", citation.chunkHash],
    ["Retrieval score", citation.retrievalScore === null ? null : citation.retrievalScore.toFixed(3)],
  ].filter((row): row is [string, string] => Boolean(row[1]))

  return (
    <section className="evidence-drawer" aria-label="Evidence detail">
      <div className="evidence-drawer-head">
        <div>
          <p>Source Evidence</p>
          <h3>{citation.sourceTitle}</h3>
        </div>
        <button type="button" aria-label="Close evidence detail" onClick={onClose}>
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>

      <div className="evidence-source">
        <span>{citation.sourceName}</span>
        {citation.agency && <span>{citation.agency}</span>}
        <span>{formatDateTime(citation.fetchedAt ?? citation.publishedAt)}</span>
      </div>

      {citation.quote ? (
        <blockquote className="evidence-quote">{citation.quote}</blockquote>
      ) : (
        <p className="evidence-empty">No quoted source text is attached yet.</p>
      )}

      {citation.sourceUrl && (
        <a className="evidence-source-link" href={citation.sourceUrl}>
          Open original source
          <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
        </a>
      )}

      {citation.matchedTerms.length > 0 && (
        <div className="evidence-tags" aria-label="Matched retrieval terms">
          {citation.matchedTerms.map((term) => (
            <span key={term}>{term}</span>
          ))}
        </div>
      )}

      {metadataRows.length > 0 && (
        <dl className="evidence-metadata">
          {metadataRows.map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  )
}
