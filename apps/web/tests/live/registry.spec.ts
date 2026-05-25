import { expect, test } from "@playwright/test"

test("registry renders seeded Supabase state", async ({ page }) => {
  await page.goto("/")

  await expect(
    page.getByRole("heading", {
      name: "Industrial policy reshapes venture capital allocation and growth trajectories in climate technologies",
    }),
  ).toBeVisible()
  await expect(page.getByText("Policy Credibility Index", { exact: true })).toBeVisible()
  await expect(page.getByRole("link", { name: "Open registry" })).toBeVisible()

  await page.goto("/dashboard")

  await expect(page.getByText("Energy Odds", { exact: true })).toBeVisible()
  await expect(page.getByText("Six policies. Real markets only.")).toBeVisible()
  await expect(page.getByRole("heading", { name: "Policies", exact: true })).toBeVisible()
  await expect(page.getByRole("button", { name: "Hydrogen 45V" })).toBeVisible()
  await expect(page.getByRole("button", { name: "Factory credits 45X" })).toBeVisible()

  await page.getByRole("button", { name: /Odds\s*0/ }).click()
  await expect(page.getByRole("heading", { name: "No live odds yet" })).toBeVisible()
  await expect(page.getByText("Waiting for a policy move")).toBeVisible()
  await expect(page.getByText("No trades pending.")).toBeVisible()
  await page.getByRole("button", { name: /Resolved\s*0/ }).click()
  await expect(page.getByText("No resolved forecasts yet.")).toBeVisible()

  await expect(page.getByText("Sports")).toHaveCount(0)
  await expect(page.getByText("Crypto")).toHaveCount(0)
})
