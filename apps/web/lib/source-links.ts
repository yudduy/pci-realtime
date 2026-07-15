import type { EvidenceItem, PolicyEvent, RegistryData } from "@/lib/data"

const TEXT_FRAGMENT_MAX = 280

export function evidenceForPolicyEvent(
  event: PolicyEvent,
  data: Pick<RegistryData, "evidenceItems" | "sourceLinks">,
  limit = 2,
) {
  const evidenceIds = new Set(
    data.sourceLinks
      .filter(
        (link) =>
          link.target_table === "policy_events" && link.target_id === event.event_id,
      )
      .map((link) => link.evidence_id),
  )

  return data.evidenceItems
    .filter((item) => evidenceIds.has(item.evidence_id))
    .slice(0, limit)
}

export function citationHrefForPolicyEvent(
  event: PolicyEvent,
  data: Pick<RegistryData, "evidenceItems" | "sourceLinks">,
) {
  const evidence = evidenceForPolicyEvent(event, data)

  for (const item of evidence) {
    const href = citationHref(item.canonical_url ?? item.url ?? event.url, item)
    if (href) return href
  }

  return event.url
}

export function citationHref(baseUrl: string | null | undefined, item: EvidenceItem) {
  const base = cleanHttpUrl(baseUrl)
  if (!base) return null

  const explicitFragment = item.citation_url_fragment?.trim()
  if (explicitFragment) return appendFragment(base, explicitFragment)

  const quote = compactCitationText(item.citation_quote)
  if (!quote) return base

  if (isPdfUrl(base)) {
    return appendFragment(base, `search=${encodeURIComponent(quote)}`)
  }

  return appendFragment(base, `:~:text=${encodeURIComponent(quote)}`)
}

function cleanHttpUrl(value: string | null | undefined) {
  if (!value) return null
  const trimmed = value.trim()
  if (!/^https?:\/\//i.test(trimmed)) return null
  return trimmed
}

function appendFragment(baseUrl: string, fragment: string) {
  if (/^https?:\/\//i.test(fragment)) return fragment

  const baseWithoutFragment = baseUrl.split("#")[0]
  const cleanFragment = fragment.startsWith("#") ? fragment.slice(1) : fragment
  return `${baseWithoutFragment}#${cleanFragment}`
}

function compactCitationText(value: string | null | undefined) {
  const compact = value?.replace(/\s+/g, " ").trim()
  if (!compact) return null
  const points = [...compact]
  return points.length > TEXT_FRAGMENT_MAX
    ? points.slice(0, TEXT_FRAGMENT_MAX).join("").trim()
    : compact
}

function isPdfUrl(value: string) {
  return /\.pdf(?:[?#]|$)/i.test(value)
}
