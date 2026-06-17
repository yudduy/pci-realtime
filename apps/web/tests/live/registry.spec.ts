import { expect, test } from "@playwright/test"

test("registry renders policy terminal state", async ({ page }) => {
  await page.goto("/")

  await expect(page.getByRole("heading", { name: "Climate policy intelligence" })).toBeVisible()
  await expect(page.getByText("Policy Intelligence Ledger", { exact: true }).first()).toBeVisible()
  await expect(page.getByRole("button", { name: "About this terminal" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Read about the paper" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Open terminal" })).toHaveCount(0)
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

  await expect(page.getByRole("heading", { name: "Climate policy intelligence" })).toBeVisible()
  await expect(page.getByText("Policy Intelligence Ledger", { exact: true })).toBeVisible()
  await expect(page.getByRole("button", { name: "About this terminal" })).toBeVisible()
  const sourceLink = page.getByRole("link", { name: "View source" })
  await expect(sourceLink).toBeVisible()
  await expect(sourceLink).toHaveAttribute("href", /#(:~:text=|search=)/)
  await expect(page.getByRole("button", { name: "View score" })).toHaveCount(0)
  await expect(page.getByRole("heading", { name: "Tracked policies" })).toBeVisible()
  await expect(page.getByText("Fragile")).toHaveCount(0)
  await expect(page.getByText("Mixed")).toHaveCount(0)
  await expect(page.getByText("Strong")).toHaveCount(0)
  await expect(page.getByText("PCI +")).toHaveCount(0)
  await expect(page.getByText("PCI -")).toHaveCount(0)
  await expect(page.getByText("Improving")).toHaveCount(0)
  await expect(page.getByText("Weakening")).toHaveCount(0)
  await expect(page.getByText("No move")).toHaveCount(0)
  await expect(page.getByText("Data updated")).toHaveCount(0)
  await expect(page.locator(".policy-accordion-item").first()).toBeVisible()
  if ((await page.locator(".policy-score-trend").count()) === 0) {
    await page.locator(".policy-accordion-trigger").first().click()
  }
  await expect(page.locator(".policy-score-trend").first()).toBeVisible()
  await expect(page.getByText("Scoring").first()).toBeVisible()
  await expect(page.locator(".policy-source-card").first()).toBeVisible()
  await expect(page.getByRole("columnheader")).toHaveCount(0)
  await expect(page.getByText("Current Brief")).toHaveCount(0)
  await expect(page.getByRole("columnheader", { name: "Score Inputs" })).toHaveCount(0)
  await expect(page.getByRole("columnheader", { name: "Weekly Change" })).toHaveCount(0)
  await expect(page.getByText("Source ledger")).toHaveCount(0)
  await expect(page.getByText("Policy basis")).toHaveCount(0)
  await expect(page.getByText("Cited evidence")).toHaveCount(0)
  await expect(page.getByText("Trajectory")).toHaveCount(0)
  await expect(page.getByRole("columnheader", { name: "Probability" })).toHaveCount(0)
  await expect(page.getByRole("columnheader", { name: "Edge" })).toHaveCount(0)
  const content = await page.content()
  expect(content).not.toMatch(/supabase/i)
  expect(content).not.toMatch(new RegExp("autonom" + "ous", "i"))
  expect(content).not.toMatch(new RegExp("absta" + "in", "i"))
  expect(content).not.toMatch(/PCIndex continuously parses official policy sources/i)
  expect(content).not.toMatch(/preview dataset|gate|agent readiness|official source pending|no scored|pci signal|prediction mode/i)

  await page.goto("/policies/45V")
  await expect(page).toHaveURL(/\/dashboard#policy-45V$/)
  await expect(page.getByRole("heading", { name: "Tracked policies" })).toBeVisible()
  await expect(page.getByText("Policy basis")).toHaveCount(0)
})
