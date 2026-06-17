import { PolicyTerminal } from "@/components/policy/terminal"
import { getPolicyTerminalData } from "@/lib/terminal-data"

export const dynamic = "force-dynamic"

export default async function DashboardPage() {
  return <PolicyTerminal data={await getPolicyTerminalData()} />
}
