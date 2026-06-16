import type { Metadata } from "next"
import { CopyBlock } from "@/components/connect/copy-block"
import { SiteHeader } from "@/components/layout/site-header"

export const metadata: Metadata = {
  title: "PCIndex MCP Server",
  description:
    "MCP setup and tool reference for reading PCIndex policy dossiers and submitting source-cited evidence.",
}

const claudeCommand =
  'claude mcp add -s user pcindex -- bash -lc "cd \\"$(pwd)\\" && uv run --extra dev python -m pci_realtime.mcp_server"'

const codexCommand =
  'codex mcp add pcindex -- bash -lc "cd \\"$(pwd)\\" && uv run --extra dev python -m pci_realtime.mcp_server"'

const connectionDetails = [
  ["Server name", "pcindex"],
  ["Transport", "Local stdio"],
  ["Run from", "PCIndex repository root"],
  ["Server command", "uv run --extra dev python -m pci_realtime.mcp_server"],
]

const toolReference = [
  {
    name: "status",
    mode: "read",
    signature: "status()",
    purpose: "Check registry reachability and write readiness.",
    parameters: "none",
    returns: "reachable, registry_configured, write_configured, tracked_policies",
  },
  {
    name: "list_policies",
    mode: "read",
    signature: "list_policies()",
    purpose: "List the six tracked IRA policy units.",
    parameters: "none",
    returns: "policy code, name, type, primary channel, baseline PCI",
  },
  {
    name: "current_pci",
    mode: "read",
    signature: "current_pci(code?)",
    purpose: "Read current PCI scores for one policy or all policies.",
    parameters: "code is optional; use values like 45V, 45Q, 30D",
    returns: "current PCI, dimensions, weekly delta, update timestamp",
  },
  {
    name: "policy_dossier",
    mode: "read",
    signature: "policy_dossier(code)",
    purpose: "Read the policy page backing data for a tracked unit.",
    parameters: "code is required",
    returns: "policy state, events, evidence rows, contributor submissions",
  },
  {
    name: "get_evidence_trace",
    mode: "read",
    signature: "get_evidence_trace(provision, evidence_id?)",
    purpose: "Verify citation links and scored evidence before using an update.",
    parameters: "provision is required; evidence_id is optional",
    returns: "evidence rows, source links, policy events",
  },
  {
    name: "submit_policy_evidence",
    mode: "write",
    signature:
      "submit_policy_evidence(provision, source, citation, claim, idempotency_key, agent_run_id?, agent_name?, question?)",
    purpose: "Submit a public, quote-backed source for validation and scoring.",
    parameters: "provision, source metadata, citation quote, claim, idempotency key",
    returns: "submission status, source document id, evidence id, score event ids",
  },
  {
    name: "ingest_source_url",
    mode: "write",
    signature:
      "ingest_source_url(provision, url, rationale, idempotency_key, agent_run_id?, agent_name?, question?)",
    purpose: "Fetch a public URL server-side, extract text, and submit it as evidence.",
    parameters: "provision, URL, rationale, idempotency key",
    returns: "submission status, extracted citation, evidence trace ids",
  },
]

export default function ConnectPage() {
  return (
    <main className="connect-page">
      <SiteHeader />

      <section className="connect-hero">
        <div>
          <p className="eyebrow">MCP Server Documentation</p>
          <h1>PCIndex MCP Server</h1>
          <p>
            Programmatic access to the policy credibility registry: read policy
            dossiers, inspect citation traces, and submit public evidence for
            validated scoring.
          </p>
        </div>
      </section>

      <section className="connect-layout">
        <div className="connect-main">
          <section className="terminal-panel">
            <div className="section-heading">
              <p>Getting started</p>
              <h2>Connection details</h2>
            </div>
            <dl className="connect-detail-grid">
              {connectionDetails.map(([label, value]) => (
                <div key={label}>
                  <dt>{label}</dt>
                  <dd>
                    <code>{value}</code>
                  </dd>
                </div>
              ))}
            </dl>
          </section>

          <section className="terminal-panel connect-command-panel">
            <div className="section-heading">
              <p>Setup instructions</p>
              <h2>Add PCIndex to your client</h2>
            </div>
            <CopyBlock label="Claude Code command" value={claudeCommand} />
            <CopyBlock label="Codex CLI command" value={codexCommand} />
          </section>

          <section className="terminal-panel">
            <div className="section-heading">
              <p>Available tools</p>
              <h2>Tool reference</h2>
            </div>
            <div className="connect-tool-reference">
              {toolReference.map((tool) => (
                <article key={tool.name}>
                  <div className="connect-tool-head">
                    <code>{tool.signature}</code>
                    <span data-mode={tool.mode}>{tool.mode}</span>
                  </div>
                  <p>{tool.purpose}</p>
                  <div className="connect-tool-meta">
                    <span>Parameters</span>
                    <strong>{tool.parameters}</strong>
                    <span>Returns</span>
                    <strong>{tool.returns}</strong>
                  </div>
                </article>
              ))}
            </div>
          </section>
        </div>

      </section>
    </main>
  )
}
