import type { SourceHealth } from "@/lib/data"
import { formatDateTime } from "@/components/market/format"

export function SourceHealthStrip({ sources }: { sources: SourceHealth[] }) {
  const visible = sources.slice(0, 5)
  if (!visible.length) return null

  return (
    <section className="source-strip" aria-label="Source updates">
      {visible.map((source) => (
        <div key={source.source} className="source-strip-item">
          <span className={source.status === "success" ? "source-dot" : "source-dot muted"} />
          <div>
            <strong>{source.source_name}</strong>
            <span>
              {source.status === "success"
                ? `Updated ${formatDateTime(source.last_success_at)}`
                : source.status === "disabled"
                  ? "Waiting for access"
                  : "Needs attention"}
            </span>
          </div>
        </div>
      ))}
    </section>
  )
}
