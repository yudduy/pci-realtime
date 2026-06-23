import { SiteHeader } from "@/components/layout/site-header"

// Shown while the server fetches registry views — mirrors the desk layout
// so the page does not reflow when content arrives.
export default function Loading() {
  return (
    <div className="tracker-page policy-terminal">
      <SiteHeader />
      <main className="terminal-shell" aria-busy="true" aria-label="Loading policy register">
        <section className="terminal-hero">
          <div>
            <p className="eyebrow">Daily Staff Desk</p>
            <div className="terminal-title-row">
              <h1>Policy Intelligence Desk</h1>
            </div>
          </div>
        </section>
        <div className="skeleton-block skeleton-carousel" />
        <div className="skeleton-list">
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className="skeleton-row">
              <div className="skeleton-row-title">
                <div className="skeleton-line skeleton-line-strong" />
                <div className="skeleton-line skeleton-line-wide" />
              </div>
              <div className="skeleton-block skeleton-spark" />
              <div className="skeleton-block skeleton-score" />
            </div>
          ))}
        </div>
      </main>
    </div>
  )
}
