import { expect, test } from "@playwright/test"

test("renders the research companion landing page", async ({ page }) => {
  await page.goto("/")

  await expect(
    page.getByRole("heading", {
      name: "Industrial policy reshapes venture capital allocation and growth trajectories in climate technologies",
    }),
  ).toBeVisible()
  await expect(page.getByText("Policy Credibility Index", { exact: true })).toBeVisible()
  await expect(page.getByText("7,271")).toBeVisible()
  await expect(page.getByText("132,826")).toBeVisible()
  await expect(page.getByRole("heading", { name: "Paper anchor" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Policy credibility by IRA provision" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Approach" })).toBeVisible()
  await expect(page.getByText("Official documents")).toBeVisible()
  await expect(page.getByRole("navigation", { name: "Project navigation" }).getByRole("link", { name: "Registry" })).toBeVisible()

  await expect(page.getByText("Sports")).toHaveCount(0)
  await expect(page.getByText("Crypto")).toHaveCount(0)
})

test("renders the PCI market registry without clone clutter", async ({ page }) => {
  await page.goto("/dashboard")

  await expect(page.getByText("Policy Markets", { exact: true })).toBeVisible()
  await expect(page.getByPlaceholder("Search policy, market, or ticker")).toBeVisible()
  await expect(page.getByRole("heading", { name: "Featured policy markets" })).toBeVisible()
  await expect(page.getByText("Plain-language IRA provisions")).toBeVisible()
  await expect(page.getByText("Will EV credits stay stable?").first()).toBeVisible()
  await expect(page.getByText("Will hydrogen credits stay stable?").first()).toBeVisible()
  await expect(page.getByText("Will factory credits stay stable?").first()).toBeVisible()
  await expect(page.getByText("No clean market yet").first()).toBeVisible()
  await expect(page.getByText("Trade gate")).toBeVisible()
  await expect(page.getByText("No backend trade proposal for this market.")).toBeVisible()

  await page.getByRole("button", { name: /Forecasts\s*0/ }).click()
  await expect(page.getByText("No matching markets.")).toBeVisible()

  await page.getByRole("button", { name: /Kalshi\s*0/ }).click()
  await expect(page.getByText("No matching markets.")).toBeVisible()

  await page.getByRole("button", { name: /Resolved\s*0/ }).click()
  await expect(page.getByText("No matching markets.")).toBeVisible()

  await expect(page.getByText("Sports")).toHaveCount(0)
  await expect(page.getByText("Crypto")).toHaveCount(0)
  await expect(page.getByText("How it works")).toHaveCount(0)
  await expect(page.getByText("KX-HYDROGEN-TAXCREDIT-2026")).toHaveCount(0)
})
