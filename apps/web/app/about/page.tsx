import Link from "next/link"
import { SiteHeader } from "@/components/layout/site-header"
import { POLICIES } from "@/lib/policy-copy"

const authors = [
  { name: "Yikai Cao", institution: "Stanford University" },
  { name: "Charles Eesley", institution: "Stanford University" },
  { name: "Rishee Jain", institution: "Stanford University" },
  { name: "Dinesh Moorjani", institution: "Stanford University" },
]

const paperFacts = [
  ["7,271", "climate technology companies"],
  ["132,826", "firm-quarter observations"],
  ["22", "quarters from Q1 2020 to Q2 2025"],
  ["6", "IRA provisions tracked live"],
]

const findings = [
  "IRA exposure increased venture entry where incentives directly matched firm technologies.",
  "Investors reacted to statutory specificity, durability, and enforceability, not only subsidy size.",
  "The OBBBA stress window depressed activity in credibility-dependent sectors.",
]

function score(value: number) {
  return value.toFixed(value % 1 === 0 ? 0 : 2)
}

function delta(policy: (typeof POLICIES)[number]) {
  return policy.stress - policy.baseline
}

function pct(value: number) {
  return `${Math.round((value / 5) * 100)}%`
}

export default function AboutPage() {
  return (
    <main className="academic-page min-h-screen bg-white text-zinc-950">
      <SiteHeader />

      <header className="academic-header compact">
        <p className="academic-kicker">Policy Credibility Index</p>
        <h1>
          Industrial policy reshapes venture capital allocation and growth
          trajectories in climate technologies
        </h1>

        <div className="academic-authors" aria-label="Authors">
          {authors.map((author) => (
            <div key={author.name}>
              <div className="academic-author-name">{author.name}</div>
              <div className="academic-institution">{author.institution}</div>
            </div>
          ))}
        </div>

        <p className="academic-venue">Research article companion / May 2026</p>

        <div className="academic-link-row" aria-label="Project links">
          <a className="academic-pill-link" href="https://github.com/yudduy/pci-realtime/blob/main/Research_report.pdf">
            Paper
          </a>
          <a className="academic-pill-link" href="https://github.com/yudduy/pci-realtime/blob/main/SI_Appendix.pdf">
            SI Appendix
          </a>
          <Link className="academic-pill-link" href="/dashboard">
            Tracker
          </Link>
          <a className="academic-pill-link" href="https://github.com/yudduy/pci-realtime">
            Code
          </a>
        </div>
      </header>

      <section id="abstract" className="academic-highlight">
        <div className="academic-text-column">
          <h2>Abstract</h2>
          <p>
            Transitioning to a low-carbon economy requires private risk capital,
            but policy scale alone does not explain where that capital moves.
            The paper studies how the U.S. Inflation Reduction Act changed
            venture funding in climate technologies and why the institutional
            credibility of each policy commitment mattered.
          </p>
        </div>
      </section>

      <section className="academic-section">
        <h2>Paper anchors</h2>
        <p>
          The live tracker keeps the paper&apos;s six load-bearing IRA provisions
          intact, then updates only from official policy documents and public
          market data.
        </p>
        <div className="academic-facts" aria-label="Paper facts">
          {paperFacts.map(([value, label]) => (
            <div key={label}>
              <strong>{value}</strong>
              <span>{label}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="academic-wide" aria-labelledby="pci-figure-title">
        <div className="academic-figure">
          <div className="academic-figure-header">
            <div>
              <p className="academic-figure-label">Figure 1</p>
              <h2 id="pci-figure-title">Policy credibility by IRA provision</h2>
            </div>
            <Link className="academic-outline-link" href="/dashboard">
              Open tracker
            </Link>
          </div>

          <div className="pci-table" role="table" aria-label="Policy credibility scores">
            <div className="pci-row pci-head" role="row">
              <div role="columnheader">Provision</div>
              <div role="columnheader">Plain name</div>
              <div role="columnheader">Baseline PCI</div>
              <div role="columnheader">OBBBA stress</div>
              <div role="columnheader">Move</div>
            </div>
            {POLICIES.map((policy) => {
              const move = delta(policy)
              return (
                <div className="pci-row" role="row" key={policy.code}>
                  <div role="cell" className="pci-code">{policy.code}</div>
                  <div role="cell">
                    <strong>{policy.name}</strong>
                    <span>{policy.formalName}</span>
                  </div>
                  <div role="cell">
                    <ScoreBar value={policy.baseline} />
                  </div>
                  <div role="cell">
                    <ScoreBar value={policy.stress} muted />
                  </div>
                  <div role="cell" className={move < 0 ? "pci-move-down" : "pci-move-flat"}>
                    {move === 0 ? "flat" : move.toFixed(2)}
                  </div>
                </div>
              )
            })}
          </div>

          <p className="academic-caption">
            PCI is the simple average of specificity, durability, and
            enforceability. The operational tracker keeps the names readable
            while preserving the paper&apos;s research anchors.
          </p>
        </div>
      </section>

      <section className="academic-section">
        <h2>What the tracker adds</h2>
        <p>
          The paper explains the empirical result. The tracker turns the same
          PCI logic into a weekly production loop: official documents, PCI
          updates, public market matches, forecasts, gated trade proposals, and
          resolved outcomes.
        </p>
        <div className="results-grid">
          {findings.map((finding) => (
            <article key={finding}>
              <h3>Finding</h3>
              <p>{finding}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="citation" className="academic-section">
        <h2>BibTeX</h2>
        <pre className="bibtex-block">{`@article{cao2026industrialpolicy,
  title={Industrial policy reshapes venture capital allocation and growth trajectories in climate technologies},
  author={Cao, Yikai and Eesley, Charles and Jain, Rishee and Moorjani, Dinesh},
  year={2026},
  note={Research article companion}
}`}</pre>
      </section>
    </main>
  )
}

function ScoreBar({ value, muted = false }: { value: number; muted?: boolean }) {
  return (
    <div className="score-bar-wrap">
      <span>{score(value)}</span>
      <div className={muted ? "score-bar score-bar-muted" : "score-bar"}>
        <div style={{ width: pct(value) }} />
      </div>
    </div>
  )
}
