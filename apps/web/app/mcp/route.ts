import { createMcpHandler } from "mcp-handler"
import { z } from "zod"
import type { EvidenceItem, PolicyEvent, RegistryData } from "@/lib/data"
import { getRegistryData } from "@/lib/data"
import { buildPolicyIntelligence } from "@/lib/intelligence"
import { POLICIES } from "@/lib/policy-copy"
import { citationHref } from "@/lib/source-links"

export const dynamic = "force-dynamic"
export const runtime = "nodejs"
export const maxDuration = 60

const POLICY_CODES = POLICIES.map((policy) => policy.code)
const READ_ONLY = { readOnlyHint: true, openWorldHint: true }

const policyCodeInput = z
  .string()
  .trim()
  .min(1)
  .transform((value) => value.toUpperCase())
  .refine((value) => POLICY_CODES.includes(value), {
    message: `Use one of: ${POLICY_CODES.join(", ")}`,
  })

const handler = createMcpHandler(
  async (server) => {
    server.registerTool(
      "status",
      {
        title: "status",
        description: "Check the hosted PCIndex registry and MCP readiness.",
        inputSchema: z.object({}),
        annotations: READ_ONLY,
      },
      async () => {
        const data = await getRegistryData()
        return asJson({
          reachable: data.connected && data.viewErrors.length === 0,
          registry_configured: data.connected,
          hosted_mcp: true,
          mode: "read_only",
          write_tools: "local_connector_only",
          tracked_policies: POLICY_CODES.length,
          view_errors: data.viewErrors,
        })
      },
    )

    server.registerTool(
      "list_policies",
      {
        title: "list_policies",
        description: "List tracked PCIndex policy units.",
        inputSchema: z.object({}),
        annotations: READ_ONLY,
      },
      async () => {
        const data = await getRegistryData()
        const policies = buildPolicyIntelligence(data).map((policy) => ({
          code: policy.code,
          name: policy.name,
          formal_name: policy.formalName,
          lane: policy.lane,
          current_pci: policy.currentPci,
          updated_at: policy.updatedAt,
          latest_evidence_title: policy.latestEvidenceTitle,
          latest_evidence_source: policy.latestEvidenceSource,
        }))
        return asJson({ policies, count: policies.length })
      },
    )

    server.registerTool(
      "current_pci",
      {
        title: "current_pci",
        description: "Read current PCI for one tracked policy or all policies.",
        inputSchema: z.object({
          code: policyCodeInput.optional(),
        }),
        annotations: READ_ONLY,
      },
      async ({ code }) => {
        const data = await getRegistryData()
        const policies = buildPolicyIntelligence(data).map((policy) => ({
          code: policy.code,
          name: policy.name,
          current_pci: policy.currentPci,
          delta: policy.weeklyDelta,
          specificity: policy.specificity,
          durability: policy.durability,
          enforceability: policy.enforceability,
          updated_at: policy.updatedAt,
          latest_evidence_at: policy.latestEvidenceAt,
          latest_evidence_title: policy.latestEvidenceTitle,
          latest_evidence_source: policy.latestEvidenceSource,
        }))
        const rows = code ? policies.filter((policy) => policy.code === code) : policies
        return asJson({ policies: rows, source: "hosted_mcp_read_only" })
      },
    )

    server.registerTool(
      "policy_dossier",
      {
        title: "policy_dossier",
        description: "Read policy score, timeline, evidence, and cited source links.",
        inputSchema: z.object({
          code: policyCodeInput,
        }),
        annotations: READ_ONLY,
      },
      async ({ code }) => {
        const data = await getRegistryData()
        const policies = buildPolicyIntelligence(data)
        const policy = policies.find((item) => item.code === code) ?? null
        const events = policyEvents(data, code)
        const evidence = evidenceForPolicy(data, code)
        const timeline = data.provisionTimelines
          .filter((row) => row.provision === code)
          .map((row) => ({
            week: row.week,
            week_start: row.week_start,
            pci: row.pci,
            delta: row.delta_this_week,
            specificity: row.specificity,
            durability: row.durability,
            enforceability: row.enforceability,
            source_event_ids: row.source_event_ids,
          }))

        return asJson({
          policy,
          timeline,
          events: events.map((event) => eventPayload(event, data)),
          evidence: evidence.map(evidencePayload),
        })
      },
    )

    server.registerTool(
      "get_evidence_trace",
      {
        title: "get_evidence_trace",
        description: "Verify evidence rows and source links for a policy.",
        inputSchema: z.object({
          provision: policyCodeInput,
          evidence_id: z.string().trim().min(1).optional(),
        }),
        annotations: READ_ONLY,
      },
      async ({ provision, evidence_id }) => {
        const data = await getRegistryData()
        const evidence = evidenceForPolicy(data, provision).filter((item) =>
          evidence_id ? item.evidence_id === evidence_id : true,
        )
        const evidenceIds = new Set(evidence.map((item) => item.evidence_id))
        const links = data.sourceLinks.filter((link) => evidenceIds.has(link.evidence_id))
        const events = policyEvents(data, provision)

        return asJson({
          provision,
          evidence: evidence.map(evidencePayload),
          links,
          events: events.map((event) => eventPayload(event, data)),
        })
      },
    )
  },
  {
    serverInfo: {
      name: "pcindex",
      version: "0.1.0",
    },
  },
  {
    basePath: "",
    disableSse: true,
    maxDuration: 60,
  },
)

