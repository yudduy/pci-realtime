import type { RegistryData } from "@/lib/data"
import type { PolicyIntelligence } from "@/lib/intelligence"
import { citationHrefForPolicyEvent } from "@/lib/source-links"

export type PolicyHeadline = {
  id: string
  code: string
  policyName: string | null
  title: string
  source: string
  date: string | null
  delta: number | null
  href: string
}

type HeadlinePolicy = Pick<
  PolicyIntelligence,
  | "code"
  | "name"
>

export function buildPolicyHeadlines(
  data: RegistryData,
  policies: HeadlinePolicy[],
  limit = 8,
): PolicyHeadline[] {
  const names = new Map(policies.map((policy) => [policy.code, policy.name]))

  return data.policyEvents
    .map((event) => {
      const policyName = event.provision_name || names.get(event.provision) || null
      const title = headlineTitle(event.title, policyName)
      const href = citationHrefForPolicyEvent(event, data)
      const source = event.agency ?? event.doc_source ?? null

      if (!title || !href || !source || !isMaterialMovement(event.pci_delta)) {
        return null
      }

      const update: PolicyHeadline = {
        id: event.event_id,
        code: event.provision,
        policyName,
        title,
        source,
        date: event.week_start ?? event.scored_at ?? event.created_at,
        delta: event.pci_delta,
        href,
      }

      return update
    })
    .filter((update): update is PolicyHeadline => Boolean(update))
    .filter((update, index, updates) => {
      const key = `${update.code}:${normalize(update.title)}:${dayKey(update.date)}`
      return (
        updates.findIndex(
          (candidate) =>
            `${candidate.code}:${normalize(candidate.title)}:${dayKey(candidate.date)}` === key,
        ) === index
      )
    })
    .sort((a, b) => dateValue(b.date) - dateValue(a.date))
    .slice(0, limit)
}

function headlineTitle(title: string | null | undefined, policyName: string | null) {
  return isUsefulHeadline(title, policyName) ? title ?? null : null
}

function isUsefulHeadline(value: string | null | undefined, policyName: string | null) {
  const normalized = normalize(value)
  if (!normalized || normalized.length < 12) return false
  if (normalized === normalize(policyName)) return false
  return ![
    "official policy update",
    "policy update",
    "evidence update",
    "official source",
  ].includes(normalized)
}

function isMaterialMovement(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value) && Math.abs(value) >= 0.005
}

function normalize(value: string | null | undefined) {
  return value?.trim().replace(/\s+/g, " ").toLowerCase() ?? ""
}

function dayKey(value: string | null | undefined) {
  if (!value) return ""
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toISOString().slice(0, 10)
}

function dateValue(value: string | null | undefined) {
  if (!value) return 0
  const date = new Date(value).getTime()
  return Number.isNaN(date) ? 0 : date
}
