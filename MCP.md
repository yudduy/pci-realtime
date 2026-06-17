# PCIndex MCP

PCIndex exposes two MCP paths:

- Hosted read-only MCP at `https://pcindex.vercel.app/mcp` for agents that need
  policy status, current PCI, dossiers, and evidence traces.
- Local write-capable MCP for trusted operators that need to submit cited
  evidence into the registry.

The local write path is the intended path for agent intake;
`data/fixtures/agent_evidence_seed.json` is only a bootstrap fixture.

## What It Does

The hosted read-only MCP lets an agent:

- Check registry status with `status`.
- List the tracked policy units with `list_policies`.
- Read current scores with `current_pci`.
- Read policy evidence with `policy_dossier` and `get_evidence_trace`.

The local write-capable MCP additionally lets a trusted operator:

- Submit a public source citation with `submit_policy_evidence`.
- Fetch a public URL for citation extraction with `ingest_source_url`.

Write tools require the hosted Supabase project to include
`supabase/migrations/005_agent_evidence_intake.sql`. Without that migration,
read tools still work, but writes stop with a clear setup error.
`status.write_credentials_configured` only means credentials are present;
`status.write_configured` is true only when the Agent COI views are live too.

For a human-facing setup page, use `/connect` on the public web app.

## Hosted Read-Only Setup

Claude Code:

```bash
claude mcp add -s user -t http pcindex https://pcindex.vercel.app/mcp
```

Codex CLI:

```bash
codex mcp add pcindex --url https://pcindex.vercel.app/mcp
```

Generic remote MCP config:

```json
{
  "mcpServers": {
    "pcindex": {
      "serverUrl": "https://pcindex.vercel.app/mcp"
    }
  }
}
```

## One-Time Owner Setup

Run this inside the repository:

```bash
uv sync --extra dev
cp .env.example .env
```

Fill `.env` with:

```bash
SUPABASE_URL="https://<project>.supabase.co"
SUPABASE_SERVICE_ROLE_KEY="<service-role-key>"
OPENAI_API_KEY="<scoring-key>"
```

Then apply the intake migration in Supabase SQL Editor:

```sql
-- paste contents of supabase/migrations/005_agent_evidence_intake.sql
```

Verify the local MCP server:

```bash
uv run --extra dev python scripts/smoke_mcp.py
```

After migration `005` is applied, verify the write path:

```bash
uv run --extra dev python scripts/smoke_mcp.py --write-smoke
```

Before migration `005`, `--write-smoke` is expected to exit nonzero with:

```text
Agent evidence intake migration is not applied.
```

## Daily Research Scout

The MCP server is an intake surface, not a scheduler. To have an agent gather
new official evidence, run the research scout:

```bash
uv run --extra dev python scripts/run_agent_research_intake.py \
  --since 2026-06-01 \
  --output-path data/debug/agent_research_intake.json
```

Add `--write` only after `status.write_configured` is true:

```bash
uv run --extra dev python scripts/run_agent_research_intake.py --write
```

The production workflow `.github/workflows/production-agent-research-intake.yml`
can run this daily. It stays dry-run by default unless manually dispatched with
`write=true`.

## Transport Modes

Local stdio is the default:

```bash
uv run --extra dev python -m pci_realtime.mcp_server
```

For a hosted or internal HTTP deployment, run the same server with Streamable
HTTP:

```bash
PCINDEX_MCP_TRANSPORT=streamable-http \
PCINDEX_MCP_MOUNT_PATH=/mcp \
uv run --extra dev python -m pci_realtime.mcp_server
```

## Claude Code Setup

```bash
claude mcp add -s user pcindex -- bash -lc 'cd /path/to/pci-realtime && set -a && source .env && set +a && uv run --extra dev python -m pci_realtime.mcp_server'
```

## Codex CLI Setup

```bash
codex mcp add pcindex -- bash -lc 'cd /path/to/pci-realtime && set -a && source .env && set +a && uv run --extra dev python -m pci_realtime.mcp_server'
```

## Generic MCP Config

```json
{
  "mcpServers": {
    "pcindex": {
      "command": "bash",
      "args": [
        "-lc",
        "cd /path/to/pci-realtime && set -a && source .env && set +a && uv run --extra dev python -m pci_realtime.mcp_server"
      ]
    }
  }
}
```

Replace `/path/to/pci-realtime` with the absolute path to your checkout.

## Agent Intake Loop

Give the agent this operating instruction:

```text
Use the pcindex MCP server for policy evidence intake.
1. Call status. Continue only if registry_configured is true.
2. Call list_policies and map evidence only to the tracked policy codes.
3. Use primary public sources when possible: IRS, Treasury, Federal Register,
   DOE/LPO, Congress, GovInfo, court records, or official agency pages.
4. Before writing, identify the exact public URL, source title, quote anchor,
   policy code, and claim.
5. Call submit_policy_evidence with a deterministic idempotency_key.
6. Call get_evidence_trace to verify the evidence and source link.
7. Call policy_dossier to confirm the policy page has the updated evidence.
```

Example `submit_policy_evidence` payload:

```json
{
  "provision": "45V",
  "source": {
    "url": "https://www.irs.gov/credits-deductions/clean-hydrogen-production-credit",
    "title": "Clean Hydrogen Production Credit",
    "source_name": "Internal Revenue Service",
    "published_at": "2026-01-01"
  },
  "citation": {
    "quote": "provides a production credit for each kilogram of qualified clean hydrogen",
    "section": "Overview"
  },
  "claim": "IRS guidance confirms section 45V remains tied to qualified clean hydrogen production and emissions intensity.",
  "idempotency_key": "irs-45v-clean-hydrogen-credit-overview",
  "agent_name": "policy-research-agent",
  "question": "Does current IRS guidance update the 45V policy credibility state?"
}
```

## Hosted Write Gap

DeepWiki-style hosted read access is live at:

```text
https://pcindex.vercel.app/mcp
```

Hosted write access is intentionally not live. It should use OAuth or scoped API
keys, audit every submitter, enforce rate limits, and preserve the same
`submit_policy_evidence` validation rules before it is exposed remotely.
