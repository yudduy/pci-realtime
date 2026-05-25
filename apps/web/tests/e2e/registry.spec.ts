import { expect, test } from "@playwright/test"

test("renders the research companion landing page", async ({ page }) => {
  await page.goto("/")

  await expect(
    page.getByRole("heading", { name: "A live monitor for policy credibility." }),
  ).toBeVisible()
  await expect(page.getByText("Companion to the IRA venture-capital paper")).toBeVisible()
  await expect(page.getByText("7,271")).toBeVisible()
  await expect(page.getByText("132,826")).toBeVisible()
  await expect(page.getByRole("heading", { name: "Paper anchor" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Approach" })).toBeVisible()
  await expect(page.getByText("Official documents")).toBeVisible()
  await expect(page.getByRole("link", { name: "Open live monitor" })).toBeVisible()

  await expect(page.getByText("Sports")).toHaveCount(0)
  await expect(page.getByText("Crypto")).toHaveCount(0)
})

test("renders the PCI market registry without clone clutter", async ({ page }) => {
  await page.goto("/dashboard")

  await expect(page.getByText("Energy Odds", { exact: true })).toBeVisible()
  await expect(page.getByPlaceholder("Search policies or markets")).toBeVisible()
  await expect(page.getByText("Six policies. Real markets only.")).toBeVisible()
  await expect(page.getByRole("heading", { name: "Policies", exact: true })).toBeVisible()
  await expect(page.getByRole("button", { name: "EV credits 30D" })).toBeVisible()
  await expect(page.getByRole("button", { name: "Hydrogen 45V" })).toBeVisible()
  await expect(page.getByRole("button", { name: "Factory credits 45X" })).toBeVisible()
  await expect(page.getByText("Now")).toHaveCount(6)
  await expect(page.getByText("Stress")).toHaveCount(6)

  await page.getByRole("button", { name: /Odds\s*0/ }).click()
  await expect(page.getByRole("heading", { name: "Odds", exact: true })).toBeVisible()
  await expect(page.getByRole("heading", { name: "No live odds yet" })).toBeVisible()
  await expect(page.getByText("Waiting for a policy move")).toBeVisible()

  await page.getByRole("button", { name: /Kalshi\s*0/ }).click()
  await expect(page.getByRole("heading", { name: "Kalshi matches", exact: true })).toBeVisible()
  await expect(page.getByText("No clean market match yet.")).toBeVisible()

  await expect(page.getByText("No trades pending.")).toBeVisible()
  await page.getByRole("button", { name: /Resolved\s*0/ }).click()
  await expect(page.getByText("No resolved forecasts yet.")).toBeVisible()

  await expect(page.getByText("Sports")).toHaveCount(0)
  await expect(page.getByText("Crypto")).toHaveCount(0)
  await expect(page.getByText("How it works")).toHaveCount(0)
  await expect(page.getByText("KX-HYDROGEN-TAXCREDIT-2026")).toHaveCount(0)
})
