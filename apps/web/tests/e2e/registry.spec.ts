import { expect, test } from "@playwright/test"

test("renders the policy-first landing page", async ({ page }) => {
  await page.goto("/")

  await expect(
    page.getByRole("heading", { name: "Live evidence for climate policy credibility." }),
  ).toBeVisible()
  await expect(page.locator(".live-chip")).toContainText("Latest update")
  await expect(page.getByText("Federal Register").first()).toBeVisible()
  await expect(page.getByText("Source coverage").first()).toBeVisible()
  await expect(page.getByText("Cited evidence").first()).toBeVisible()
  await expect(page.getByText("Policy Intelligence", { exact: true })).toBeVisible()
  await expect(page.getByText("Clean Vehicle Credit").first()).toBeVisible()
  await expect(page.getByRole("link", { name: "Open terminal" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Read about the paper" })).toBeVisible()
  await expect(page.getByText("Registry Trace")).toHaveCount(0)
  await expect(page.getByText("Source ledger")).toHaveCount(0)
  await expect(page.locator("[aria-label='Policy credibility trend']")).toHaveCount(0)
  const content = await page.content()
  expect(content).not.toMatch(/supabase/i)
  expect(content).not.toMatch(new RegExp("autonom" + "ous", "i"))
  expect(content).not.toMatch(new RegExp("absta" + "in", "i"))
  expect(content).not.toMatch(/preview dataset|gate|agent readiness|official source pending|no scored|pci signal|prediction mode/i)
})

test("renders the methodology companion with policy dimensions", async ({ page }) => {
  await page.goto("/about")

  await expect(
    page.getByRole("heading", {
      name: "Industrial policy reshapes venture capital allocation and growth trajectories in climate technologies",
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
  await expect(page.getByText("source citations, and source refresh timing")).toBeVisible()
  await expect(page.getByRole("heading", { name: "BibTeX" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Terminal" }).first()).toBeVisible()
  expect(await page.content()).not.toMatch(/gated trade proposals|supabase/i)
})

test("renders the agent connection setup without secrets", async ({ page }) => {
  await page.goto("/connect")

  await expect(
    page.getByRole("heading", { name: "PCIndex MCP Server" }),
  ).toBeVisible()
  await expect(page.getByText("Connection details")).toBeVisible()
  await expect(page.getByText("Server name")).toBeVisible()
  await expect(page.getByText("Local stdio")).toBeVisible()
  await expect(page.locator(".connect-detail-grid div", { hasText: "Server command" })).toContainText(
    "uv run --extra dev python -m pci_realtime.mcp_server",
  )
  await expect(page.getByText("Setup instructions")).toBeVisible()
  await expect(page.getByText("Available tools")).toBeVisible()
  await expect(page.getByText("status()")).toBeVisible()
  await expect(page.getByText("list_policies()")).toBeVisible()
  await expect(page.getByText("current_pci(code?)")).toBeVisible()
  await expect(page.getByText("policy_dossier(code)")).toBeVisible()
  await expect(page.getByText("get_evidence_trace(provision, evidence_id?)")).toBeVisible()
  await expect(page.getByText("submit_policy_evidence(provision, source, citation, claim, idempotency_key, agent_run_id?, agent_name?, question?)")).toBeVisible()
  await expect(page.getByText("ingest_source_url(provision, url, rationale, idempotency_key, agent_run_id?, agent_name?, question?)")).toBeVisible()
  await expect(page.getByText("Claude Code command")).toBeVisible()
  await expect(page.getByText("Codex CLI command")).toBeVisible()
  await expect(page.getByText("claude mcp add -s user pcindex")).toBeVisible()
  await expect(page.getByText("codex mcp add pcindex")).toBeVisible()
  await expect(page.getByText("Generic MCP client")).toHaveCount(0)
  await expect(page.getByText("Policy evidence brief")).toHaveCount(0)
  await expect(page.getByText("Use the PCIndex connector named pcindex.")).toHaveCount(0)
  await expect(page.getByText("Connector workflow")).toHaveCount(0)
  await expect(page.getByText("Supported agents")).toHaveCount(0)
  await expect(page.getByText("Agent instruction")).toHaveCount(0)
  await expect(page.getByText("Setup checklist")).toHaveCount(0)
  await expect(page.getByText("Environment")).toHaveCount(0)
  await expect(page.getByText("Reads")).toHaveCount(0)
  await expect(page.getByText("Hosted connector")).toHaveCount(0)
  await expect(page.getByText("Safety boundary")).toHaveCount(0)

  const content = await page.content()
  expect(content).not.toMatch(/sb_secret_|sb_publishable_|sk-proj-|fdxinkqiarezurwofhmz/i)
  expect(content).not.toMatch(/\/Users\/c-dnguyen/i)
  expect(content).not.toMatch(/SUPABASE_|service-role|005_agent_evidence_intake|scripts\/smoke_mcp|--write-smoke|\.env|public browser app stays read-only/i)
  expect(content).not.toMatch(/\/path\/to|mcpServers|Copy the setup block/i)

  const fitsViewport = await page.evaluate(
    () => document.documentElement.scrollWidth <= window.innerWidth + 1,
  )
  expect(fitsViewport).toBe(true)
})

test("redirects the common connect page typo", async ({ page }) => {
  await page.goto("/conncet")

  await expect(page).toHaveURL(/\/connect$/)
  await expect(
    page.getByRole("heading", { name: "PCIndex MCP Server" }),
  ).toBeVisible()
})

test("lists the connection page in the agent documentation index", async ({ page }) => {
  await page.goto("/llms.txt")

  await expect(page.getByText("[Connect](https://pcindex.vercel.app/connect)")).toBeVisible()
})

test("renders the policy credibility terminal without fake market fields", async ({ page }) => {
  await page.goto("/dashboard")

  await expect(page.getByRole("heading", { name: "Climate policy intelligence terminal" })).toBeVisible()
  await expect(
    page.getByRole("navigation", { name: "Primary navigation" }).getByRole("link", { name: "Connect" }),
  ).toBeVisible()
  await expect(page.getByPlaceholder("Search policy, agency, or document")).toBeVisible()
  await expect(page.getByText("Policy Intelligence", { exact: true })).toBeVisible()
  await expect(page.getByText("Source coverage").first()).toBeVisible()
  await expect(page.getByText("Cited evidence").first()).toBeVisible()
  const isMobile = (page.viewportSize()?.width ?? 1280) < 900
  if (isMobile) {
    await expect(page.locator(".mobile-cell-label").filter({ hasText: "Current PCI" }).first()).toBeVisible()
    await expect(page.locator(".mobile-cell-label").filter({ hasText: "Weekly change" }).first()).toBeVisible()
    await expect(page.locator(".mobile-cell-label").filter({ hasText: "Score inputs" }).first()).toBeVisible()
  } else {
    await expect(page.getByRole("columnheader", { name: "Current PCI" })).toBeVisible()
    await expect(page.getByRole("columnheader", { name: "Weekly Change" })).toBeVisible()
    await expect(page.getByRole("columnheader", { name: "Score Inputs" })).toBeVisible()
  }
  await expect(page.getByText("Policy basis").first()).toBeVisible()
  await expect(page.getByText("Source ledger")).toHaveCount(0)
  await page.getByPlaceholder("Search policy, agency, or document").fill("45V")
  await expect(page.getByText("Clean hydrogen production credit guidance").first()).toBeVisible()

  const content = await page.content()
  expect(content).not.toMatch(/supabase/i)
  expect(content).not.toMatch(new RegExp("autonom" + "ous", "i"))
  expect(content).not.toMatch(new RegExp("absta" + "in", "i"))
  expect(content).not.toMatch(/preview dataset|gate|agent readiness|official source pending|no scored|no source|pci signal|prediction mode/i)
  await expect(page.getByRole("columnheader", { name: "Probability" })).toHaveCount(0)
  await expect(page.getByRole("columnheader", { name: "Edge" })).toHaveCount(0)
  await expect(page.getByRole("columnheader", { name: "Liquidity" })).toHaveCount(0)
  await expect(page.getByText("KX-HYDROGEN-TAXCREDIT-2026")).toHaveCount(0)
})

test("renders canonical policy dossier pages", async ({ page }) => {
  await page.goto("/policies/45V")

  await expect(
    page.getByRole("heading", { name: "Clean Hydrogen Production Credit", exact: true }),
  ).toBeVisible()
  await expect(page.getByText("Section 45V Clean Hydrogen Production Credit").first()).toBeVisible()
  await expect(page.getByRole("heading", { name: "Latest official evidence" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Specificity, durability, enforceability" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Links behind this policy score" })).toBeVisible()
  await expect(page.getByText("Weekly change")).toHaveCount(0)
  await expect(page.getByText("Score evidence")).toBeVisible()
  await expect(page.getByText("Contributor intake")).toBeVisible()
  await expect(
    page.getByText("Treasury guidance narrows eligibility for the clean hydrogen credit.").first(),
  ).toBeVisible()
  await expect(page.getByText("Source ledger")).toHaveCount(0)
  await expect(page.getByText("Policy intelligence context").first()).toBeVisible()
  await expect(page.getByText("Policy basis")).toBeVisible()
  await expect(page.getByText("The displayed PCI is the average")).toBeVisible()
  await expect(page.locator("[aria-label='Policy credibility trend']")).toBeVisible()
  await expect(page.getByText("Treasury guidance narrows eligibility").first()).toBeVisible()

  const content = await page.content()
  expect(content).not.toMatch(/supabase/i)
  expect(content).not.toMatch(new RegExp("autonom" + "ous", "i"))
  expect(content).not.toMatch(new RegExp("absta" + "in", "i"))
  expect(content).not.toMatch(/preview dataset|gate|agent readiness|official source pending|no scored|no source|pci signal|prediction mode/i)
  await expect(page.getByText("US Treasury send transactions on blockchain")).toHaveCount(0)
})
