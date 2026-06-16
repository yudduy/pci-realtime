import type { Metadata } from "next"
import { notFound } from "next/navigation"
import { PolicyDossier } from "@/components/policy/dossier"
import { getRegistryData } from "@/lib/data"
import { getPolicyIntelligence } from "@/lib/intelligence"

export const dynamic = "force-dynamic"

type PolicyPageProps = {
  params: Promise<{ code: string }>
}

export async function generateMetadata({
  params,
}: PolicyPageProps): Promise<Metadata> {
  const { code } = await params
  const data = await getRegistryData()
  const policy = getPolicyIntelligence(data, code)
  if (!policy) return { title: "Policy not found / PCIndex" }

  return {
    title: `${policy.code} ${policy.name} / PCIndex`,
    description: `${policy.formalName} credibility evidence, PCI state, source trace, and attribution.`,
  }
}

export default async function PolicyPage({ params }: PolicyPageProps) {
  const { code } = await params
  const data = await getRegistryData()
  const policy = getPolicyIntelligence(data, code)

  if (!policy) notFound()

  return <PolicyDossier data={data} policy={policy} />
}
