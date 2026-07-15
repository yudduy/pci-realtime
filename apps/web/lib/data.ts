export type CurrentPci = {
  code: string
  name: string
  provision_type: string
  primary_channel: string
  paper_role?: string
  week: string | null
  week_start: string | null
  pci: number | null
  specificity: number | null
  durability: number | null
  enforceability: number | null
  delta_this_week: number | null
  data_origin: string | null
  baseline_pci: number
  updated_at: string | null
}

export type VerticalPci = {
  id: string
  name: string
  coverage_note: string
  display_order: number
  vertical_pci: number | null
  baseline_pci: number
  weekly_delta: number | null
  as_of_week_start: string | null
  last_change_week_start: string | null
  provisions: string[]
}

export type PolicyEvent = {
  event_id: string
  provision: string
  provisions?: string[]
  provision_name: string
  week: string
  week_start: string
  agency: string | null
  doc_id?: string
  doc_source?: string | null
  title: string | null
  url: string | null
  pci_delta: number
  dimension_deltas: Record<string, number>
  dimensions?: Record<string, number | null> | null
  dimension_scores?: Record<string, number | null> | null
  rationale: string | null
  claim?: string | null
  summary?: string | null
  confidence: number | null
  prompt_version?: string | null
  schema_version?: string | null
  method_version?: string | null
  scored_at?: string | null
  created_at: string
}

export type PipelineRun = {
  run_id: string
  run_type: string
  status: string
  started_at: string
  completed_at: string | null
  git_sha?: string | null
  source: string
  error_summary: string | null
  metadata: Record<string, unknown>
}

export type ProvisionTimeline = {
  provision: string
  name: string
  week: string
  week_start: string
  pci: number
  specificity: number
  durability: number
  enforceability: number
  n_docs: number
  delta_this_week: number
  data_origin: string
  source_event_ids: string[]
  provenance_status: string
}

export type EvidenceItem = {
  evidence_id: string
  source_doc_id: string | null
  provision: string | null
  provision_name: string | null
  evidence_type: string
  snippet: string | null
  normalized_signal: string | null
  score_dimension: string | null
  confidence: number | null
  extractor_version: string | null
  created_at: string
  citation_quote?: string | null
  citation_section?: string | null
  citation_page?: string | null
  citation_url_fragment?: string | null
  claim_hash?: string | null
  submitted_by_agent_run_id?: string | null
  extraction_confidence?: number | null
  raw_public_metadata?: Record<string, unknown>
  source: string | null
  source_name: string | null
  source_type: string | null
  source_title: string | null
  agency: string | null
  url: string | null
  canonical_url?: string | null
  published_at: string | null
  fetched_at: string | null
}

export type SourceDocument = {
  source_doc_id: string
  source: string
  source_name: string
  source_type: string
  external_id: string | null
  title: string
  agency: string | null
  url: string | null
  canonical_url?: string | null
  published_at: string | null
  fetched_at: string | null
  first_seen_at?: string | null
  last_seen_at?: string | null
  submitted_by_agent_run_id?: string | null
  text_excerpt: string | null
  raw_public_metadata: Record<string, unknown>
}

export type SourceLink = {
  link_id: string
  evidence_id: string
  target_table: string
  target_id: string
  link_type: string
  created_at: string
}

export type SourceHealth = {
  source: string
  source_name: string
  status: string
  last_attempt_at: string
  last_success_at: string | null
  latency_ms: number | null
  row_count: number
  last_error_class: string | null
  last_error_summary: string | null
  details: Record<string, unknown>
}

export type AgentEvidenceSubmission = {
  submission_id: string
  agent_run_id: string | null
  provision: string
  provision_name: string | null
  source_doc_id: string | null
  evidence_id: string | null
  event_id: string | null
  canonical_url: string | null
  source_title: string | null
  claim_hash: string | null
  status: string
  rejection_reason: string | null
  promotion_result: Record<string, unknown>
  submitted_at: string
  promoted_at: string | null
  raw_public_metadata: Record<string, unknown>
}

export type RegistryData = {
  verticals: VerticalPci[]
  currentPci: CurrentPci[]
  policyEvents: PolicyEvent[]
  pipelineRuns: PipelineRun[]
  provisionTimelines: ProvisionTimeline[]
  evidenceItems: EvidenceItem[]
  sourceDocuments: SourceDocument[]
  sourceLinks: SourceLink[]
  sourceHealth: SourceHealth[]
  agentEvidenceSubmissions: AgentEvidenceSubmission[]
  connected: boolean
  viewErrors: string[]
}

export type RegistryFixtureMode =
  | "all-views-fail"
  | "empty-views"
  | "stale-timestamps"

function registryConfig() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? process.env.SUPABASE_URL
  const key =
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ??
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ??
    process.env.SUPABASE_ANON_KEY ??
    process.env.SUPABASE_PUBLISHABLE_KEY

  if (!url || !key) return null
  return { url: url.replace(/\/$/, ""), key }
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : String(error)
}

