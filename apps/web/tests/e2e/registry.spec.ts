import { expect, test } from "@playwright/test"

test("renders the policy terminal as the home page", async ({ page }) => {
  await page.goto("/")

  await expect(page.getByRole("heading", { name: "Climate-tech credibility by vertical" })).toBeVisible()
  await expect(page.getByRole("button", { name: "About this terminal" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Read about the paper" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Evidence moving the index" })).toBeVisible()
  await expect(page.locator(".terminal-updates-carousel")).toContainText("Clean hydrogen production credit guidance")
  await expect(page.locator(".terminal-updates-carousel")).not.toContainText("Advanced Manufacturing Production Credit")
  await expect(page.getByText("Climate-Tech Vertical Ledger", { exact: true })).toBeVisible()
  await expect(
    page.getByTestId("vertical-card").filter({ hasText: "Electric Vehicles" }),
  ).toBeVisible()
  await expect(page.getByRole("link", { name: "Open terminal" })).toHaveCount(0)
  await expect(page.locator(".policy-compare-table")).toHaveCount(0)
  await expect(page.getByRole("button", { name: "Compact" })).toHaveCount(0)
  await expect(page.getByText("Source coverage")).toHaveCount(0)
  await expect(page.getByText("PCI headlines")).toHaveCount(0)
  await expect(
    page.getByRole("heading", { name: "Live evidence for climate policy credibility." }),
  ).toHaveCount(0)
  await expect(page.getByText("Registry Trace")).toHaveCount(0)
  await expect(page.getByText("Source ledger")).toHaveCount(0)
  await expect(page.locator("[aria-label='Policy credibility trend']")).toHaveCount(0)
  await expect(page.getByText("Cited evidence")).toHaveCount(0)
  await expect(page.getByText("Trajectory")).toHaveCount(0)
  await expect(page.getByText("Data updated")).toHaveCount(0)
  const content = await page.content()
  expect(content).not.toMatch(/rules, notices, agency guidance|tax-credit guidance, forms, FAQs|statutes, amendments, committee movement/i)
  expect(content).not.toMatch(/supabase/i)
  expect(content).not.toMatch(new RegExp("autonom" + "ous", "i"))
  expect(content).not.toMatch(new RegExp("absta" + "in", "i"))
  expect(content).not.toMatch(/preview dataset|gate|agent readiness|official source pending|pci signal|prediction mode/i)
})

