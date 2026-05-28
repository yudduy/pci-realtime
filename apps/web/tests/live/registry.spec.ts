import { expect, test } from "@playwright/test"

test("registry renders seeded policy state", async ({ page }) => {
  await page.goto("/")

  await expect(page.getByRole("heading", { name: "Policy credibility, market-by-market." })).toBeVisible()
  await expect(page.getByText("PCIndex", { exact: true }).first()).toBeVisible()
  expect(await page.content()).not.toMatch(/supabase/i)

  await page.goto("/about")
  await expect(
    page.getByRole("heading", {
      name: "Industrial policy reshapes venture capital allocation and growth trajectories in climate technologies",
    }),
  ).toBeVisible()
  expect(await page.content()).not.toMatch(/supabase/i)

  await page.goto("/markets/45V")
  await expect(page.getByRole("heading", { name: "Will clean hydrogen credits remain in place?" })).toBeVisible()
  await expect(page.getByRole("tab", { name: /Evidence/ })).toBeVisible()
  expect(await page.content()).not.toMatch(/supabase/i)

  await expect(page.getByText("Demo")).toHaveCount(0)
  await expect(page.getByText("Monitor")).toHaveCount(0)
  await expect(page.getByText("Sports")).toHaveCount(0)
  await expect(page.getByText("Crypto")).toHaveCount(0)
})
