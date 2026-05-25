import Link from "next/link"
import {
  BarChart3,
  Database,
  FileText,
  Github,
  LineChart,
} from "lucide-react"
import { POLICIES } from "@/lib/policy-copy"

const authors = [
  { name: "Yikai Cao", institution: "Stanford University" },
  { name: "Charles Eesley", institution: "Stanford University" },
  { name: "Rishee Jain", institution: "Stanford University" },
  { name: "Dinesh Moorjani", institution: "Stanford University" },
]

const links = [
  { label: "Paper", href: "#abstract", icon: FileText },
  { label: "Code", href: "https://github.com/yudduy/pci-realtime", icon: Github },
  { label: "Registry", href: "/dashboard", icon: BarChart3, internal: true },
  { label: "Data Flow", href: "#approach", icon: Database },
]

const paperFacts = [
  ["7,271", "climate technology companies"],
  ["132,826", "firm-quarter observations"],
  ["22", "quarters from Q1 2020 to Q2 2025"],
  ["6", "IRA provisions tracked live"],
]

const findings = [
  [
    "Capital moved selectively",
    "IRA exposure increased venture entry where incentives directly matched firm technologies.",
  ],
  [
    "Credibility changed the response",
    "Investors reacted to statutory specificity, durability, and enforceability, not only subsidy size.",
  ],
  [
    "Durability shocks mattered",
    "The OBBBA stress window depressed activity in credibility-dependent sectors.",
  ],
]

const pipeline = [
  ["Official documents", "Federal Register, Treasury, IRS, Congress, and OMB text"],
  ["PCI scoring", "Specificity, durability, and enforceability on a 1-5 scale"],
  ["Market match", "Public Kalshi markets only when the resolution is clean"],
  ["Forecast gates", "Probability, edge, liquidity, confidence, and private-info checks"],
  ["Registry", "Supabase views power the live public dashboard"],
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

export default function Home() {
  return (
    <main className="academic-page min-h-screen bg-white text-zinc-950">
      <div className="academic-mobile-note">
        Best viewed on a desktop browser. Tables and figures use a wide reading column.
      </div>

      <nav className="academic-topbar" aria-label="Project navigation">
        <a href="#abstract">Abstract</a>
        <a href="#approach">Approach</a>
        <a href="#results">Results</a>
        <Link href="/dashboard">Registry</Link>
      </nav>

      <header className="academic-header">
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

        <p className="academic-venue">Research article companion · May 2026</p>

        <div className="academic-link-row" aria-label="Project links">
          {links.map((link) => {
            const Icon = link.icon
            const className = "academic-pill-link"
            const content = (
              <>
                <Icon aria-hidden="true" className="h-5 w-5" />
                <span>{link.label}</span>
              </>
            )

            if (link.internal) {
              return (
                <Link key={link.label} className={className} href={link.href}>
                  {content}
                </Link>
              )
            }

            return (
              <a key={link.label} className={className} href={link.href}>
                {content}
              </a>
            )
          })}
        </div>
      </header>

      <section id="abstract" className="academic-highlight">
        <div className="academic-text-column">
          <h2>Abstract</h2>
          <p>
            Transitioning to a low-carbon economy requires private risk capital,
            but policy scale alone does not explain where that capital moves.
            This project companion follows the paper&apos;s core result: the U.S.
            Inflation Reduction Act increased venture funding in targeted climate
            technologies, and the response depended on the institutional
            credibility of the policy commitment.
          </p>
          <p>
            The live registry extends the paper by turning the Policy Credibility
            Index into an inspectable weekly system. Official policy documents
            update PCI, market matches create forecasts, and trade proposals stay
            gated behind backend risk checks.
          </p>
        </div>
      </section>

      <section className="academic-section">
        <h2>Paper anchor</h2>
        <p>
          The empirical setting covers venture financing around the IRA and an
          OBBBA durability shock. These are the fixed anchors that the live
          product should explain in plain language before users enter the
          dashboard.
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
              Open live registry
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
            enforceability. The dashboard keeps these names readable while
            preserving the research paper&apos;s six load-bearing policy anchors.
          </p>
        </div>
      </section>

      <section id="approach" className="academic-section">
        <h2>Approach</h2>
        <p>
          The backend stays the source of truth. The landing page explains the
          paper; the registry tab shows current PCI, policy moves, market
          matches, forecasts, proposals, and resolved outcomes.
        </p>

        <div className="pipeline-diagram">
          {pipeline.map(([title, body], index) => (
            <div key={title} className="pipeline-step">
              <div className="pipeline-index">{index + 1}</div>
              <h3>{title}</h3>
              <p>{body}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="results" className="academic-section">
        <h2>Results</h2>
        <p>
          The site should not make users parse statutory names first. It should
          start from the paper&apos;s logic, then let users click into live policy
          tracking when they need the operational view.
        </p>

        <div className="results-grid">
          {findings.map(([title, body]) => (
            <article key={title}>
              <LineChart aria-hidden="true" className="h-5 w-5" />
              <h3>{title}</h3>
              <p>{body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="academic-highlight">
        <div className="academic-text-column">
          <h2>Live registry</h2>
          <p>
            The dashboard is the operational layer: current scores, latest
            official policy moves, public market matches, open forecasts, gated
            trade proposals, and outcomes. It remains separate from the landing
            paper so the homepage stays readable.
          </p>
          <Link className="academic-primary-link" href="/dashboard">
            Open registry
          </Link>
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

      <footer className="academic-footer">
        <p>
          Built with a layout adapted from{" "}
          <a href="https://research-template.roman.technology">
            Roman Hauksson-Neill&apos;s project page template
          </a>
          .
        </p>
      </footer>
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