test("renders the methodology companion with policy dimensions", async ({ page }) => {
  await page.goto("/about")

  await expect(
    page.getByRole("heading", {
      name: "Whether industrial policy mobilizes private capital depends on the credibility of its commitments",
    }),
  ).toBeVisible()
  await expect(page.getByText("7,271")).toBeVisible()
  await expect(page.getByText("132,826")).toBeVisible()
  await expect(page.getByRole("heading", { name: "Paper anchors" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Policy credibility by unit" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "What the terminal adds" })).toBeVisible()
  await expect(page.getByRole("columnheader", { name: "Specificity" })).toBeVisible()
  await expect(page.getByRole("columnheader", { name: "Durability" })).toBeVisible()
  await expect(page.getByRole("columnheader", { name: "Enforceability" })).toBeVisible()
  await expect(page.getByText("source citations, and source freshness")).toBeVisible()
  await expect(page.getByRole("heading", { name: "BibTeX" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Terminal" }).first()).toBeVisible()
  await expect(page.getByRole("link", { name: "Paper", exact: true })).toHaveAttribute(
    "href",
    "/paper.pdf",
  )
  await expect(page.getByRole("link", { name: "SI Appendix" })).toHaveAttribute(
    "href",
    "/si-appendix.pdf",
  )
  expect(await page.content()).not.toMatch(/supabase/i)
})

test("renders the agent connection setup without secrets", async ({ page }) => {
  await page.goto("/connect")

  await expect(
    page.getByRole("heading", { name: "Connect an agent to PCIndex" }),
  ).toBeVisible()
  await expect(page.getByRole("heading", { name: "Use hosted read access; keep writes local." })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Hosted read connector" })).toBeVisible()
  await expect(page.getByText("Hosted read MCP: live")).toBeVisible()
  await expect(page.getByText("Local write MCP: ready")).toBeVisible()
  await expect(page.getByText("Add PCIndex.")).toBeVisible()
  await expect(page.getByText("Use read tools.")).toBeVisible()
  await expect(page.getByText("Keep intake local.")).toBeVisible()
  await expect(page.getByRole("heading", { name: "What is live" })).toBeVisible()
  await expect(page.getByText("Hosted read MCP", { exact: true })).toBeVisible()
  await expect(page.getByText("Local write MCP", { exact: true })).toBeVisible()
  await expect(page.getByText("Live", { exact: true })).toBeVisible()
  await expect(page.getByText("Ready", { exact: true })).toBeVisible()
  await expect(page.locator(".connect-protocol-card", { hasText: "Hosted read MCP" })).toContainText(
    "https://pcindex.vercel.app/mcp",
  )
  await expect(page.locator(".connect-protocol-card", { hasText: "Local write MCP" })).toContainText(
    "uv run --extra dev python -m pci_realtime.mcp_server",
  )
  await expect(page.getByRole("heading", { name: "Generic hosted config" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Local write connector" })).toBeVisible()
  await expect(page.getByText("Functions the agent gets")).toBeVisible()
  await expect(page.getByText("status()")).toBeVisible()
  await expect(page.getByText("list_policies()")).toBeVisible()
  await expect(page.getByText("current_pci(code?)")).toBeVisible()
  await expect(page.getByText("policy_dossier(code)")).toBeVisible()
  await expect(page.getByText("get_evidence_trace(provision, evidence_id?)")).toBeVisible()
  await expect(page.getByText("list_changes(since?, vertical?, limit?)")).toBeVisible()
  await expect(page.getByText("submit_policy_evidence(...)")).toHaveCount(0)
  await expect(page.getByText("ingest_source_url(...)")).toHaveCount(0)
  await expect(page.getByText("Claude Code", { exact: true })).toBeVisible()
  await expect(page.getByText("Codex CLI", { exact: true })).toBeVisible()
  await expect(page.getByText(`claude mcp add -s user -t http pcindex https://pcindex.vercel.app/mcp`)).toBeVisible()
  await expect(page.getByText(`codex mcp add pcindex --url https://pcindex.vercel.app/mcp`)).toBeVisible()
  await expect(page.getByText("Generic hosted MCP config")).toBeVisible()
  await expect(page.getByText("Generic local MCP config")).toBeVisible()
  await expect(page.getByText("Get PCIndex")).toBeVisible()
  await expect(page.getByText("git clone https://github.com/yudduy/pci-realtime")).toBeVisible()
  await expect(page.getByText("claude mcp add -s user pcindex")).toBeVisible()
  await expect(page.getByText("codex mcp add pcindex -- bash")).toBeVisible()
  await expect(page.getByText("Streamable HTTP server command")).toHaveCount(0)
  await expect(page.getByText("PCINDEX_MCP_TRANSPORT=streamable-http")).toHaveCount(0)
  await expect(page.getByText("Generic MCP client")).toHaveCount(0)
  await expect(page.getByText("Policy evidence brief")).toHaveCount(0)
  await expect(page.getByText("Use the PCIndex connector named pcindex.")).toHaveCount(0)
  await expect(page.getByText("Connector workflow")).toHaveCount(0)
  await expect(page.getByText("Supported agents")).toHaveCount(0)
  await expect(page.getByText("Agent instruction")).toHaveCount(0)
  await expect(page.getByText("Setup checklist")).toHaveCount(0)
  await expect(page.getByText("Environment")).toHaveCount(0)
  await expect(page.getByText("Reads")).toHaveCount(0)
  await expect(page.getByText("Safety boundary")).toHaveCount(0)

  const content = await page.content()
  expect(content).not.toMatch(/sb_secret_|sb_publishable_|sk-proj-/i)
  expect(content).not.toMatch(/[a-z0-9]{20}\.supabase\.co/i)
  expect(content).not.toMatch(/\/Users\/[a-z-]+\//i)
  expect(content).not.toMatch(/SUPABASE_|service-role|005_agent_evidence_intake|scripts\/smoke_mcp|--write-smoke|\.env|public browser app stays read-only/i)
  expect(content).not.toMatch(/\/path\/to|Copy the setup block/i)

  const fitsViewport = await page.evaluate(
    () => document.documentElement.scrollWidth <= window.innerWidth + 1,
  )
  expect(fitsViewport).toBe(true)
})

test("exposes the hosted read-only MCP endpoint", async ({ request }) => {
  const initializeResponse = await request.post("/mcp", {
    headers: { accept: "application/json, text/event-stream" },
    data: {
      jsonrpc: "2.0",
      id: 1,
      method: "initialize",
      params: {
        protocolVersion: "2025-03-26",
        capabilities: {},
        clientInfo: { name: "pcindex-e2e", version: "0.1.0" },
      },
    },
  })

  expect(initializeResponse.status()).toBeLessThan(500)
  const initializeBody = await initializeResponse.text()
  expect(initializeBody).toContain("pcindex")

  const sessionId = initializeResponse.headers()["mcp-session-id"]
  const listResponse = await request.post("/mcp", {
    headers: {
      accept: "application/json, text/event-stream",
      ...(sessionId ? { "mcp-session-id": sessionId } : {}),
    },
    data: {
      jsonrpc: "2.0",
      id: 2,
      method: "tools/list",
      params: {},
    },
  })

  expect(listResponse.status()).toBeLessThan(500)
  const payload = parseMcpResponse(await listResponse.text())
  expect(payload.result.tools.map((tool: { name: string }) => tool.name)).toEqual([
    "status",
    "list_policies",
    "current_pci",
    "policy_dossier",
    "get_evidence_trace",
    "list_verticals",
    "vertical_status",
    "list_changes",
  ])

  const verticalsResponse = await request.post("/mcp", {
    headers: {
      accept: "application/json, text/event-stream",
      ...(sessionId ? { "mcp-session-id": sessionId } : {}),
    },
    data: {
      jsonrpc: "2.0",
      id: 3,
      method: "tools/call",
      params: { name: "list_verticals", arguments: {} },
    },
  })
  const verticalsResult = parseMcpResponse(await verticalsResponse.text())
  const verticalsPayload = JSON.parse(verticalsResult.result.content[0].text)
  expect(verticalsPayload.verticals.map((vertical: { id: string }) => vertical.id)).toEqual([
    "advanced-manufacturing",
    "clean-hydrogen",
    "carbon-capture",
    "electric-vehicles",
    "clean-energy-finance",
  ])
  expect(verticalsPayload.source).toBe("registry")

  const statusResponse = await request.post("/mcp", {
    headers: {
      accept: "application/json, text/event-stream",
      ...(sessionId ? { "mcp-session-id": sessionId } : {}),
    },
    data: {
      jsonrpc: "2.0",
      id: 4,
      method: "tools/call",
      params: {
        name: "vertical_status",
        arguments: { vertical_id: "clean-energy-finance" },
      },
    },
  })
  const statusResult = parseMcpResponse(await statusResponse.text())
  const statusPayload = JSON.parse(statusResult.result.content[0].text)
  expect(statusPayload.vertical).toMatchObject({
    id: "clean-energy-finance",
    coverage_note:
      "Tracks DOE Loan Programs Office funding (50141) and Energy Infrastructure Reinvestment authority (50144).",
    vertical_pci: 3.17,
    provisions: ["50141", "50144"],
  })
  expect(statusPayload.provisions.map((policy: { code: string }) => policy.code)).toEqual([
    "50141",
    "50144",
  ])

  const changesResponse = await request.post("/mcp", {
    headers: {
      accept: "application/json, text/event-stream",
      ...(sessionId ? { "mcp-session-id": sessionId } : {}),
    },
    data: {
      jsonrpc: "2.0",
      id: 5,
      method: "tools/call",
      params: { name: "list_changes", arguments: {} },
    },
  })
  const changesResult = parseMcpResponse(await changesResponse.text())
  const changesPayload = JSON.parse(changesResult.result.content[0].text)
  expect(changesPayload.count).toBe(1)
  expect(changesPayload.changes[0].id).toBe(
    "2026-W21:federal_register:45v-guidance:45V",
  )
  expect(changesPayload.changes[0].headline).toMatch(/^Clean Hydrogen:/)

  const filteredChangesResponse = await request.post("/mcp", {
    headers: {
      accept: "application/json, text/event-stream",
      ...(sessionId ? { "mcp-session-id": sessionId } : {}),
    },
    data: {
      jsonrpc: "2.0",
      id: 6,
      method: "tools/call",
      params: {
        name: "list_changes",
        arguments: { vertical: "advanced-manufacturing" },
      },
    },
  })
  const filteredChangesResult = parseMcpResponse(
    await filteredChangesResponse.text(),
  )
  const filteredChangesPayload = JSON.parse(
    filteredChangesResult.result.content[0].text,
  )
  expect(filteredChangesPayload.count).toBe(0)

  const unknownResponse = await request.post("/mcp", {
    headers: {
      accept: "application/json, text/event-stream",
      ...(sessionId ? { "mcp-session-id": sessionId } : {}),
    },
    data: {
      jsonrpc: "2.0",
      id: 7,
      method: "tools/call",
      params: {
        name: "vertical_status",
        arguments: { vertical_id: "geothermal" },
      },
    },
  })
  const unknownResult = parseMcpResponse(await unknownResponse.text())
  expect(unknownResult.result.isError).toBe(true)
  expect(unknownResult.result.content[0].text).toContain(
    "advanced-manufacturing, clean-hydrogen, carbon-capture, electric-vehicles, clean-energy-finance",
  )
})

test("lists the connection page in the agent documentation index", async ({ page }) => {
  await page.goto("/llms.txt")

  await expect(page.getByText("[Connect](https://pcindex.vercel.app/connect)")).toBeVisible()
  await expect(page.getByText("[Hosted MCP](https://pcindex.vercel.app/mcp)")).toBeVisible()
})

test("renders the policy credibility terminal with policy evidence", async ({ page }) => {
  await page.goto("/")

  await expect(page.getByRole("heading", { name: "Climate-tech credibility by vertical" })).toBeVisible()
  await expect(
    page.getByRole("navigation", { name: "Primary navigation" }).getByRole("link", { name: "Terminal" }),
  ).toHaveCount(0)
  await expect(
    page.getByRole("navigation", { name: "Primary navigation" }).getByRole("link", { name: "Connect" }),
  ).toBeVisible()
  await expect(
    page.getByRole("navigation", { name: "Primary navigation" }).getByRole("link", { name: "Paper" }),
  ).toHaveCount(0)
  await expect(page.getByPlaceholder("Search vertical, provision, agency, or document")).toBeVisible()
  await expect(page.getByText("Climate-Tech Vertical Ledger", { exact: true })).toBeVisible()
  await expect(page.getByRole("button", { name: "About this terminal" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Read about the paper" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Evidence moving the index" })).toBeVisible()
  await expect(page.locator(".terminal-updates-carousel")).not.toContainText("Advanced Manufacturing Production Credit")
  await expect(page.getByRole("button", { name: "Previous PCI update" })).toBeVisible()
  await expect(page.getByRole("button", { name: "Next PCI update" })).toBeVisible()
  const sourceLink = page.getByRole("link", { name: "View source" })
  await expect(sourceLink).toBeVisible()
  await expect(sourceLink).toHaveAttribute(
    "href",
    /https:\/\/www\.federalregister\.gov\/documents\/example#:~:text=Treasury%20guidance%20narrows%20eligibility/,
  )
  await page.getByRole("button", { name: "About this terminal" }).click()
  await expect(page.getByRole("dialog", { name: "How to read policy scores" })).toBeVisible()
  await page.getByRole("button", { name: "Close terminal information" }).click()
  await expect(page.getByRole("heading", { name: "Tracked verticals" })).toBeVisible()
  await expect(page.getByText("Fragile")).toHaveCount(0)
  await expect(page.getByText("Mixed")).toHaveCount(0)
  await expect(page.getByText("Strong")).toHaveCount(0)
  await expect(page.getByText("PCI +")).toHaveCount(0)
  await expect(page.getByText("PCI -")).toHaveCount(0)
  await expect(page.getByText("Improving")).toHaveCount(0)
  await expect(page.getByText("Weakening")).toHaveCount(0)
  await expect(page.getByText("No move")).toHaveCount(0)
  await expect(page.getByText("Data updated")).toHaveCount(0)
  await expect(page.locator(".policy-accordion-item")).toHaveCount(6)
  if ((await page.locator(".policy-score-trend").count()) === 0) {
    await page.locator(".policy-accordion-trigger").first().click()
  }
  await expect(page.locator(".policy-score-trend").first()).toBeVisible()
  await expect(page.getByText("Scoring").first()).toBeVisible()
  await expect(page.locator(".policy-source-card").first()).toBeVisible()
  await expect(page.getByRole("columnheader")).toHaveCount(0)
  await expect(page.getByText("Current Brief")).toHaveCount(0)
  await expect(page.getByText("Latest Evidence")).toHaveCount(0)
  await expect(page.getByRole("columnheader", { name: "Weekly Change" })).toHaveCount(0)
  await expect(page.getByRole("columnheader", { name: "Dimensions" })).toHaveCount(0)
  await expect(page.getByRole("columnheader", { name: "Score Inputs" })).toHaveCount(0)
  await expect(page.getByRole("columnheader", { name: "Trajectory" })).toHaveCount(0)
  await expect(page.getByText("Policy basis")).toHaveCount(0)
  await expect(page.getByText("Cited evidence")).toHaveCount(0)
  await expect(page.getByText("Trajectory")).toHaveCount(0)
  await expect(page.getByText("Source ledger")).toHaveCount(0)
  await page.getByPlaceholder("Search vertical, provision, agency, or document").fill("45V")
  await page.locator(".policy-accordion-trigger", { hasText: "45V" }).click()
  await expect(page.locator("[aria-label='45V PCI score trend']")).toBeVisible()
  await expect(page.getByTestId("terminal-trend-point-45V-2026-W21")).toBeVisible()
  await page.getByTestId("terminal-trend-point-45V-2026-W21").hover()
  await expect(page.getByText("Clean hydrogen production credit guidance").first()).toBeVisible()
  await expect(page.locator(".policy-point-attribution")).toContainText("Treasury guidance narrows eligibility for the clean hydrogen credit.")

  const content = await page.content()
  expect(content).not.toMatch(/supabase/i)
  expect(content).not.toMatch(new RegExp("autonom" + "ous", "i"))
  expect(content).not.toMatch(new RegExp("absta" + "in", "i"))
  expect(content).not.toMatch(/PCIndex continuously parses official policy sources/i)
  expect(content).not.toMatch(/preview dataset|gate|agent readiness|official source pending|no source|pci signal|prediction mode/i)
})

test("policy detail URLs resolve back to the terminal accordion", async ({ page }) => {
  await page.goto("/policies/45V")

  await expect(page).toHaveURL(/\/#policy-45V$/)
  await expect(page.getByRole("heading", { name: "Tracked verticals" })).toBeVisible()
  await expect(page.locator(".policy-accordion-trigger", { hasText: "45V" })).toBeVisible()
  await expect(page.getByText("Latest official evidence")).toHaveCount(0)
  await expect(page.getByText("Policy basis")).toHaveCount(0)
  await expect(page.getByText("Cited evidence")).toHaveCount(0)

  const content = await page.content()
  expect(content).not.toMatch(/supabase/i)
  expect(content).not.toMatch(new RegExp("autonom" + "ous", "i"))
  expect(content).not.toMatch(new RegExp("absta" + "in", "i"))
  expect(content).not.toMatch(/preview dataset|gate|agent readiness|official source pending|no source|pci signal|prediction mode/i)
})

function parseMcpResponse(body: string) {
  const dataLine = body
    .split("\n")
    .find((line) => line.startsWith("data:"))
  return JSON.parse(dataLine ? dataLine.slice("data:".length).trim() : body)
}
