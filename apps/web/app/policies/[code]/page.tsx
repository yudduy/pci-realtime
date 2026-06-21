import { redirect } from "next/navigation"

type PolicyPageProps = {
  params: Promise<{ code: string }>
}

export default async function PolicyPage({ params }: PolicyPageProps) {
  const { code } = await params
  redirect(`/#policy-${code.toUpperCase()}`)
}
