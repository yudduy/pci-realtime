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

  await expect(page.getByText("Policy Markets", { exact: true })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Featured policy markets" })).toBeVisible()
  await expect(page.getByText("Plain-language IRA provisions")).toBeVisible()
  await expect(page.getByText("Will hydrogen credits stay stable?").first()).toBeVisible()
  await expect(page.getByText("Will factory credits stay stable?").first()).toBeVisible()

  await page.getByRole("button", { name: /Forecasts\s*0/ }).click()
  await expect(page.getByText("No matching markets.")).toBeVisible()
  await page.getByRole("button", { name: /Resolved\s*0/ }).click()
  await expect(page.getByText("No matching markets.")).toBeVisible()

  await expect(page.getByText("Sports")).toHaveCount(0)
  await expect(page.getByText("Crypto")).toHaveCount(0)
})
