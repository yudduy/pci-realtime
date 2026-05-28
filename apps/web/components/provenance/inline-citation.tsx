"use client"

import type { ProvenanceCitation } from "@/lib/provenance"

export function InlineCitation({
  citation,
  label,
  active = false,
  onOpen,
}: {
  citation: ProvenanceCitation
  label: string
  active?: boolean
  onOpen: (citationId: string) => void
}) {
  return (
    <span className="inline-citation-wrap">
      <button
        type="button"
        className={active ? "inline-citation active" : "inline-citation"}
        aria-label={`Open evidence ${label}: ${citation.sourceTitle}`}
        onClick={() => onOpen(citation.id)}
      >
        {label}
      </button>
      <span className="inline-citation-preview" role="tooltip">
        <strong>{citation.sourceName}</strong>
        <span>{citation.sourceTitle}</span>
        {citation.quote && <em>{citation.quote}</em>}
      </span>
    </span>
  )
}
