import { expect, test } from "@playwright/test"

test("renders the PCI market registry without clone clutter", async ({ page }) => {
  await page.goto("/")

  await expect(page.getByText("Policy Markets", { exact: true })).toBeVisible()
  await expect(page.getByPlaceholder("Search provisions, markets, tickers")).toBeVisible()
  await expect(
    page.getByText("PCI-backed IRA odds · official sources only · no synthetic markets"),
  ).toBeVisible()
  await expect(
    page.getByRole("heading", { name: "All markets", exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole("heading", { name: "Forecast markets", exact: true }),
  ).toBeVisible()
  await expect(page.getByText("Current PCI")).toHaveCount(6)
  await expect(page.getByText("OBBBA stress")).toHaveCount(6)

  await expect(page.getByRole("heading", { name: "No published forecasts yet" })).toBeVisible()
  await expect(
    page.getByText("Waiting for a scored policy event"),
  ).toBeVisible()
  await expect(page.getByRole("heading", { name: "Eligible Kalshi markets", exact: true })).toBeVisible()
  await expect(page.getByText("No eligible policy markets in the latest scan.")).toBeVisible()
  await expect(page.getByText("No proposals pending approval.")).toBeVisible()
  await expect(page.getByText("No resolved forecast commitments yet")).toBeVisible()

  await expect(page.getByText("Sports")).toHaveCount(0)
  await expect(page.getByText("Crypto")).toHaveCount(0)
  await expect(page.getByText("How it works")).toHaveCount(0)
  await expect(page.getByText("KX-HYDROGEN-TAXCREDIT-2026")).toHaveCount(0)
})
