import { expect, test } from "@playwright/test"

test("registry renders seeded Supabase state", async ({ page }) => {
  await page.goto("/")

  await expect(page.getByRole("heading", { name: "Live odds for climate policy credibility." })).toBeVisible()
  await expect(page.getByText("Policy Credibility Index", { exact: true }).first()).toBeVisible()
  await expect(page.getByRole("link", { name: "Open tracker" })).toBeVisible()

  await page.goto("/about")
  await expect(
    page.getByRole("heading", {
      name: "Industrial policy reshapes venture capital allocation and growth trajectories in climate technologies",
    }),
  ).toBeVisible()

  await page.goto("/dashboard")

  await expect(page.getByRole("heading", { name: "IRA credibility markets" })).toBeVisible()
  await expect(page.getByText("Policy Market Tracker")).toBeVisible()
  await expect(page.getByText("Will hydrogen credits stay stable?").first()).toBeVisible()
  await expect(page.getByText("Will factory credits stay stable?").first()).toBeVisible()

  await expect(page.getByText("Pipeline")).toHaveCount(0)
  await expect(page.getByText("Demo")).toHaveCount(0)
  await expect(page.getByText("Monitor")).toHaveCount(0)
  await expect(page.getByText("Sports")).toHaveCount(0)
  await expect(page.getByText("Crypto")).toHaveCount(0)
})
