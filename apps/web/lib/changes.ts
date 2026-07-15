import type { EvidenceItem, PolicyEvent, RegistryData } from "@/lib/data"
import { getRegistryData } from "@/lib/data"
import {
  citationHref,
  citationHrefForPolicyEvent,
  evidenceForPolicyEvent,
} from "@/lib/source-links"
import { baselineVerticals, isVerticalId, VERTICAL_IDS } from "@/lib/verticals"

export const DEFAULT_CHANGE_LIMIT = 50
export const MAX_CHANGE_LIMIT = 200

const DIMENSION_NAMES = [
  "specificity",
  "durability",
  "enforceability",
] as const

export type ChangeRecord = {
  id: string
  date: string
  verticals: string[]
  provisions: string[]
  title: string
  summary: string
  pci_delta: number | null
  dimensions: {
    specificity: number | null
    durability: number | null
    enforceability: number | null
  } | null
  citation: {
    url: string | null
    quote: string | null
    source_name: string | null
    published_at: string | null
  }
  method: {
    schema_version?: string
    method_version?: string
    prompt_version?: string
  } | null
}

export type ChangesResponse = {
  as_of: string
  count: number
  changes: ChangeRecord[]
}

export type ChangesQuery = {
  since?: string | null
  vertical?: string | null
  limit?: number
}

export class ChangesQueryError extends Error {
  readonly validVerticals?: string[]

  constructor(message: string, validVerticals?: string[]) {
    super(message)
    this.name = "ChangesQueryError"
    this.validVerticals = validVerticals
  }
}

export async function getChanges(query: ChangesQuery = {}): Promise<ChangesResponse> {
  const data = await getRegistryData()
  return buildChanges(data, query)
}

export function buildChanges(
  data: RegistryData,
  query: ChangesQuery = {},
  asOf = new Date(),
): ChangesResponse {
  const { since, vertical, limit } = normalizeQuery(query)
  const changes = data.policyEvents
    .map((event) => changeRecord(event, data))
    .filter((change): change is ChangeRecord => change !== null)
    .filter((change) => (since ? change.date >= since : true))
    .filter((change) => (vertical ? change.verticals.includes(vertical) : true))
    .sort(
      (left, right) =>
        right.date.localeCompare(left.date) || left.id.localeCompare(right.id),
    )
    .slice(0, limit)

  return {
    as_of: asOf.toISOString(),
    count: changes.length,
    changes,
  }
}

export function deliveryKey(vertical: string | null | undefined) {
  const normalized = vertical?.trim().toLowerCase()
  if (!normalized) return "all"
  return isVerticalId(normalized) ? normalized : "unknown"
}

export function logDeliveryHit(
  surface: "api" | "feed" | "mcp",
  key: string,
) {
  console.log(JSON.stringify({ evt: "delivery_hit", surface, key }))
}

function normalizeQuery(query: ChangesQuery) {
  const since = normalizeSince(query.since)
  const vertical = query.vertical?.trim().toLowerCase() || null
  if (vertical && !isVerticalId(vertical)) {
    throw new ChangesQueryError(
      `Unknown vertical. Valid slugs: ${VERTICAL_IDS.join(", ")}`,
      [...VERTICAL_IDS],
    )
  }

  const limit = query.limit ?? DEFAULT_CHANGE_LIMIT
  if (!Number.isInteger(limit) || limit < 1 || limit > MAX_CHANGE_LIMIT) {
    throw new ChangesQueryError(
      `Limit must be an integer between 1 and ${MAX_CHANGE_LIMIT}.`,
    )
  }

  return { since, vertical, limit }
}

function normalizeSince(value: string | null | undefined) {
  const since = value?.trim()
  if (!since) return null
  if (!/^\d{4}-\d{2}-\d{2}$/.test(since) || !isCalendarDate(since)) {
    throw new ChangesQueryError("Since must be a valid date in YYYY-MM-DD format.")
  }
  return since
}

function isCalendarDate(value: string) {
  const parsed = new Date(`${value}T00:00:00.000Z`)
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value
}

function changeRecord(event: PolicyEvent, data: RegistryData): ChangeRecord | null {
  const date = dateOnly(event.week_start ?? event.scored_at ?? event.created_at)
  if (!date) return null

  const provisions = eventProvisions(event)
  const verticals = baselineVerticals()
    .filter((vertical) =>
      vertical.provisions.some((code) => provisions.includes(code)),
    )
    .map((vertical) => vertical.id)
  const citation = eventCitation(event, data)

  return {
    id: event.event_id,
    date,
    verticals,
    provisions,
    title: cleanText(event.title) ?? "Official policy update",
    summary:
      cleanText(event.summary) ??
      cleanText(event.claim) ??
      cleanText(event.rationale) ??
      "",
    pci_delta: finiteNumber(event.pci_delta),
    dimensions: eventDimensions(event),
    citation,
    method: eventMethod(event),
  }
}

function eventProvisions(event: PolicyEvent) {
  const values = Array.isArray(event.provisions)
    ? event.provisions
    : [event.provision]
  return [...new Set(values.map((value) => cleanText(value)).filter(isString))]
}

function eventCitation(event: PolicyEvent, data: RegistryData) {
  const linkedEvidence = evidenceForPolicyEvent(event, data)
  let evidence: EvidenceItem | null = linkedEvidence[0] ?? null
  let url: string | null = null

  for (const item of linkedEvidence) {
    const href = citationHref(item.canonical_url ?? item.url ?? event.url, item)
    if (href) {
      evidence = item
      url = href
      break
    }
  }

  url ??= citationHrefForPolicyEvent(event, data)

  return {
    url: cleanText(url),
    quote: cleanText(evidence?.citation_quote ?? evidence?.snippet),
    source_name: cleanText(
      evidence?.source_name ??
        evidence?.agency ??
        evidence?.source ??
        event.agency ??
        event.doc_source,
    ),
    published_at: cleanText(evidence?.published_at),
  }
}

function eventDimensions(event: PolicyEvent): ChangeRecord["dimensions"] {
  const source = event.dimensions ?? event.dimension_scores ?? event.dimension_deltas
  if (!source || typeof source !== "object") return null

  const dimensions = {
    specificity: finiteNumber(source.specificity),
    durability: finiteNumber(source.durability),
    enforceability: finiteNumber(source.enforceability),
  }
  return DIMENSION_NAMES.some((name) => dimensions[name] !== null)
    ? dimensions
    : null
}

function eventMethod(event: PolicyEvent): ChangeRecord["method"] {
  const versions = {
    schema_version: cleanText(event.schema_version),
    method_version: cleanText(event.method_version),
    prompt_version: cleanText(event.prompt_version),
  }
  const method = Object.fromEntries(
    Object.entries(versions).filter((entry): entry is [string, string] =>
      Boolean(entry[1]),
    ),
  ) as NonNullable<ChangeRecord["method"]>
  return Object.keys(method).length ? method : null
}

function dateOnly(value: string | null | undefined) {
  const text = cleanText(value)
  if (!text) return null
  const direct = text.match(/^\d{4}-\d{2}-\d{2}/)?.[0]
  if (direct && isCalendarDate(direct)) return direct
  const parsed = new Date(text)
  return Number.isNaN(parsed.getTime()) ? null : parsed.toISOString().slice(0, 10)
}

function finiteNumber(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : null
}

function cleanText(value: string | null | undefined) {
  const text = value?.trim()
  return text || null
}

function isString(value: string | null): value is string {
  return value !== null
}
