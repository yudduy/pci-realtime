import { RegistryDashboard } from "@/components/registry-dashboard"
import { getRegistryData } from "@/lib/data"

export const dynamic = "force-dynamic"

export default async function DashboardPage() {
  const data = await getRegistryData()
  return <RegistryDashboard data={data} />
}
