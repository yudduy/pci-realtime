import { HOSTED_MCP_URL, REPO_URL, SITE_URL } from "@/lib/site"

const baseUrl = SITE_URL
const repoUrl = REPO_URL

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

## Change Feeds & API
- [All-changes Atom feed](${baseUrl}/feed.xml): Every cited policy-change event, vertical-first.
- Per-vertical Atom feeds: ${baseUrl}/verticals/<vertical-id>/feed.xml (ids: advanced-manufacturing, clean-hydrogen, carbon-capture, electric-vehicles, clean-energy-finance).
- [Changes API](${baseUrl}/api/changes.json): Full JSON snapshot with stable IDs and citations.
- Per-vertical JSON snapshots: ${baseUrl}/api/changes/<vertical-id>.json (ids: advanced-manufacturing, clean-hydrogen, carbon-capture, electric-vehicles, clean-energy-finance).
- Snapshots rebuilt by CI; filter client-side on recorded_at, or use MCP list_changes(since?, vertical?, limit?) for filtered reads.

## Hosted MCP
- [Hosted MCP](${HOSTED_MCP_URL}): Read-only Streamable HTTP endpoint.
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
