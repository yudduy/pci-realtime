import { policyCopy } from "@/lib/policy-copy"
import type { PolicyEvent, RegistryData, SourceDocument, SourceLink } from "@/lib/data"

export type SourceCitation = {
  id: string
  index: number
  policyCode: string | null
  policyName: string | null
  sourceName: string
  sourceType: string | null
  agency: string | null
  title: string
  url: string | null
  publishedAt: string | null
  fetchedAt: string | null
  snippet: string | null
  signal: string | null
  dimension: string | null
  confidence: number | null
  citationQuote: string | null
  citationSection: string | null
  citationPage: string | null
  collectedEvidence: boolean
  eventTitle: string | null
  eventDelta: number | null
}

export function buildSourceCitations(
  data: RegistryData,
  policyCode?: string,
): SourceCitation[] {
  const eventsByTarget = new Map(
    data.policyEvents.map((event) => [`policy_events:${event.event_id}`, event]),
  )
  const linksByEvidence = groupSourceLinks(data)
  const documentsById = new Map(
    data.sourceDocuments.map((document) => [document.source_doc_id, document]),
  )

  const citations = data.evidenceItems
    .map((item): SourceCitation | null => {
      const event = linkedPolicyEvent(item, linksByEvidence, eventsByTarget)
      const document = item.source_doc_id ? documentsById.get(item.source_doc_id) : undefined
      const code = item.provision ?? event?.provision ?? null
      if (policyCode && code !== policyCode) return null
      const copy = code ? policyCopy(code) : null

      const citation: SourceCitation = {
        id: item.evidence_id,
        index: 0,
        policyCode: code,
        policyName: item.provision_name ?? event?.provision_name ?? copy?.name ?? null,
        sourceName:
          item.source_name ??
          document?.source_name ??
          item.agency ??
          event?.agency ??
          item.source ??
          "Official source",
        sourceType: item.source_type ?? document?.source_type ?? null,
        agency: item.agency ?? document?.agency ?? event?.agency ?? null,
        title:
          item.source_title ??
          document?.title ??
          event?.title ??
          item.snippet ??
          "Source evidence",
        url: item.url ?? document?.url ?? document?.canonical_url ?? event?.url ?? null,
        publishedAt:
          item.published_at ??
          document?.published_at ??
          event?.created_at ??
          item.created_at,
        fetchedAt: item.fetched_at ?? document?.fetched_at ?? null,
        snippet: item.snippet,
        signal: item.normalized_signal,
        dimension: item.score_dimension,
        confidence:
          item.extraction_confidence ?? item.confidence ?? event?.confidence ?? null,
        citationQuote: item.citation_quote ?? sourceExcerpt(document),
        citationSection: item.citation_section ?? sourceMetadataText(document, "citation_section"),
        citationPage: item.citation_page ?? null,
        collectedEvidence: Boolean(
          item.submitted_by_agent_run_id ?? document?.submitted_by_agent_run_id,
        ),
        eventTitle: event?.title ?? null,
        eventDelta: event?.pci_delta ?? null,
      }
      return citation
    })
    .filter((item): item is SourceCitation => Boolean(item))
    .sort((a, b) => dateValue(b.publishedAt) - dateValue(a.publishedAt))

  return citations.map((citation, index) => ({ ...citation, index: index + 1 }))
}

function sourceExcerpt(document: SourceDocument | undefined) {
  const excerpt = document?.text_excerpt?.trim()
  return excerpt || null
}

function sourceMetadataText(
  document: SourceDocument | undefined,
  key: string,
) {
  const value = document?.raw_public_metadata?.[key]
  return typeof value === "string" && value.trim() ? value : null
}

function groupSourceLinks(data: RegistryData) {
  return data.sourceLinks.reduce<Map<string, SourceLink[]>>((groups, link) => {
    const links = groups.get(link.evidence_id) ?? []
    links.push(link)
    groups.set(link.evidence_id, links)
    return groups
  }, new Map())
}

function linkedPolicyEvent(
  item: { evidence_id: string },
  linksByEvidence: Map<string, SourceLink[]>,
  eventsByTarget: Map<string, PolicyEvent>,
) {
  const links = linksByEvidence.get(item.evidence_id) ?? []
  return links
    .map((link) => eventsByTarget.get(`${link.target_table}:${link.target_id}`))
    .find((event): event is PolicyEvent => Boolean(event))
}

function dateValue(value: string | null) {
  return value ? new Date(value).getTime() : 0
}
