import { expect, test } from "@playwright/test"
import type { RegistryData, SourceHealth } from "../../lib/data"
import {
  buildPolicyIntelligence,
  deriveEvidenceStatus,
} from "../../lib/intelligence"

const freshAt = "2099-01-01T00:00:00.000Z"

test.describe("PolicyIntelligence evidence derivation", () => {
  test("derives review, documented, refresh, and stale states", () => {
    expect(
      deriveEvidenceStatus({
        sourceLeads: [policySourceCandidate("30D")],
        latestRefreshAt: freshAt,
      }),
    ).toBe("source_review")

    expect(
      deriveEvidenceStatus({
        sourceLeads: [],
        latestRefreshAt: freshAt,
      }),
    ).toBe("documented")

    expect(
      deriveEvidenceStatus({
        latestRefreshAt: null,
      }),
    ).toBe("source_refresh")

    expect(
      deriveEvidenceStatus({
        latestRefreshAt: "2026-01-01T00:00:00.000Z",
        now: new Date("2026-01-03T00:00:00.000Z"),
      }),
    ).toBe("stale")
  })

  test("verified policy evidence marks the policy documented", () => {
    const policies = buildPolicyIntelligence(
      registryData({
        policyEvidenceItems: [evidenceItem("45V")],
      }),
    )

    const hydrogen = policies.find((policy) => policy.code === "45V")

    expect(hydrogen?.evidenceStatus).toBe("documented")
  })

  test("adds source references to every tracked policy", () => {
    const policies = buildPolicyIntelligence(registryData())
    const hydrogen = policies.find((policy) => policy.code === "45V")

    expect(hydrogen?.evidenceAnchorCount).toBeGreaterThanOrEqual(2)
    expect(hydrogen?.sourceReferences[0]?.source).toBe("Internal Revenue Service")
    expect(hydrogen?.attributionDrivers.length).toBeGreaterThan(0)
  })

  test("keeps approved policy source leads scoped to their policy unit", () => {
    const policies = buildPolicyIntelligence(
      registryData({
        policySourceCandidates: [policySourceCandidate("45V")],
      }),
    )

    const hydrogen = policies.find((policy) => policy.code === "45V")
    const manufacturing = policies.find((policy) => policy.code === "45X")

    expect(hydrogen?.sourceLeads).toHaveLength(1)
    expect(manufacturing?.sourceLeads).toHaveLength(0)
  })
})

function registryData(
  overrides: Partial<RegistryData> = {},
): RegistryData {
  return {
    currentPci: [],
    openForecasts: [],
    resolvedForecasts: [],
    tradeProposals: [],
    marketSnapshots: [],
    marketDiscoveryCandidates: [],
    policySourceCandidates: [],
    policyTheses: [],
    beliefUpdates: [],
    policyBriefs: [],
    policyEvents: [],
    pipelineRuns: [],
    provisionTimelines: [],
    forecastPerformance: null,
    evidenceItems: [],
    policyEvidenceItems: [],
    sourceDocuments: [],
    sourceLinks: [],
    sourceHealth: [sourceHealth()],
    agentEvidenceSubmissions: [],
    connected: true,
    viewErrors: [],
    ...overrides,
  }
}

function policySourceCandidate(policyCode: string) {
  return {
    candidate_id: `policy-source:${policyCode}`,
    run_id: "test-run",
    discovered_at: freshAt,
    provision: policyCode,
    provision_name: "Policy source candidate",
    source_class: "analysis" as const,
    review_state: "approved" as const,
    promotability: "context_only" as const,
    source_name: "Policy analysis",
    source_type: "policy_discovery_lead",
    canonical_url: "https://example.com/policy-analysis",
    resolved_primary_url: null,
    title: "Policy analysis",
    published_at: freshAt,
    citation_quote: "A reviewed context lead.",
    citation_section: null,
    claim: "Reviewed context lead.",
    decision_relevance: "implementation_watch",
    why_it_matters: "It may matter for implementation timing.",
    confidence: 0.6,
    related_evidence_ids: [],
    verification_status: "not_checked" as const,
    quote_verified_against_source: false,
    source_retrieved_at: null,
    source_retrieval_method: null,
    quote_locator_type: null,
    review_decision_code: "context_review",
    promotion_policy_version: "policy-intel-review-v2",
    reviewed_at: freshAt,
    promoted_submission_id: null,
    promotion_result: {},
    raw_public_metadata: {},
  }
}

function sourceHealth(): SourceHealth {
  return {
    source: "polymarket",
    source_name: "Polymarket markets",
    status: "success",
    last_attempt_at: freshAt,
    last_success_at: freshAt,
    latency_ms: 100,
    row_count: 100,
    last_error_class: null,
    last_error_summary: null,
    details: {
      scanned: 100,
      published: 0,
      stored_candidates: 0,
      rate_limited: 0,
    },
  }
}

function evidenceItem(policyCode: string) {
  return {
    evidence_id: `evidence:${policyCode}`,
    source_doc_id: `source:${policyCode}`,
    provision: policyCode,
    provision_name: "Policy evidence",
    evidence_type: "policy_evidence_citation",
    snippet: "Verified quote-backed evidence.",
    normalized_signal: "+0.10 PCI",
    score_dimension: "specificity",
    confidence: 0.8,
    extractor_version: "test",
    created_at: freshAt,
    citation_quote: "Verified quote-backed evidence.",
    citation_section: null,
    citation_page: null,
    citation_url_fragment: null,
    claim_hash: `claim:${policyCode}`,
    quote_hash: `quote:${policyCode}`,
    quote_verified_against_source: true,
    quote_locator_type: "text",
    quote_locator_value: null,
    submitted_by_agent_run_id: null,
    extraction_confidence: 0.8,
    raw_public_metadata: {},
    source: "treasury",
    source_name: "Treasury",
    source_type: "official",
    source_title: "Official guidance",
    agency: "Treasury",
    url: "https://example.com/guidance",
    canonical_url: "https://example.com/guidance",
    published_at: freshAt,
    fetched_at: freshAt,
  }
}
