import { notFound } from "next/navigation"
import { BottomSheet } from "@/components/provenance/bottom-sheet"
import { getRegistryData } from "@/lib/data"

export const dynamic = "force-dynamic"

type Params = { params: Promise<{ code: string; id: string }> }

export default async function EvidenceDrawerPage({ params }: Params) {
  const { id } = await params
  const decoded = decodeURIComponent(id)
  const data = await getRegistryData()
  const event = data.policyEvents.find((row) => row.event_id === id || row.event_id === decoded)
  if (!event) notFound()

  return (
    <BottomSheet title={event.title ?? "Policy event"} eyebrow="Evidence source">
      <dl className="bottom-sheet-meta">
        <div>
          <dt>Provision</dt>
          <dd>{event.provision}</dd>
        </div>
        <div>
          <dt>Agency</dt>
          <dd>{event.agency ?? event.doc_source ?? "Official source"}</dd>
        </div>
        <div>
          <dt>Recorded</dt>
          <dd>{new Date(event.created_at).toLocaleString("en-US")}</dd>
        </div>
        <div>
          <dt>Score change</dt>
          <dd>
            {event.pci_delta >= 0 ? "+" : ""}
            {event.pci_delta.toFixed(2)} PCI
          </dd>
        </div>
      </dl>

      {event.rationale && (
        <section className="bottom-sheet-section">
          <h3>Rationale</h3>
          <p>{event.rationale}</p>
        </section>
      )}

      <section className="bottom-sheet-section">
        <h3>Dimension deltas</h3>
        <ul className="bottom-sheet-dims">
          {Object.entries(event.dimension_deltas ?? {}).map(([dim, value]) => (
            <li key={dim}>
              <strong>{dim}</strong>
              <span>
                {value >= 0 ? "+" : ""}
                {value.toFixed(2)}
              </span>
            </li>
          ))}
        </ul>
      </section>

      {event.url && (
        <a href={event.url} className="bottom-sheet-source" rel="noopener noreferrer">
          Open original source
        </a>
      )}
    </BottomSheet>
  )
}
