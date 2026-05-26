import { expect, test } from "@playwright/test"

test("renders the live tracker landing page", async ({ page }) => {
  await page.goto("/")

  await expect(page.getByRole("heading", { name: "Live odds for climate policy credibility." })).toBeVisible()
  await expect(page.getByText("Live policy data")).toBeVisible()
  await expect(page.getByText("Federal Register").first()).toBeVisible()
  await expect(page.getByText("Featured Policy Markets")).toBeVisible()
  await expect(page.getByText("Will EV credits stay stable?").first()).toBeVisible()
  await expect(page.getByRole("link", { name: "Open tracker" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Read about the paper" })).toBeVisible()
  await expect(
    page.getByRole("heading", {
      name: "Industrial policy reshapes venture capital allocation and growth trajectories in climate technologies",
    }),
  ).toHaveCount(0)
  await expect(page.getByText("Policy Credibility Index", { exact: true }).first()).toBeVisible()
  expect(await page.content()).not.toMatch(/supabase/i)
  await expect(page.getByText("Demo")).toHaveCount(0)
  await expect(page.getByText("Monitor")).toHaveCount(0)
  await expect(page.getByText("Sports")).toHaveCount(0)
  await expect(page.getByText("Crypto")).toHaveCount(0)
})

test("renders the paper companion on about", async ({ page }) => {
  await page.goto("/about")

  await expect(
    page.getByRole("heading", {
      name: "Industrial policy reshapes venture capital allocation and growth trajectories in climate technologies",
    }),
  ).toBeVisible()
  await expect(page.getByText("7,271")).toBeVisible()
  await expect(page.getByText("132,826")).toBeVisible()
  await expect(page.getByRole("heading", { name: "Paper anchors" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Policy credibility by IRA provision" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "What the tracker adds" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "BibTeX" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Tracker" }).first()).toBeVisible()
  expect(await page.content()).not.toMatch(/supabase/i)

  await expect(page.getByText("Demo")).toHaveCount(0)
  await expect(page.getByText("Monitor")).toHaveCount(0)
  await expect(page.getByText("Sports")).toHaveCount(0)
  await expect(page.getByText("Crypto")).toHaveCount(0)
})

test("renders the PCI market tracker without clone clutter", async ({ page }) => {
  await page.goto("/dashboard")

  await expect(page.getByRole("heading", { name: "IRA credibility markets" })).toBeVisible()
  await expect(page.getByPlaceholder("Search policy, market, or ticker")).toBeVisible()
  await expect(page.getByText("Policy Market Tracker")).toBeVisible()
  await expect(page.getByText("Will EV credits stay stable?").first()).toBeVisible()
  await expect(page.getByText("Will hydrogen credits stay stable?").first()).toBeVisible()
  await expect(page.getByText("Will factory credits stay stable?").first()).toBeVisible()
  await expect(page.getByText("No eligible public market").first()).toBeVisible()
  await expect(page.getByText("Market Discovery Audit").first()).toBeVisible()
  await expect(page.getByText("No IRA/policy context").first()).toBeVisible()
  await expect(page.getByRole("button", { name: /Policy moves\s*6/ })).toBeVisible()
  await expect(page.getByRole("button", { name: /Forecasts\s*0/ })).toHaveCount(0)
  await page.getByText("Will hydrogen credits stay stable?").first().click()
  await expect(page.getByText("Market Facts")).toBeVisible()
  await expect(page.getByText("Why This Moved")).toBeVisible()
  await expect(page.getByText("Evidence path")).toBeVisible()
  await expect(page.getByText("Treasury guidance narrows eligibility").first()).toBeVisible()
  expect(await page.content()).not.toMatch(/supabase/i)

  await expect(page.getByText("Pipeline")).toHaveCount(0)
  await expect(page.getByText("No backend trade proposal for this market.")).toHaveCount(0)
  await expect(page.getByText("Demo")).toHaveCount(0)
  await expect(page.getByText("Monitor")).toHaveCount(0)
  await expect(page.getByText("Sports")).toHaveCount(0)
  await expect(page.getByText("Crypto")).toHaveCount(0)
  await expect(page.getByText("How it works")).toHaveCount(0)
  await expect(page.getByText("KX-HYDROGEN-TAXCREDIT-2026")).toHaveCount(0)
})
