import { expect, test } from "@playwright/test"

test("registry renders policy terminal state", async ({ page }) => {
  await page.goto("/")

  await expect(
    page.getByRole("heading", { name: "Live evidence for climate policy credibility." }),
  ).toBeVisible()
  await expect(page.getByText("Policy Credibility Index", { exact: true }).first()).toBeVisible()
  await expect(page.getByText("Cited evidence").first()).toBeVisible()
  await expect(page.getByRole("link", { name: "Open terminal" })).toBeVisible()
  await expect(page.getByText("Source ledger")).toHaveCount(0)
  expect(await page.content()).not.toMatch(/supabase/i)

  await page.goto("/about")
  await expect(
    page.getByRole("heading", {
      name: "Industrial policy reshapes venture capital allocation and growth trajectories in climate technologies",
    }),
  ).toBeVisible()
  await expect(page.getByRole("columnheader", { name: "Specificity" })).toBeVisible()
  expect(await page.content()).not.toMatch(/supabase/i)

  await page.goto("/dashboard")

  await expect(page.getByRole("heading", { name: "Climate policy intelligence terminal" })).toBeVisible()
  await expect(page.getByText("Policy Intelligence", { exact: true })).toBeVisible()
  const viewportWidth = page.viewportSize()?.width ?? 1280
  if (viewportWidth < 900) {
    await expect(page.locator(".mobile-cell-label").filter({ hasText: "Current PCI" }).first()).toBeVisible()
    await expect(page.locator(".mobile-cell-label").filter({ hasText: "Score inputs" }).first()).toBeVisible()
  } else {
    await expect(page.getByRole("columnheader", { name: "Current PCI" })).toBeVisible()
    await expect(page.getByRole("columnheader", { name: "Score Inputs" })).toBeVisible()
  }
  await expect(page.getByText("Source ledger")).toHaveCount(0)
  await expect(page.getByRole("columnheader", { name: "Probability" })).toHaveCount(0)
  await expect(page.getByRole("columnheader", { name: "Edge" })).toHaveCount(0)
  const content = await page.content()
  expect(content).not.toMatch(/supabase/i)
  expect(content).not.toMatch(new RegExp("autonom" + "ous", "i"))
  expect(content).not.toMatch(new RegExp("absta" + "in", "i"))
  expect(content).not.toMatch(/preview dataset|gate|agent readiness|official source pending|no scored|pci signal|prediction mode/i)

  await page.goto("/policies/45V")
  await expect(
    page.getByRole("heading", { name: "Clean Hydrogen Production Credit", exact: true }),
  ).toBeVisible()
  await expect(page.getByRole("heading", { name: "Links behind this policy score" })).toBeVisible()
  await expect(page.getByText("Policy basis")).toBeVisible()
})
