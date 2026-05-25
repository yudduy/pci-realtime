import Link from "next/link"
import { POLICIES } from "@/lib/policy-copy"

const stats = [
  ["7,271", "climate tech companies"],
  ["132,826", "firm-quarter observations"],
  ["6", "IRA provisions tracked live"],
]

const loop = [
  ["Official documents", "Federal policy text, not news sentiment"],
  ["PCI scoring", "Specific, durable, enforced"],
  ["Weekly series", "Sticky credibility on a 1-5 scale"],
  ["Market match", "Only clean public markets"],
  ["Live monitor", "Forecasts, trades, outcomes"],
]

const results = [
  ["IRA targeted capital", "VC response rose most where statutory incentives directly applied."],
  ["Credibility mattered", "Investors reacted to design quality, not only subsidy size."],
  ["OBBBA stress test", "Credibility shocks predicted sharper contractions in exposed sectors."],
]

function score(value: number) {
  return value.toFixed(value % 1 === 0 ? 0 : 2)
}

function delta(policy: (typeof POLICIES)[number]) {
  return policy.stress - policy.baseline
}

export default function Home() {
  return (
    <main className="min-h-screen bg-background">
      <div className="mx-auto max-w-6xl px-5 py-4 lg:px-8">
        <div className="mb-4 text-center text-xs text-muted-foreground">
          Best viewed on a desktop browser. The live monitor uses hover states and wide policy cards.
        </div>

        <nav className="sticky top-0 z-40 -mx-5 mb-10 border-b border-border bg-background/95 px-5 py-3 backdrop-blur lg:-mx-8 lg:px-8">
          <div className="mx-auto flex max-w-6xl items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue text-sm font-black text-white">
                PCI
              </div>
              <div>
                <div className="font-bold">Policy Credibility Index</div>
                <div className="text-xs text-muted-foreground">Research companion</div>
              </div>
            </div>
            <div className="hidden items-center gap-2 md:flex">
              <a className="landing-nav-link" href="#monitor">Monitor</a>
              <a className="landing-nav-link" href="#approach">Approach</a>
              <a className="landing-nav-link" href="#results">Results</a>
              <Link className="rounded-full bg-blue px-4 py-2 text-sm font-bold text-white" href="/dashboard">
                Live monitor
              </Link>
            </div>
          </div>
        </nav>

        <section className="grid gap-8 pb-12 lg:grid-cols-[1fr_390px] lg:items-start">
          <div>
            <div className="mb-3 text-sm font-bold uppercase text-blue">
              Companion to the IRA venture-capital paper
            </div>
            <h1 className="max-w-3xl text-4xl font-black leading-[1.02] tracking-normal md:text-6xl">
              A live monitor for policy credibility.
            </h1>
            <p className="mt-5 max-w-2xl text-lg leading-8 text-muted-foreground">
              The paper shows that clean-energy investment depends on how credible policy commitments are. This site turns the paper&apos;s two PCI snapshots into a weekly, inspectable monitor.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <Link className="rounded-full bg-blue px-5 py-3 text-sm font-bold text-white" href="/dashboard">
                Open live monitor
              </Link>
              <a className="rounded-full bg-card px-5 py-3 text-sm font-bold text-foreground ring-1 ring-border" href="#approach">
                See method
              </a>
            </div>
            <div className="mt-8 grid max-w-2xl grid-cols-1 gap-3 sm:grid-cols-3">
              {stats.map(([value, label]) => (
                <div key={label} className="rounded-xl border border-border bg-card p-4">
                  <div className="text-2xl font-black">{value}</div>
                  <div className="mt-1 text-sm text-muted-foreground">{label}</div>
                </div>
              ))}
            </div>
          </div>

          <section className="rounded-xl border border-border bg-card p-4">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-black">Paper anchor</h2>
                <p className="text-sm text-muted-foreground">Baseline to OBBBA stress</p>
              </div>
              <span className="rounded-full bg-blue-soft px-3 py-1 text-xs font-bold text-blue">
                1-5 scale
              </span>
            </div>
            <div className="space-y-2">
              {POLICIES.map((policy) => (
                <div key={policy.code} className="rounded-lg bg-muted p-3">
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate font-bold">{policy.name}</div>
                      <div className="text-xs text-muted-foreground">{policy.code}</div>
                    </div>
                    <div className={`rounded-full px-2.5 py-1 text-xs font-bold ${delta(policy) < 0 ? "bg-red-soft text-red" : "bg-muted text-muted-foreground"}`}>
                      {delta(policy) === 0 ? "flat" : delta(policy).toFixed(2)}
                    </div>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-card">
                    <div
                      className="h-full rounded-full bg-blue"
                      style={{ width: `${(policy.baseline / 5) * 100}%` }}
                    />
                  </div>
                  <div className="mt-1 flex justify-between text-xs text-muted-foreground">
                    <span>Baseline {score(policy.baseline)}</span>
                    <span>Stress {score(policy.stress)}</span>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </section>

        <section id="monitor" className="border-t border-border py-12">
          <div className="mb-5 flex flex-col justify-between gap-3 md:flex-row md:items-end">
            <div>
              <h2 className="text-3xl font-black">Monitor</h2>
              <p className="mt-2 max-w-2xl text-muted-foreground">
                The live board is the operational companion: it shows current PCI, policy moves, matched markets, forecasts, gated trades, and resolved outcomes when real rows exist.
              </p>
            </div>
            <Link className="w-fit rounded-full bg-blue px-5 py-3 text-sm font-bold text-white" href="/dashboard">
              Launch dashboard
            </Link>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            {POLICIES.slice(0, 3).map((policy) => (
              <article key={policy.code} className="market-card min-h-0">
                <div className="flex items-center gap-3 border-b border-border bg-muted/50 p-3">
                  <div className="flex h-11 w-12 shrink-0 items-center justify-center rounded-lg bg-blue text-xs font-black text-white">
                    {policy.code}
                  </div>
                  <div>
                    <div className="text-xs font-bold uppercase text-muted-foreground">{policy.lane}</div>
                    <div className="font-bold">{policy.name}</div>
                  </div>
                </div>
                <div className="p-4">
                  <h3 className="market-title min-h-0">{policy.question}</h3>
                  <div className="mt-4 grid grid-cols-2 gap-2">
                    <div className="odds-button odds-button-strong">
                      <div className="text-[11px] font-bold uppercase">Now</div>
                      <div className="mt-1 text-base font-black">{score(policy.baseline)}</div>
                    </div>
                    <div className="odds-button">
                      <div className="text-[11px] font-bold uppercase">Stress</div>
                      <div className="mt-1 text-base font-black">{score(policy.stress)}</div>
                    </div>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section id="approach" className="border-t border-border py-12">
          <h2 className="text-3xl font-black">Approach</h2>
          <p className="mt-2 max-w-3xl text-muted-foreground">
            PCI measures institutional design quality. It is not investor sentiment and it is not a news index.
          </p>
          <div className="mt-6 grid gap-3 md:grid-cols-3">
            <DimensionCard title="Specific" body="Are eligibility rules clear enough to reduce discretion?" />
            <DimensionCard title="Durable" body="Is the commitment insulated over the investment horizon?" />
            <DimensionCard title="Enforced" body="Is implementation assigned to a clear agency process?" />
          </div>

          <div className="mt-8 rounded-xl border border-border bg-card p-4">
            <h3 className="mb-4 text-lg font-black">Live pipeline</h3>
            <div className="grid gap-3 lg:grid-cols-5">
              {loop.map(([title, body], index) => (
                <div key={title} className="relative rounded-lg bg-muted p-4">
                  <div className="mb-2 flex h-7 w-7 items-center justify-center rounded-full bg-blue text-xs font-black text-white">
                    {index + 1}
                  </div>
                  <div className="font-bold">{title}</div>
                  <div className="mt-1 text-sm text-muted-foreground">{body}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="results" className="border-t border-border py-12">
          <h2 className="text-3xl font-black">What the paper establishes</h2>
          <div className="mt-6 grid gap-3 md:grid-cols-3">
            {results.map(([title, body]) => (
              <div key={title} className="rounded-xl border border-border bg-card p-5">
                <h3 className="text-lg font-black">{title}</h3>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">{body}</p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </main>
  )
}

function DimensionCard({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <h3 className="text-lg font-black">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">{body}</p>
    </div>
  )
}
