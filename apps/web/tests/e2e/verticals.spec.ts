import { expect, test } from "@playwright/test"

test("makes climate-tech verticals the landing page hierarchy", async ({ page }) => {
  await page.goto("/")

  const cards = page.getByTestId("vertical-card")
  await expect(cards).toHaveCount(5)
  await expect(cards.locator("h3")).toHaveText([
    "Advanced Manufacturing",
    "Clean Hydrogen",
    "Carbon Capture",
    "Electric Vehicles",
    "Clean Energy Finance",
  ])
  await expect(
    page.getByText("Commitment credibility vs IRA-enactment baseline", {
      exact: true,
    }),
  ).toBeVisible()

  const financeCard = cards.filter({ hasText: "Clean Energy Finance" })
  await expect(financeCard.locator(".vertical-provision-chip")).toHaveText([
    "50141",
    "50144",
  ])
  await expect(financeCard.locator(".vertical-card-status strong")).toHaveText(
    "3.17",
  )

  const financeGroup = page.locator("#vertical-clean-energy-finance")
  const financeTrigger = financeGroup.locator(".vertical-group-trigger")
  await expect(financeTrigger).toHaveAttribute("aria-expanded", "false")
  await financeCard.click()
  await expect(page).toHaveURL(/#vertical-clean-energy-finance$/)
  await expect(financeTrigger).toHaveAttribute("aria-expanded", "true")
  await expect(financeGroup.locator(".policy-accordion-item")).toHaveCount(2)
  await expect(financeGroup.locator(".policy-accordion-item").first()).toBeVisible()

  await expect(page.getByRole("heading", { name: "Not yet scored" })).toBeVisible()
  await expect(page.locator(".unscored-verticals")).toContainText(
    "Solar & Wind Deployment (45Y/48E)",
  )
  await expect(page.locator(".unscored-verticals")).toContainText(
    "Scoring requires methodology sign-off",
  )

  await expect(page.locator("#vertical-advanced-manufacturing")).toHaveClass(
    /vertical-tone-green/,
  )
  await expect(page.locator("#vertical-clean-hydrogen")).toHaveClass(
    /vertical-tone-amber/,
  )
  await expect(page.locator("#vertical-carbon-capture")).toHaveClass(
    /vertical-tone-red/,
  )
  await expect(page.locator("#vertical-electric-vehicles")).toHaveClass(
    /vertical-tone-green/,
  )
  await expect(page.locator("#vertical-clean-energy-finance")).toHaveClass(
    /vertical-tone-green/,
  )
})
