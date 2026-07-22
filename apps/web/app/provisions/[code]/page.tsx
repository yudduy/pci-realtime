import { RedirectToTerminal } from "@/components/layout/redirect-to-terminal"
import { POLICIES } from "@/lib/policy-copy"

export const dynamicParams = false

export function generateStaticParams() {
  return POLICIES.map(({ code }) => ({ code }))
}

type LegacyPolicyPageProps = {
  params: Promise<{ code: string }>
}

export default async function LegacyPolicyPage({ params }: LegacyPolicyPageProps) {
  const { code } = await params
  return <RedirectToTerminal target={`/#policy-${code.toUpperCase()}`} />
}
