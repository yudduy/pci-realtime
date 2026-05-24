import { expect, test } from "@playwright/test"

test("renders the PCI market registry without clone clutter", async ({ page }) => {
  await page.goto("/")

  await expect(page.getByText("PCI Forecast Registry")).toBeVisible()
  await expect(page.getByText("Advanced Manufacturing Production Credit")).toBeVisible()
  await expect(page.getByText("Clean Hydrogen Production Credit")).toBeVisible()
  await expect(
    page.getByRole("heading", { name: "Forecast commitments", exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole("heading", { name: "Gated trade proposals", exact: true }),
  ).toBeVisible()

  await expect(page.getByText("Last registry update: May 24, 2026")).toBeVisible()
  await expect(page.getByText("Policy events", { exact: true })).toBeVisible()
  await expect(page.getByText("Eligible markets", { exact: true })).toBeVisible()
  await expect(page.getByText("Forecasts", { exact: true })).toBeVisible()
  await expect(page.getByText("Trade proposals", { exact: true })).toBeVisible()
  await expect(page.getByRole("heading", { name: "No live forecast commitments yet" })).toBeVisible()
  await expect(
    page.getByText("No official PCI event has matched a clean Kalshi market yet."),
  ).toBeVisible()
  await expect(page.getByRole("heading", { name: "Market scan", exact: true })).toBeVisible()
  await expect(page.getByText("No eligible policy markets in the latest scan.")).toBeVisible()
  await expect(page.getByText("No proposals are pending approval.")).toBeVisible()
  await expect(page.getByText("No resolved forecast commitments yet")).toBeVisible()

  await expect(page.getByText("Polymarket")).toHaveCount(0)
  await expect(page.getByText("Sports")).toHaveCount(0)
  await expect(page.getByText("Crypto")).toHaveCount(0)
  await expect(page.getByText("How it works")).toHaveCount(0)
  await expect(page.getByText("KX-HYDROGEN-TAXCREDIT-2026")).toHaveCount(0)
})
