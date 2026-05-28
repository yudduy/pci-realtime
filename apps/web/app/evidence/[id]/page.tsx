import { notFound } from "next/navigation"
import Link from "next/link"
import { SiteHeader } from "@/components/layout/site-header"
import { getRegistryData } from "@/lib/data"

export const dynamic = "force-dynamic"

type Params = { params: Promise<{ id: string }> }

export default async function EvidenceDetailPage({ params }: Params) {
  const { id } = await params
  const decoded = decodeURIComponent(id)
  const data = await getRegistryData()
  const event = data.policyEvents.find((row) => row.event_id === id || row.event_id === decoded)
  if (!event) notFound()

  return (
    <main className="evidence-page">
      <SiteHeader />
      <article className="evidence-article">
        <nav aria-label="Breadcrumbs" className="provision-breadcrumb">
          <Link href="/markets">Markets</Link>
          <span aria-hidden="true">·</span>
          <Link href={`/markets/${event.provision}`}>{event.provision}</Link>
          <span aria-hidden="true">·</span>
          <span>Evidence</span>
        </nav>

        <header>
          <h1>{event.title ?? "Policy event"}</h1>
          <p>
            {event.agency ?? event.doc_source ?? "Official source"} · {new Date(event.created_at).toLocaleString("en-US")}
          </p>
        </header>

        <dl className="evidence-article-meta">
          <div>
            <dt>Score change</dt>
            <dd>
              {event.pci_delta >= 0 ? "+" : ""}
              {event.pci_delta.toFixed(2)} PCI
            </dd>
          </div>
          <div>
            <dt>Confidence</dt>
            <dd>{event.confidence ? `${Math.round(event.confidence * 100)}%` : "—"}</dd>
          </div>
          <div>
            <dt>Prompt</dt>
            <dd>{event.prompt_version ?? "—"}</dd>
          </div>
        </dl>

        {event.rationale && (
          <section>
            <h2>Rationale</h2>
            <p>{event.rationale}</p>
          </section>
        )}

        <section>
          <h2>Dimension deltas</h2>
          <ul className="evidence-dim-list">
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
          <a href={event.url} className="evidence-source-link" rel="noopener noreferrer">
            Open original source ↗
          </a>
        )}
      </article>
    </main>
  )
}
