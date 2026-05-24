import { defineConfig, devices } from "@playwright/test"

export default defineConfig({
  testDir: "./tests/live",
  fullyParallel: true,
  reporter: "list",
  use: {
    baseURL: process.env.PCI_E2E_LIVE_URL ?? "http://127.0.0.1:8510",
    trace: "on-first-retry",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile-chromium", use: { ...devices["Pixel 5"] } },
  ],
})
