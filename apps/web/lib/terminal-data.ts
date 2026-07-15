import { buildPolicyHeadlines } from "@/lib/headlines"
import { buildPolicyIntelligence } from "@/lib/intelligence"
import {
  getRegistryData,
  type PolicyEvent,
  type RegistryData,
  type RegistryFixtureMode,
} from "@/lib/data"
import {
  citationHrefForPolicyEvent,
  evidenceForPolicyEvent,
} from "@/lib/source-links"
import { baselineVerticals } from "@/lib/verticals"

const DAY_MS = 24 * 60 * 60 * 1000
const STALE_AFTER_DAYS = 8

export type TerminalDataStatus = {
  mode: "live" | "stale" | "degraded" | "disconnected"
  lastSourceRefresh: string | null
  staleDays: number | null
  viewErrors: string[]
}

export async function getPolicyTerminalData(fixtureMode?: RegistryFixtureMode) {
  const data = await getRegistryData(fixtureMode)
  const policies = buildPolicyIntelligence(data).map((policy) => ({
    code: policy.code,
    name: policy.name,
    formalName: policy.formalName,
    lane: policy.lane,
    question: policy.question,
    currentPci: policy.currentPci,
    scoreOrigin: policy.scoreOrigin,
    scoreDelta: policy.weeklyDelta,
    specificity: policy.specificity,
    durability: policy.durability,
    enforceability: policy.enforceability,
    updatedAt: policy.updatedAt,
    latestEvidenceAt: policy.latestEvidenceAt,
    latestEvidenceTitle: policy.latestEvidenceTitle,
    latestEvidenceSource: policy.latestEvidenceSource,
    evidenceAnchorCount: policy.evidenceAnchorCount,
    attributionDrivers: policy.attributionDrivers,
    sourceReferences: policy.sourceReferences,
    timeline: policyTimeline(
      data,
      policy.code,
      policy.currentPci,
      policy.updatedAt,
      policy.scoreOrigin,
    ),
  }))
  const run = latestCompletedRun(data)
  const lastSourceRefresh =
    latestDate(data.sourceHealth.map((source) => source.last_success_at)) ??
    run?.completed_at ??
    run?.started_at ??
    null

  return {
    verticals: data.verticals.length ? data.verticals : baselineVerticals(),
    policies,
    dataStatus: deriveDataStatus(
      data.connected,
      data.viewErrors,
      lastSourceRefresh,
    ),
    recentUpdates: buildPolicyHeadlines(data, policies, 8),
  }
}

function policyTimeline(
  data: RegistryData,
  code: string,
  currentPci: number | null,
  updatedAt: string | null,
  scoreOrigin: "live" | "baseline_view" | "hardcoded_copy",
) {
  const rows = data.provisionTimelines
    .filter((row) => row.provision === code)
    .sort((a, b) => new Date(a.week_start).getTime() - new Date(b.week_start).getTime())
    .map((row) => {
      const events = eventsForTimelineRow(row, data.policyEvents)
      return {
        key: `${row.provision}-${row.week}`,
        date: row.week_start,
        value: row.pci,
        delta: row.delta_this_week,
        attributions: events.map((event) => eventAttribution(event, data)),
      }
    })

  if (rows.length) return rows
  if (scoreOrigin === "hardcoded_copy") return []
  return [
    {
      key: `${code}-current`,
      date: updatedAt,
      value: currentPci,
      delta: null,
      attributions: [],
    },
  ]
}

function deriveDataStatus(
  connected: boolean,
  viewErrors: string[],
  lastSourceRefresh: string | null,
): TerminalDataStatus {
  const refreshTime = lastSourceRefresh
    ? new Date(lastSourceRefresh).getTime()
    : Number.NaN
  const ageMs = Date.now() - refreshTime
  const staleDays = Number.isFinite(ageMs)
    ? Math.max(0, Math.floor(ageMs / DAY_MS))
    : null

  // Missing refresh metadata alone is neither a failed view nor proof of
  // staleness; rows still expose hardcoded fallbacks and history gaps.
  const mode = !connected
    ? "disconnected"
    : viewErrors.length > 0
      ? "degraded"
      : Number.isFinite(ageMs) && ageMs > STALE_AFTER_DAYS * DAY_MS
        ? "stale"
        : "live"

  return {
    mode,
    lastSourceRefresh,
    staleDays,
    viewErrors,
  }
}

function eventsForTimelineRow(
  row: RegistryData["provisionTimelines"][number],
  events: PolicyEvent[],
) {
  const ids = new Set(row.source_event_ids)
  const linked = ids.size
    ? events.filter((event) => ids.has(event.event_id))
    : []
  if (linked.length) return linked

  return events.filter(
    (event) =>
      event.provision === row.provision &&
      (event.week === row.week || event.week_start === row.week_start),
  )
}

function eventAttribution(event: PolicyEvent, data: RegistryData) {
  const evidence = evidenceForPolicyEvent(event, data)

  return {
    source: event.agency ?? event.doc_source ?? "Policy source",
    title: event.title ?? "Policy score update",
    rationale: event.rationale,
    url: citationHrefForPolicyEvent(event, data) ?? event.url,
    delta: event.pci_delta,
    quotes: evidence
      .map((item) => item.citation_quote ?? item.snippet ?? item.source_title)
      .filter((value): value is string => Boolean(value)),
  }
}

function latestDate(values: Array<string | null | undefined>) {
  return values.reduce<string | null>((latest, value) => {
    if (!value) return latest
    if (!latest) return value
    return new Date(value).getTime() > new Date(latest).getTime() ? value : latest
  }, null)
}

function latestCompletedRun(data: RegistryData) {
  return data.pipelineRuns.find((run) => run.status === "success") ?? data.pipelineRuns[0] ?? null
}
