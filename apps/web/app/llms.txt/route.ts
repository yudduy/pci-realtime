const baseUrl = "https://pcindex.vercel.app"
const repoUrl = "https://github.com/yudduy/pci-realtime"

export const dynamic = "force-static"

export function GET() {
  const body = `# PCIndex Docs

## Public Product
- [Homepage](${baseUrl}/): Live Policy Credibility Index overview.
- [Terminal](${baseUrl}/dashboard): Policy-unit register, source freshness, and evidence state.
- [About](${baseUrl}/about): Methodology companion for PCI scoring.

## Agent Setup
- [Connect](${baseUrl}/connect): Human-facing setup page for trusted agents that read the PCIndex registry and submit cited evidence.
- [Hosted MCP](${baseUrl}/mcp): Read-only Streamable HTTP MCP endpoint for policy status, dossiers, and evidence traces.
- [PCIndex MCP](${repoUrl}/blob/main/MCP.md): How agents connect to the PCIndex MCP server and submit cited evidence.
- [Repository README](${repoUrl}/blob/main/README.md): Build, registry, web app, and operator guide.
- [Contributor guide](${repoUrl}/blob/main/AGENTS.md): Repository structure, commands, tests, and contribution rules.

## Registry Interfaces
- [MCP server source](${repoUrl}/blob/main/src/pci_realtime/mcp_server.py): Read and write tools exposed to agents.
- [Agent intake service](${repoUrl}/blob/main/src/pci_realtime/service.py): Registry service layer for evidence intake.

## Tracked Policy Pages
- [30D Clean Vehicle Credit](${baseUrl}/policies/30D)
- [45Q Carbon Oxide Sequestration Credit](${baseUrl}/policies/45Q)
- [45V Clean Hydrogen Production Credit](${baseUrl}/policies/45V)
- [45X Advanced Manufacturing Production Credit](${baseUrl}/policies/45X)
- [50141 Loan Programs Office Funding](${baseUrl}/policies/50141)
- [50144 Energy Infrastructure Reinvestment](${baseUrl}/policies/50144)
`

  return new Response(body, {
    headers: {
      "content-type": "text/plain; charset=utf-8",
    },
  })
}
