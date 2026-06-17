import { redirect } from "next/navigation"

type LegacyPolicyPageProps = {
  params: Promise<{ code: string }>
}

export default async function LegacyPolicyPage({ params }: LegacyPolicyPageProps) {
  const { code } = await params
  redirect(`/dashboard#policy-${code.toUpperCase()}`)
}
