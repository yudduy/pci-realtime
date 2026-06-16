import type { PolicyEvent, ResolvedForecast } from "@/lib/data"
import { deltaToneClass, formatDate, formatDelta, formatPercent } from "@/components/market/format"
import { policyCopy } from "@/lib/policy-copy"

export function ActivityList({
  events,
  outcomes,
}: {
  events: PolicyEvent[]
  outcomes: ResolvedForecast[]
}) {
  const items = [
    ...events.map((event) => ({
      id: `event:${event.event_id}`,
      title: event.title ?? event.agency ?? "Official policy update",
      meta: `${policyCopy(event.provision, event.provision_name).name} / ${formatDate(event.created_at)}`,
      value: formatDelta(event.pci_delta),
      valueClassName: deltaToneClass(event.pci_delta),
      href: event.url,
      source: event.agency ?? event.doc_source ?? "Official source",
    })),
    ...outcomes.map((outcome) => ({
      id: `outcome:${outcome.forecast_id}`,
      title: outcome.market_title ?? outcome.market_ticker,
      meta: `Resolved / ${formatDate(outcome.resolved_at)}`,
      value: formatPercent(outcome.settlement_value),
      valueClassName: undefined,
      href: null,
      source: outcome.venue,
    })),
  ].slice(0, 8)

  return (
    <section className="activity-panel">
      <div className="section-heading">
        <p>Latest Updates</p>
        <h2>Official moves and outcomes</h2>
      </div>
      <div className="activity-list">
        {items.length ? (
          items.map((item) => {
            const content = (
              <>
                <div>
                  <strong>{item.title}</strong>
                  <span>{item.meta}</span>
                  <small>{item.source}</small>
                </div>
                <em className={item.valueClassName}>{item.value}</em>
              </>
            )

            if (item.href) {
              return (
                <a key={item.id} href={item.href} className="activity-item">
                  {content}
                </a>
              )
            }

            return (
              <div key={item.id} className="activity-item">
                {content}
              </div>
            )
          })
        ) : (
          <div className="activity-empty">Policy movement appears here as source citations update the registry.</div>
        )}
      </div>
    </section>
  )
}
