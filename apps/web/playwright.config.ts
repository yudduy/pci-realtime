import { defineConfig, devices } from "@playwright/test"

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:8511",
    trace: "on-first-retry",
  },
  webServer: [
    {
      command: "node tests/e2e/mock-supabase.mjs",
      reuseExistingServer: false,
      timeout: 120_000,
      url: "http://127.0.0.1:8787/health",
    },
    {
      command:
        "NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:8787 NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=test npm run dev -- --hostname 127.0.0.1 --port 8511",
      reuseExistingServer: false,
      timeout: 120_000,
      url: "http://127.0.0.1:8511",
    },
  ],
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile-chromium", use: { ...devices["Pixel 5"] } },
  ],
})
