import { expect, test } from "@playwright/test"

test("live local demo renders seeded Supabase state", async ({ page }) => {
  await page.goto("/")

  await expect(page.getByRole("heading", { name: "Policy Markets", exact: true })).toBeVisible()
  await expect(
    page.getByText("IRA credibility board · official sources only · no synthetic markets"),
  ).toBeVisible()
  await expect(page.getByRole("heading", { name: "Provision markets", exact: true })).toBeVisible()
  await expect(page.getByText("Clean Hydrogen Production Credit")).toBeVisible()
  await expect(page.getByText("Advanced Manufacturing Production Credit")).toBeVisible()
  await expect(page.getByRole("heading", { name: "No live forecast commitments yet" })).toBeVisible()
  await expect(
    page.getByText("Waiting for a scored policy event"),
  ).toBeVisible()
  await expect(page.getByText("No proposals pending approval.")).toBeVisible()
  await expect(page.getByText("No resolved forecast commitments yet")).toBeVisible()

  await expect(page.getByText("Sports")).toHaveCount(0)
  await expect(page.getByText("Crypto")).toHaveCount(0)
})