function policyEvents(data: RegistryData, code: string) {
  return data.policyEvents
    .filter((event) => event.provision === code)
    .sort((a, b) => dateValue(b.week_start) - dateValue(a.week_start))
}

function evidenceForPolicy(data: RegistryData, code: string) {
  const eventIds =
    data.policyEvents
      .filter((event) => event.provision === code)
      .map((event) => event.event_id)
  const linkedEvidenceIds = evidenceIdsForEvents(data, eventIds)
  return verifiedPolicyEvidence(
    data,
    (item) => item.provision === code || linkedEvidenceIds.has(item.evidence_id),
  )
}

function eventPayload(event: PolicyEvent, data: RegistryData) {
  const evidence = verifiedEvidenceForEvent(event, data)
  return {
    event_id: event.event_id,
    provision: event.provision,
    week: event.week,
    week_start: event.week_start,
    agency: event.agency ?? event.doc_source,
    title: event.title,
    pci_delta: event.pci_delta,
    dimension_deltas: event.dimension_deltas,
    source_url:
      evidence
        .map((item) => citationHref(item.canonical_url ?? item.url ?? event.url, item))
        .find((href): href is string => Boolean(href)) ?? event.url,
    evidence_ids: evidence.map((item) => item.evidence_id),
  }
}

function verifiedEvidenceForEvent(event: PolicyEvent, data: RegistryData) {
  const evidenceIds = evidenceIdsForEvents(data, [event.event_id])
  return verifiedPolicyEvidence(data, (item) =>
    evidenceIds.has(item.evidence_id),
  )
}

function evidenceIdsForEvents(data: RegistryData, eventIds: Iterable<string>) {
  const ids = new Set(eventIds)
  return new Set(
    data.sourceLinks
      .filter(
        (link) =>
          link.target_table === "policy_events" && ids.has(link.target_id),
      )
      .map((link) => link.evidence_id),
  )
}

function verifiedPolicyEvidence(
  data: RegistryData,
  include: (item: EvidenceItem) => boolean,
) {
  return data.policyEvidenceItems.filter(
    (item) => item.quote_verified_against_source === true && include(item),
  )
}

function evidencePayload(item: EvidenceItem) {
  return {
    evidence_id: item.evidence_id,
    provision: item.provision,
    source_title: item.source_title,
    source_name: item.source_name ?? item.agency,
    citation_quote: item.citation_quote ?? item.snippet,
    citation_section: item.citation_section,
    score_dimension: item.score_dimension,
    normalized_signal: item.normalized_signal,
    confidence: item.confidence,
    quote_verified_against_source: item.quote_verified_against_source,
    source_url: citationHref(item.canonical_url ?? item.url, item),
    published_at: item.published_at,
    created_at: item.created_at,
  }
}

function asJson(payload: unknown) {
  return {
    content: [
      {
        type: "text" as const,
        text: JSON.stringify(payload, null, 2),
      },
    ],
  }
}

function dateValue(value: string | null | undefined) {
  if (!value) return 0
  const date = new Date(value).getTime()
  return Number.isNaN(date) ? 0 : date
}

export { handler as GET, handler as POST, handler as DELETE }
