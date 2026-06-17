import type { PolicyTerminalData } from "@/components/policy/terminal"
import { buildPolicyHeadlines } from "@/lib/headlines"
import { buildPolicyIntelligence } from "@/lib/intelligence"
import { latestCompletedRun } from "@/lib/market-model"
import { getRegistryData, type PolicyEvent, type RegistryData } from "@/lib/data"
import {
  citationHrefForPolicyEvent,
  evidenceForPolicyEvent,
} from "@/lib/source-links"

export async function getPolicyTerminalData(): Promise<PolicyTerminalData> {
  const data = await getRegistryData()
  const policies = buildPolicyIntelligence(data).map((policy) => ({
    code: policy.code,
    name: policy.name,
    formalName: policy.formalName,
    lane: policy.lane,
    question: policy.question,
    currentPci: policy.currentPci,
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
    latestRefreshAt: policy.latestRefreshAt,
    timeline: policyTimeline(data, policy.code, policy.currentPci, policy.updatedAt),
  }))
  const run = latestCompletedRun(data)
  const lastSourceRefresh =
    latestDate(data.sourceHealth.map((source) => source.last_success_at)) ??
    run?.completed_at ??
    run?.started_at ??
    null

  return {
    policies,
    connected: data.connected,
    viewErrors: data.viewErrors,
    lastSourceRefresh,
    recentUpdates: buildPolicyHeadlines(data, policies, 8),
  }
}

function policyTimeline(
  data: RegistryData,
  code: string,
  currentPci: number | null,
  updatedAt: string | null,
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
