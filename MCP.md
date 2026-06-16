# PCIndex MCP

PCIndex exposes a local MCP server for policy agents that need to read the
registry and submit cited evidence. It is the intended path for agent intake;
`data/fixtures/agent_evidence_seed.json` is only a bootstrap fixture.

## What It Does

The MCP server lets an agent:

- Check registry status with `status`.
- List the tracked policy units with `list_policies`.
- Read current scores with `current_pci`.
- Read policy evidence with `policy_dossier` and `get_evidence_trace`.
- Submit a public source citation with `submit_policy_evidence`.
- Fetch a public URL for citation extraction with `ingest_source_url`.

Write tools require the hosted Supabase project to include
`supabase/migrations/005_agent_evidence_intake.sql`. Without that migration,
read tools still work, but writes stop with a clear setup error.

For a human-facing setup page, use `/connect` on the public web app.

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

## Current Product Gap

DeepWiki provides a hosted remote MCP endpoint. PCIndex currently provides a
local stdio MCP server because write access requires service-role Supabase
credentials and scorer credentials. For nontechnical users, the next product
step is a hosted authenticated MCP endpoint, for example:

```text
https://pcindex.vercel.app/mcp
```

That endpoint should use OAuth or scoped API keys, never browser publishable
keys, and should preserve the same `submit_policy_evidence` validation rules.
