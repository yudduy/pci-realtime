import { expect, test } from "@playwright/test"

test("renders the landing market grid (Polymarket-style)", async ({ page }) => {
  await page.goto("/")

  await expect(page.getByRole("heading", { name: "Policy credibility, market-by-market." })).toBeVisible()
  await expect(page.getByText("Live data")).toBeVisible()
  await expect(page.getByText("Federal Register").first()).toBeVisible()

  // Each tracked provision must appear as a scanable card linking to its modular detail route
  await expect(page.getByRole("link", { name: /45V/ }).first()).toBeVisible()
  await expect(page.getByRole("link", { name: /45X/ }).first()).toBeVisible()
  await expect(page.getByRole("link", { name: /30D/ }).first()).toBeVisible()
  await expect(page.getByText("Will clean hydrogen credits remain in place?").first()).toBeVisible()

  // No collapsed-dashboard relics
  await expect(page.getByText("Featured rows")).toHaveCount(0)
  await expect(page.getByPlaceholder("Search policy, market, or ticker")).toHaveCount(0)

  await expect(page.getByText("PCIndex", { exact: true }).first()).toBeVisible()
  expect(await page.content()).not.toMatch(/supabase/i)
  await expect(page.getByText("Demo")).toHaveCount(0)
  await expect(page.getByText("Monitor")).toHaveCount(0)
  await expect(page.getByText("Sports")).toHaveCount(0)
  await expect(page.getByText("Crypto")).toHaveCount(0)
})

test("renders the paper companion on about", async ({ page }) => {
  await page.goto("/about")

  await expect(
    page.getByRole("heading", {
      name: "Industrial policy reshapes venture capital allocation and growth trajectories in climate technologies",
    }),
  ).toBeVisible()
  await expect(page.getByText("7,271")).toBeVisible()
  await expect(page.getByText("132,826")).toBeVisible()
  await expect(page.getByRole("heading", { name: "Paper anchors" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Policy credibility by IRA provision" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "What the tracker adds" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "BibTeX" })).toBeVisible()
  expect(await page.content()).not.toMatch(/supabase/i)

  await expect(page.getByText("Demo")).toHaveCount(0)
  await expect(page.getByText("Monitor")).toHaveCount(0)
  await expect(page.getByText("Sports")).toHaveCount(0)
  await expect(page.getByText("Crypto")).toHaveCount(0)
})

test("renders the per-provision detail page with modular tabs", async ({ page }) => {
  await page.goto("/markets/45V")

  await expect(page.getByRole("heading", { name: "Will clean hydrogen credits remain in place?" })).toBeVisible()

  // Hero state chip + score stats
  await expect(page.getByText("Policy score").first()).toBeVisible()
  await expect(page.getByText("Stress score").first()).toBeVisible()
  await expect(page.getByText("Eligible markets").first()).toBeVisible()

  // Tab strip
  await expect(page.getByRole("tab", { name: /Evidence/ })).toBeVisible()
  await expect(page.getByRole("tab", { name: /Markets/ })).toBeVisible()
  await expect(page.getByRole("tab", { name: /Methodology/ })).toBeVisible()
  await expect(page.getByRole("tab", { name: /Trace/ })).toBeVisible()

  // Right-rail decomposition (scoped to the rail aside since methodology tab also lists dims)
  const rail = page.getByRole("complementary", { name: "Provision score breakdown" })
  await expect(rail.getByText("Decomposition")).toBeVisible()
  await expect(rail.getByText("Specificity")).toBeVisible()
  await expect(rail.getByText("Durability")).toBeVisible()
  await expect(rail.getByText("Enforceability")).toBeVisible()

  // Methodology tab content reachable
  await page.getByRole("tab", { name: /Methodology/ }).click()
  await expect(page.getByText(/How 45V is scored/)).toBeVisible()
  await expect(page.getByText(/Weekly update rule/)).toBeVisible()

  expect(await page.content()).not.toMatch(/supabase/i)
  await expect(page.getByText("KX-HYDROGEN-TAXCREDIT-2026")).toHaveCount(0)
})

test("legacy /dashboard redirects to landing", async ({ page }) => {
  await page.goto("/dashboard")
  await expect(page).toHaveURL("/")
  await expect(page.getByRole("heading", { name: "Policy credibility, market-by-market." })).toBeVisible()
})

test("/markets index lists all provisions", async ({ page }) => {
  await page.goto("/markets")
  await expect(page.getByRole("heading", { name: "Markets", exact: true })).toBeVisible()
  await expect(page.getByRole("link", { name: /45V/ }).first()).toBeVisible()
  await expect(page.getByRole("link", { name: /50141/ }).first()).toBeVisible()
})

test("intercepting drawer opens from /markets/[code] and Escape closes it", async ({ page }) => {
  await page.goto("/markets/45V")
  const viewSource = page.getByRole("link", { name: "View source" }).first()
  await expect(viewSource).toBeVisible()

  // Soft-click should keep us on /markets/45V and show the drawer dialog
  await viewSource.click()
  await expect(page).toHaveURL(/\/markets\/45V/)
  const dialog = page.getByRole("dialog", { name: /policy event|Clean hydrogen/i })
  await expect(dialog).toBeVisible()
  await expect(dialog.getByText("Evidence source")).toBeVisible()

  // Escape closes the bottom sheet without leaving the provision page
  await page.keyboard.press("Escape")
  await expect(dialog).toHaveCount(0)
  await expect(page).toHaveURL(/\/markets\/45V/)
})

test("direct /evidence/[id] renders the standalone fallback (no drawer)", async ({ page }) => {
  await page.goto("/evidence/2026-W21:federal_register:45v-guidance:45V")
  await expect(page.getByRole("heading", { name: "Clean hydrogen production credit guidance" })).toBeVisible()
  // No bottom-sheet on direct deep-link
  await expect(page.getByRole("dialog")).toHaveCount(0)
})
