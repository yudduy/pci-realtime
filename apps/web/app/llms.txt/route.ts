const baseUrl = "https://pcindex.vercel.app"
const repoUrl = "https://github.com/yudduy/pci-realtime"

export const dynamic = "force-static"

export function GET() {
  const body = `# PCIndex Climate-Tech Vertical Credibility

PCIndex tracks commitment credibility for five scored climate-tech verticals. Statutory provisions are the underlying scoring units and evidence detail within each vertical.

## Scored Verticals
- Advanced Manufacturing (section 45X)
- Clean Hydrogen (section 45V)
- Carbon Capture (section 45Q)
- Electric Vehicles (section 30D)
- Clean Energy Finance (sections 50141 and 50144, combined as a weighted score)

## Public Product
- [Terminal](${baseUrl}/): Vertical-first Policy Credibility Index with provision-level evidence detail.
- [About](${baseUrl}/about): Methodology companion for PCI scoring.

## Change Delivery
- [All changes feed](${baseUrl}/feed.xml): Subscribe to every cited policy change as Atom.
- [Vertical feed](${baseUrl}/verticals/clean-hydrogen/feed.xml): Replace the slug with any scored vertical id to subscribe to that vertical only.
- [Changes JSON API](${baseUrl}/api/changes?since=2026-01-01&limit=50): Filter with since=YYYY-MM-DD, vertical=<slug>, and limit=1..200.

## Hosted MCP
- [Hosted MCP](${baseUrl}/mcp): Read-only Streamable HTTP endpoint.
- Read-only tools: status, list_policies, current_pci, policy_dossier, get_evidence_trace, list_verticals, vertical_status, list_changes.
- [Connect](${baseUrl}/connect): Setup for hosted reads and trusted local evidence intake.
- [Repository README](${repoUrl}/blob/main/README.md): Build, registry, web app, MCP setup, and operator guide.

## Registry Interfaces
- [MCP server source](${repoUrl}/blob/main/src/pci_realtime/mcp_server.py): Local read and write tools exposed to agents.
- [Agent intake service](${repoUrl}/blob/main/src/pci_realtime/service.py): Registry service layer for vertical and provision reads plus evidence intake.

## Underlying Provision Evidence
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
