import { open, unlink, type FileHandle } from "node:fs/promises"
import { join } from "node:path"
import { expect, test, type APIRequestContext } from "@playwright/test"

const FIXTURE_APP_URL = "http://127.0.0.1:8513/"
const FIXTURE_CONTROL_URL = "http://127.0.0.1:8788/__set_mode"
const FIXTURE_LOCK_PATH = join(
  process.cwd(),
  ".next/e2e-fixture/.control-lock",
)

type FixtureMode =
  | "all-views-fail"
  | "empty-views"
  | "stale-timestamps"

function useFixtureMode(mode: FixtureMode) {
  let lock: FileHandle | null = null

  test.beforeEach(async ({ request }) => {
    lock = await acquireFixtureLock()
    await setFixtureMode(request, mode)
  })
  test.afterEach(async ({ request }) => {
    if (!lock) return

    try {
      await setFixtureMode(request, null)
    } finally {
      await lock.close()
      await unlink(FIXTURE_LOCK_PATH)
      lock = null
    }
  })
}

async function acquireFixtureLock() {
  while (true) {
    try {
      return await open(FIXTURE_LOCK_PATH, "wx")
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "EEXIST") throw error
      await new Promise((resolve) => setTimeout(resolve, 25))
    }
  }
}

async function setFixtureMode(
  request: APIRequestContext,
  mode: FixtureMode | null,
) {
  const response = await request.post(FIXTURE_CONTROL_URL, {
    data: { mode },
  })
  expect(response.status()).toBe(204)
}

test("shows disconnected paper baselines when registry config is absent", async ({
  page,
}) => {
  await page.goto("http://127.0.0.1:8512/")

  const status = page.getByTestId("data-status")
  await expect(status).toHaveAttribute("data-mode", "disconnected")
  await expect(status).toContainText(
    "DISCONNECTED: showing paper baselines (Aug 2022)",
  )
  await expect(page.locator(".policy-baseline-marker")).toHaveCount(6)
})

test.describe("controlled Supabase fixture modes", () => {
  test.describe.configure({ mode: "serial" })

  test.describe("all views fail", () => {
    useFixtureMode("all-views-fail")

    test("shows expandable partial-data detail when registry views fail", async ({
      page,
    }) => {
      await page.goto(FIXTURE_APP_URL)

      const status = page.getByTestId("data-status")
      await expect(status).toHaveAttribute("data-mode", "degraded")
      await expect(status).toContainText("PARTIAL DATA: 10 sources failing")
      await status.locator("summary").click()
      await expect(status.locator(".data-status-errors li")).toHaveCount(10)
      await expect(status.locator(".data-status-errors")).toContainText(
        "v_current_pci: 500",
      )
    })
  })

  test.describe("stale timestamps", () => {
    useFixtureMode("stale-timestamps")

    test("shows stale source age when refresh timestamps are old", async ({
      page,
    }) => {
      await page.goto(FIXTURE_APP_URL)

      const status = page.getByTestId("data-status")
      await expect(status).toHaveAttribute("data-mode", "stale")
      await expect(status).toContainText(
        "STALE: last source refresh Jan 1, 2020",
      )
      await expect(status).toContainText(/\(\d+ days ago\)/)
    })
  })

  test.describe("empty views", () => {
    useFixtureMode("empty-views")

    test("marks hardcoded rows and reports zero history for empty views", async ({
      page,
    }) => {
      await page.goto(FIXTURE_APP_URL)

      await expect(page.getByTestId("data-status")).toHaveAttribute(
        "data-mode",
        "live",
      )
      await expect(page.locator(".policy-baseline-marker")).toHaveCount(6)
      await expect(
        page.locator(".policy-accordion-trigger .row-spark-empty").first(),
      ).toHaveText("0 weeks of history")

      await page.locator(".policy-accordion-trigger").first().click()
      await expect(page.locator(".trend-history-placeholder")).toContainText(
        "0 weeks of history",
      )
    })
  })
})

test("shows a subtle update date for the normal live fixture", async ({ page }) => {
  await page.goto("/")

  const status = page.getByTestId("data-status")
  await expect(status).toHaveAttribute("data-mode", "live")
  await expect(status).toContainText(/Updated [A-Z][a-z]{2} \d{1,2}, \d{4}/)
})

test("charts two moving weeks and labels genuinely flat history", async ({
  page,
}) => {
  await page.goto("/")
  const search = page.getByPlaceholder("Search vertical, provision, agency, or document")

  await search.fill("30D")
  await page.locator(".policy-accordion-trigger", { hasText: "30D" }).click()
  const movingTrend = page.locator(".policy-score-trend")
  await expect(movingTrend).toHaveAttribute("aria-label", "30D PCI score trend")
  await expect(movingTrend.locator("circle")).toHaveCount(2)
  await expect(movingTrend.locator(".trend-history-meta")).toContainText(
    "2 weeks of history",
  )
  await expect(movingTrend.locator(".trend-history-meta")).toContainText(
    "Last change May 18",
  )

  await search.fill("50141")
  await page.locator(".policy-accordion-trigger", { hasText: "50141" }).click()
  const flatTrend = page.locator(".policy-score-trend")
  await expect(flatTrend.locator(".trend-baseline")).toContainText(
    "Holding at the Aug 15 baseline",
  )
  await expect(flatTrend.locator(".trend-history-meta")).toContainText(
    "Last change Aug 15",
  )
})
