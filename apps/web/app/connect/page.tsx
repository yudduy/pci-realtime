import type { Metadata } from "next"
import { CopyBlock } from "@/components/connect/copy-block"
import { SiteHeader } from "@/components/layout/site-header"

export const metadata: Metadata = {
  title: "Connect PCIndex MCP",
  description:
    "MCP server reference for connecting trusted agents to the PCIndex policy evidence registry.",
}

const localServerCommand =
  "uv run --extra dev python -m pci_realtime.mcp_server"

const hostedUrl = "https://pcindex.vercel.app/mcp"

const setupCommand =
  "git clone https://github.com/yudduy/pci-realtime && cd pci-realtime && uv sync --extra dev"

const claudeHostedCommand =
  `claude mcp add -s user -t http pcindex ${hostedUrl}`

const codexHostedCommand =
  `codex mcp add pcindex --url ${hostedUrl}`

const claudeLocalCommand =
  'claude mcp add -s user pcindex -- bash -lc "cd \\"$(pwd)\\" && uv run --extra dev python -m pci_realtime.mcp_server"'

const codexLocalCommand =
  'codex mcp add pcindex -- bash -lc "cd \\"$(pwd)\\" && uv run --extra dev python -m pci_realtime.mcp_server"'

const genericLocalConfig = `{
  "mcpServers": {
    "pcindex": {
      "command": "bash",
      "args": [
        "-lc",
        "cd \\"$(pwd)\\" && uv run --extra dev python -m pci_realtime.mcp_server"
      ]
    }
  }
}`

const genericHostedConfig = `{
  "mcpServers": {
    "pcindex": {
      "serverUrl": "${hostedUrl}"
    }
  }
}`

const tools = [
  {
    name: "status",
    signature: "status()",
    mode: "read",
    purpose: "Check registry reachability and connector readiness.",
  },
  {
    name: "list_verticals",
    signature: "list_verticals()",
    mode: "read",
    purpose: "List the five scored climate-tech verticals and weighted PCI status.",
  },
  {
    name: "vertical_status",
    signature: "vertical_status(vertical_id)",
    mode: "read",
    purpose: "Read one vertical with its underlying provision-level status.",
  },
  {
    name: "list_changes",
    signature: "list_changes(since?, vertical?, limit=50)",
    mode: "read",
    purpose: "List cited policy changes using the public delivery contract.",
  },
  {
    name: "list_policies",
    signature: "list_policies()",
    mode: "read",
    purpose: "Return the six provisions used as underlying scoring units.",
  },
  {
    name: "current_pci",
    signature: "current_pci(code?)",
    mode: "read",
    purpose: "Read the current PCI score for one policy or all policies.",
  },
  {
    name: "policy_dossier",
    signature: "policy_dossier(code)",
    mode: "read",
    purpose: "Read policy events, evidence rows, and registry state.",
  },
  {
    name: "get_evidence_trace",
    signature: "get_evidence_trace(provision, evidence_id?)",
    mode: "read",
    purpose: "Verify source links and evidence that entered the registry.",
  },
]

export default function ConnectPage() {
  return (
    <main className="connect-page">
      <SiteHeader />

      <section className="connect-hero">
        <div>
          <p className="eyebrow">PCIndex MCP</p>
          <h1>Connect an agent to PCIndex</h1>
          <p>
            The website is the public terminal. The hosted MCP endpoint gives
            agents read access; trusted operators can run the local connector
            when they need evidence intake.
          </p>
        </div>
      </section>

      <section className="connect-layout">
        <div className="connect-main">
          <section className="terminal-panel connect-answer-card">
            <div className="connect-answer-grid">
              <div>
                <p className="eyebrow">Recommended today</p>
                <h2>Use hosted read access; keep writes local.</h2>
                <p>
                  External agents can read PCIndex directly from the hosted MCP
                  URL. Registry-changing tools stay in the configured local
                  runtime until authentication and review controls are added.
                </p>
              </div>
              <div className="connect-status-stack" aria-label="Connector status">
                <span>Hosted read MCP: live</span>
                <span>Local write MCP: ready</span>
              </div>
            </div>
          </section>

          <section className="terminal-panel connect-server-card">
            <div className="section-heading">
              <p>Quick start</p>
              <h2>Hosted read connector</h2>
            </div>
            <ol className="connect-steps">
              <li>
                <strong>Add PCIndex.</strong>
                <span>Register the hosted MCP URL in your agent client.</span>
              </li>
              <li>
                <strong>Use read tools.</strong>
                <span>Ask for vertical status, provision detail, or evidence traces.</span>
              </li>
              <li>
                <strong>Keep intake local.</strong>
                <span>Write-capable evidence intake remains operator-only.</span>
              </li>
            </ol>
            <div className="connect-quick-grid">
              <CopyBlock label="Claude Code" value={claudeHostedCommand} />
              <CopyBlock label="Codex CLI" value={codexHostedCommand} />
            </div>
          </section>

          <section className="terminal-panel">
            <div className="section-heading">
              <p>Current setup</p>
              <h2>What is live</h2>
            </div>
            <div className="connect-choice-grid">
              <ProtocolCard
                label="Use now"
                title="Hosted read MCP"
                status="Live"
                body="Works from MCP clients that support Streamable HTTP. Exposes read-only policy and evidence tools."
                code={hostedUrl}
              />
              <ProtocolCard
                label="Trusted operators"
                title="Local write MCP"
                status="Ready"
                body="Runs from the repository checkout and keeps evidence intake inside the configured PCIndex runtime."
                code={localServerCommand}
              />
            </div>
          </section>

          <section className="terminal-panel">
            <div className="section-heading">
              <p>Tool surface</p>
              <h2>Functions the agent gets</h2>
            </div>
            <div className="connect-tool-list">
              {tools.map((tool, index) => (
                <article key={tool.name}>
                  <span>{index + 1}</span>
                  <div>
                    <div className="connect-tool-head">
                      <code>{tool.signature}</code>
                      <em data-mode={tool.mode}>{tool.mode}</em>
                    </div>
                    <p>{tool.purpose}</p>
                  </div>
                </article>
              ))}
            </div>
          </section>

          <section className="terminal-panel connect-command-panel">
            <div className="section-heading">
              <p>Manual config</p>
              <h2>Generic hosted config</h2>
            </div>
            <p className="connect-lede">
              Use this when your agent client accepts remote MCP server JSON.
            </p>
            <CopyBlock label="Generic hosted MCP config" value={genericHostedConfig} language="json" />
          </section>

          <section className="terminal-panel connect-command-panel">
            <div className="section-heading">
              <p>Evidence intake</p>
              <h2>Local write connector</h2>
            </div>
            <p className="connect-lede">
              Use this only for trusted operators who need to submit cited
              evidence into the registry.
            </p>
            <CopyBlock label="Get PCIndex" value={setupCommand} />
            <div className="connect-quick-grid">
              <CopyBlock label="Claude Code local" value={claudeLocalCommand} />
              <CopyBlock label="Codex CLI local" value={codexLocalCommand} />
            </div>
            <CopyBlock label="Generic local MCP config" value={genericLocalConfig} language="json" />
          </section>
        </div>
      </section>
    </main>
  )
}

function ProtocolCard({
  label,
  title,
  status,
  body,
  code,
}: {
  label: string
  title: string
  status: string
  body: string
  code: string
}) {
  return (
    <article className="connect-protocol-card">
      <div>
        <span>{label}</span>
        <strong>{status}</strong>
      </div>
      <h3>{title}</h3>
      <p>{body}</p>
      <code>{code}</code>
    </article>
  )
}