async function fetchView<T>(
  view: string,
  query = "select=*",
  fixtureMode?: RegistryFixtureMode,
): Promise<{ rows: T[]; error: string | null }> {
  const config = registryConfig()
  if (!config) return { rows: [], error: null }

  try {
    const pageSize = 1000
    const rows: T[] = []
    let start = 0

    while (true) {
      const end = start + pageSize - 1
      const fixtureQuery = fixtureMode
        ? `&__mock_mode=${encodeURIComponent(fixtureMode)}`
        : ""
      const response = await fetch(
        `${config.url}/rest/v1/${view}?${query}${fixtureQuery}`,
        {
          headers: {
            apikey: config.key,
            authorization: `Bearer ${config.key}`,
            range: `${start}-${end}`,
            "range-unit": "items",
          },
          cache: "no-store",
        },
      )

      if (!response.ok) return { rows: [], error: `${view}: ${response.status}` }

      const pageRows = (await response.json()) as T[]
      rows.push(...pageRows)

      if (pageRows.length < pageSize) return { rows, error: null }
      start += pageSize
    }
  } catch (error) {
    return { rows: [], error: `${view}: ${errorMessage(error)}` }
  }
}

export function emptyRegistryData(viewErrors: string[] = []): RegistryData {
  return {
    verticals: [],
    currentPci: [],
    policyEvents: [],
    pipelineRuns: [],
    provisionTimelines: [],
    evidenceItems: [],
    sourceDocuments: [],
    sourceLinks: [],
    sourceHealth: [],
    agentEvidenceSubmissions: [],
    connected: false,
    viewErrors,
  }
}

export async function getRegistryData(
  fixtureMode?: RegistryFixtureMode,
): Promise<RegistryData> {
  const config = registryConfig()
  if (!config) return emptyRegistryData(["Supabase registry config is not set."])

  const [
    verticalsResult,
    currentPciResult,
    policyEventsResult,
    pipelineRunsResult,
    provisionTimelinesResult,
    evidenceItemsResult,
    sourceDocumentsResult,
    sourceLinksResult,
    sourceHealthResult,
    agentEvidenceSubmissionsResult,
  ] = await Promise.all([
    fetchView<VerticalPci>(
      "v_vertical_pci",
      "select=*&order=display_order.asc",
      fixtureMode,
    ),
    fetchView<CurrentPci>("v_current_pci", "select=*&order=code.asc", fixtureMode),
    fetchView<PolicyEvent>("v_policy_events", "select=*&order=created_at.desc", fixtureMode),
    fetchView<PipelineRun>("v_pipeline_status", "select=*&limit=5", fixtureMode),
    fetchView<ProvisionTimeline>(
      "v_provision_timelines",
      "select=*&order=provision.asc,week_start.asc",
      fixtureMode,
    ),
    fetchView<EvidenceItem>("v_evidence_items", "select=*&order=created_at.desc", fixtureMode),
    fetchView<SourceDocument>("v_source_documents", "select=*&order=fetched_at.desc", fixtureMode),
    fetchView<SourceLink>("v_source_links", "select=*&order=created_at.desc", fixtureMode),
    fetchView<SourceHealth>("v_source_health", "select=*", fixtureMode),
    fetchView<AgentEvidenceSubmission>(
      "v_agent_evidence_submissions",
      "select=*&order=submitted_at.desc",
      fixtureMode,
    ),
  ])
  const viewErrors = [
    verticalsResult.error,
    currentPciResult.error,
    policyEventsResult.error,
    pipelineRunsResult.error,
    provisionTimelinesResult.error,
    evidenceItemsResult.error,
    sourceDocumentsResult.error,
    sourceLinksResult.error,
    sourceHealthResult.error,
    agentEvidenceSubmissionsResult.error,
  ].filter((error): error is string => Boolean(error))

  const verticals = verticalsResult.rows.sort(
    (a, b) => a.display_order - b.display_order,
  )
  const currentPci = currentPciResult.rows
  const policyEvents = policyEventsResult.rows
  const pipelineRuns = pipelineRunsResult.rows.map((run) => ({
    ...run,
    source: "registry",
  }))
  const provisionTimelines = provisionTimelinesResult.rows
  const evidenceItems = evidenceItemsResult.rows
  const sourceDocuments = sourceDocumentsResult.rows
  const sourceLinks = sourceLinksResult.rows
  const sourceHealth = sourceHealthResult.rows
  const agentEvidenceSubmissions = agentEvidenceSubmissionsResult.rows

  return {
    verticals,
    currentPci,
    policyEvents,
    pipelineRuns,
    provisionTimelines,
    evidenceItems,
    sourceDocuments,
    sourceLinks,
    sourceHealth,
    agentEvidenceSubmissions,
    connected: Boolean(config),
    viewErrors,
  }
}
