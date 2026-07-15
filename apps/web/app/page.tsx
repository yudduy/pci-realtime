import { PolicyTerminal } from "@/components/policy/terminal"
import type { RegistryFixtureMode } from "@/lib/data"
import { getPolicyTerminalData } from "@/lib/terminal-data"

export const dynamic = "force-dynamic"

type HomeProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>
}

export default async function Home({ searchParams }: HomeProps) {
  const params = await searchParams
  const fixtureMode = e2eFixtureMode(params["mock-supabase-mode"])
  return <PolicyTerminal data={await getPolicyTerminalData(fixtureMode)} />
}

function e2eFixtureMode(
  value: string | string[] | undefined,
): RegistryFixtureMode | undefined {
  if (process.env.PCI_E2E_DATA_MODES !== "1" || typeof value !== "string") {
    return undefined
  }
  if (
    value === "all-views-fail" ||
    value === "empty-views" ||
    value === "stale-timestamps"
  ) {
    return value
  }
  return undefined
}
