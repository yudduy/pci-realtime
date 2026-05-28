import Link from "next/link"
import type { PolicyEvent } from "@/lib/data"

export function EvidenceTimeline({
  events,
  provisionCode,
}: {
  events: PolicyEvent[]
  provisionCode: string
}) {
  if (!events.length) {
    return (
      <p className="evidence-timeline-empty" role="status">
        No scored policy update found for {provisionCode}. The next weekly ingest will add events here when official
        sources publish changes.
      </p>
    )
  }

  return (
    <ol className="evidence-timeline" aria-label="Policy events">
      {events.map((event) => (
        <li key={event.event_id} className="evidence-timeline-item">
          <time dateTime={event.created_at}>
            {new Date(event.created_at).toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
              year: "numeric",
            })}
          </time>
          <div className="evidence-timeline-body">
            <header>
              <h3>{event.title ?? "Policy event"}</h3>
              <DeltaPill value={event.pci_delta} />
            </header>
            {event.rationale && <p>{event.rationale}</p>}
            <div className="evidence-timeline-meta">
              <span>{event.agency ?? event.doc_source ?? "Official source"}</span>
              {Object.entries(event.dimension_deltas ?? {}).map(([dim, value]) => (
                <span key={dim} className="evidence-timeline-dim">
                  {dim.slice(0, 4)} {value >= 0 ? "+" : ""}
                  {value.toFixed(2)}
                </span>
              ))}
              <Link href={`/evidence/${event.event_id}`}>View source</Link>
            </div>
          </div>
        </li>
      ))}
    </ol>
  )
}

function DeltaPill({ value }: { value: number | null | undefined }) {
  if (value === null || value === undefined || Number.isNaN(value) || value === 0) {
    return <span className="delta-pill delta-flat">No score change</span>
  }
  const positive = value > 0
  return (
    <span className={`delta-pill ${positive ? "delta-up" : "delta-down"}`}>
      {positive ? "+" : ""}
      {value.toFixed(2)} PCI
    </span>
  )
}
