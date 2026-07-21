// Ported from apps/web/lib/changes.ts — keep in sync.
import type { RegistryData } from "./data.ts"
import {
  citationHrefForPolicyEvent,
  evidenceForPolicyEvent,
} from "./source-links.ts"
import { baselineVerticals } from "./verticals.ts"

const DELIVERY_VIEWS = ["v_policy_events", "v_evidence_items", "v_source_links"]
const SINCE_PATTERN =
  /^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|z|[+-]\d{2}:?\d{2})?)?$/

export const DELIVERY_LIMIT_MAX = 500
export const DELIVERY_LIMIT_DEFAULT_API = 100
export const DELIVERY_LIMIT_DEFAULT_MCP = 50

export type ChangeEvent = {
  id: string
  headline: string | null
  title: string | null
  verticals: string[]
  provision: {
    code: string
    name: string
  }
  week: string
  week_start: string
  recorded_at: string
  agency: string | null
  pci_delta: number
  dimension_deltas: Record<string, number>
  rationale: string | null
  confidence: number | null
  method_version: string | null
  source: {
    url: string | null
    title: string | null
    name: string | null
    quote: string | null
  }
}

export function buildChanges(
  data: Pick<
    RegistryData,
    "policyEvents" | "evidenceItems" | "sourceLinks"
  >,
  opts: { since?: string; vertical?: string; limit?: number } = {},
): ChangeEvent[] {
  const verticals = baselineVerticals()
  const selectedVertical = opts.vertical
    ? verticals.find((vertical) => vertical.id === opts.vertical)
    : null
  const selectedProvisions = new Set(selectedVertical?.provisions ?? [])
  const sinceTime = opts.since ? new Date(opts.since).getTime() : null
  const events = data.policyEvents
    .filter((event) => {
      if (opts.vertical && !selectedProvisions.has(event.provision)) return false

      if (sinceTime !== null) {
        const recordedAt = new Date(event.created_at).getTime()
        if (Number.isNaN(recordedAt) || recordedAt < sinceTime) return false
      }

      return true
    })
    .sort((a, b) => {
      const aRecordedAt = dateValue(a.created_at)
      const bRecordedAt = dateValue(b.created_at)
      if (aRecordedAt !== bRecordedAt) return bRecordedAt > aRecordedAt ? 1 : -1
      if (a.event_id < b.event_id) return -1
      if (a.event_id > b.event_id) return 1
      return 0
    })

  return (opts.limit === undefined ? events : events.slice(0, opts.limit)).map(
    (event) => {
      const matchedVerticals = verticals.filter((vertical) =>
        vertical.provisions.includes(event.provision),
      )
      const verticalIds = matchedVerticals.map((vertical) => vertical.id)
      const primaryName = matchedVerticals[0]?.name ?? null
      const evidence = evidenceForPolicyEvent(event, data)
      const firstEvidence = evidence[0]
      const sourceUrl = citationHrefForPolicyEvent(event, data)

      return {
        id: event.event_id,
        headline:
          primaryName && event.title ? `${primaryName}: ${event.title}` : event.title,
        title: event.title,
        verticals: verticalIds,
        provision: {
          code: event.provision,
          name: event.provision_name,
        },
        week: event.week,
        week_start: event.week_start,
        recorded_at: event.created_at,
        agency: event.agency ?? event.doc_source ?? null,
        pci_delta: event.pci_delta,
        dimension_deltas: event.dimension_deltas,
        rationale: event.rationale,
        confidence: event.confidence,
        method_version: event.prompt_version ?? null,
        source: {
          url: sourceUrl,
          title: firstEvidence?.source_title ?? event.title,
          name: firstEvidence
            ? (firstEvidence.source_name ?? firstEvidence.agency)
            : (event.agency ?? event.doc_source ?? null),
          quote: firstEvidence
            ? (firstEvidence.citation_quote ?? firstEvidence.snippet)
            : null,
        },
      }
    },
  )
}

export function deliveryError(
  data: Pick<RegistryData, "connected" | "viewErrors">,
): string | null {
  if (!data.connected) return "Registry is not configured."
  const error = data.viewErrors.find((item) =>
    DELIVERY_VIEWS.some((view) => item.startsWith(`${view}:`)),
  )
  return error ?? null
}

export function normalizeSince(value: string): string | null {
  const trimmed = value.trim()
  if (!SINCE_PATTERN.test(trimmed)) return null
  const hasTime = /[T ]\d{2}:\d{2}/.test(trimmed)
  const hasZone = /(Z|z|[+-]\d{2}:?\d{2})$/.test(trimmed)
  const candidate =
    hasTime && !hasZone
      ? `${trimmed.replace(" ", "T")}Z`
      : trimmed.replace(" ", "T")
  const parsed = new Date(candidate)
  return Number.isNaN(parsed.getTime()) ? null : parsed.toISOString()
}

export function logDeliveryHit(
  surface: "feed" | "feed_vertical" | "changes_api" | "mcp_list_changes",
  vertical: string | null,
  extra?: Record<string, unknown>,
) {
  console.log(
    JSON.stringify({
      metric: "delivery_hit",
      surface,
      vertical,
      ...(extra ?? {}),
    }),
  )
}

function dateValue(value: string) {
  const parsed = new Date(value).getTime()
  return Number.isNaN(parsed) ? Number.NEGATIVE_INFINITY : parsed
}
