import { McpServer } from "npm:@modelcontextprotocol/sdk@1.25.3/server/mcp.js"
import { WebStandardStreamableHTTPServerTransport } from "npm:@modelcontextprotocol/sdk@1.25.3/server/webStandardStreamableHttp.js"
import { z } from "npm:zod@3"
import type {
  EvidenceItem,
  PolicyEvent,
  RegistryData,
  VerticalPci,
} from "./lib/data.ts"
import {
  buildChanges,
  DELIVERY_LIMIT_DEFAULT_MCP,
  DELIVERY_LIMIT_MAX,
  deliveryError,
  logDeliveryHit,
  normalizeSince,
} from "./lib/changes.ts"
import { getDeliveryData, getRegistryData } from "./lib/data.ts"
import { buildPolicyIntelligence } from "./lib/intelligence.ts"
import { POLICIES } from "./lib/policy-copy.ts"
import {
  citationHref,
  citationHrefForPolicyEvent,
  evidenceForPolicyEvent,
} from "./lib/source-links.ts"
import {
  baselineVertical,
  baselineVerticals,
  isVerticalId,
  UNSCORED_VERTICALS,
  VERTICAL_IDS,
} from "./lib/verticals.ts"

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

const verticalIdInput = z
  .string()
  .trim()
  .min(1)
  .transform((value) => value.toLowerCase())
  .refine(isVerticalId, {
    message: `Unknown vertical. Valid ids: ${VERTICAL_IDS.join(", ")}`,
  })

const sinceInput = z
  .string()
  .trim()
  .refine((value) => normalizeSince(value) !== null, {
    message: "Use ISO 8601, e.g. 2026-07-01",
  })

export function createServer() {
  const server = new McpServer({ name: "pcindex", version: "0.1.0" })

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

    server.registerTool(
      "list_verticals",
      {
        title: "list_verticals",
        description: "List climate-tech verticals and their current weighted PCI.",
        inputSchema: z.object({}),
        annotations: READ_ONLY,
      },
      async () => {
        const data = await getRegistryData()
        return asJson({
          verticals: verticalRows(data),
          uncovered: [...UNSCORED_VERTICALS],
          source: data.connected ? "registry" : "baseline",
        })
      },
    )

    server.registerTool(
      "vertical_status",
      {
        title: "vertical_status",
        description: "Read one climate-tech vertical and its provision-level status.",
        inputSchema: z.object({
          vertical_id: verticalIdInput,
        }),
        annotations: READ_ONLY,
      },
      async ({ vertical_id }) => {
        const data = await getRegistryData()
        const fallback = baselineVertical(vertical_id)
        const vertical =
          verticalRows(data).find((item) => item.id === vertical_id) ?? fallback
        const currentByCode = new Map(
          data.currentPci.map((policy) => [policy.code, policy]),
        )
        return asJson({
          vertical,
          provisions: fallback.provisions.map(
            (code) => currentByCode.get(code) ?? baselineProvision(code),
          ),
          source: data.connected ? "registry" : "baseline",
        })
      },
    )

    server.registerTool(
      "list_changes",
      {
        title: "list_changes",
        description: "List cited policy-change events since a timestamp, vertical-first.",
        inputSchema: z.object({
          since: sinceInput.optional(),
          vertical: verticalIdInput.optional(),
          limit: z.number().int().min(1).max(DELIVERY_LIMIT_MAX).optional(),
        }),
        annotations: READ_ONLY,
      },
      async ({ since, vertical, limit }) => {
        const normalizedSince = since
          ? (normalizeSince(since) ?? undefined)
          : undefined
        const data = await getDeliveryData()
        const error = deliveryError(data)
        if (error) throw new Error(error)
        const changes = buildChanges(data, {
          since: normalizedSince,
          vertical,
          limit: limit ?? DELIVERY_LIMIT_DEFAULT_MCP,
        })

        logDeliveryHit("mcp_list_changes", vertical ?? null)

        return asJson({
          changes,
          count: changes.length,
          since: normalizedSince ?? null,
          vertical: vertical ?? null,
          source: "registry",
        })
      },
    )

  return server
}

function policyEvents(data: RegistryData, code: string) {
  return data.policyEvents
    .filter((event) => event.provision === code)
    .sort((a, b) => dateValue(b.week_start) - dateValue(a.week_start))
}

function evidenceForPolicy(data: RegistryData, code: string) {
  const eventIds = new Set(
    data.policyEvents
      .filter((event) => event.provision === code)
      .map((event) => event.event_id),
  )
  const evidenceIds = new Set(
    data.sourceLinks
      .filter(
        (link) =>
          link.target_table === "policy_events" && eventIds.has(link.target_id),
      )
      .map((link) => link.evidence_id),
  )
  return data.evidenceItems.filter(
    (item) => item.provision === code || evidenceIds.has(item.evidence_id),
  )
}

function verticalRows(data: RegistryData): VerticalPci[] {
  if (!data.connected) return baselineVerticals()
  const error = data.viewErrors.find((item) => item.startsWith("v_vertical_pci:"))
  if (error) throw new Error(error)
  return data.verticals
}

function baselineProvision(code: string) {
  const policy = POLICIES.find((item) => item.code === code)
  if (!policy) throw new Error(`Unknown provision: ${code}`)
  return {
    code,
    name:
      code === "50144" ? "Energy Infrastructure Reinvestment" : policy.name,
    pci: policy.baseline,
    specificity: policy.specificity,
    durability: policy.durability,
    enforceability: policy.enforceability,
    baseline_pci: policy.baseline,
    source: "baseline",
  }
}

function eventPayload(event: PolicyEvent, data: RegistryData) {
  return {
    event_id: event.event_id,
    provision: event.provision,
    week: event.week,
    week_start: event.week_start,
    agency: event.agency ?? event.doc_source,
    title: event.title,
    pci_delta: event.pci_delta,
    dimension_deltas: event.dimension_deltas,
    source_url: citationHrefForPolicyEvent(event, data) ?? event.url,
    evidence_ids: evidenceForPolicyEvent(event, data).map((item) => item.evidence_id),
  }
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

const CORS_HEADERS = {
  "access-control-allow-origin": "*",
  "access-control-allow-headers":
    "authorization, content-type, accept, mcp-session-id, mcp-protocol-version",
  "access-control-expose-headers": "mcp-session-id",
  "access-control-allow-methods": "GET, POST, DELETE, OPTIONS",
}

function withCors(response: Response) {
  const headers = new Headers(response.headers)
  for (const [name, value] of Object.entries(CORS_HEADERS)) {
    headers.set(name, value)
  }
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  })
}

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: CORS_HEADERS })
  }

  const server = createServer()
  const transport = new WebStandardStreamableHTTPServerTransport()
  await server.connect(transport)
  const response = await transport.handleRequest(request)
  return withCors(response)
})
