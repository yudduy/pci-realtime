import { expect, test } from "@playwright/test"
import type {
  MarketDiscoveryCandidate,
  MarketSnapshot,
  RegistryData,
  SourceHealth,
} from "../../lib/data"
import {
  buildPolicyIntelligence,
  deriveEvidenceStatus,
} from "../../lib/intelligence"

const freshAt = "2099-01-01T00:00:00.000Z"

test.describe("PolicyIntelligence evidence derivation", () => {
  test("derives market, review, documented, refresh, and stale states", () => {
    expect(
      deriveEvidenceStatus({
        marketSignals: [marketSnapshot("45Q")],
        reviewCandidates: [],
        latestRefreshAt: freshAt,
        scanned: 100,
      }),
    ).toBe("market_context")

    expect(
      deriveEvidenceStatus({
        marketSignals: [],
        reviewCandidates: [candidate("30D")],
        latestRefreshAt: freshAt,
        scanned: 100,
      }),
    ).toBe("source_review")

    expect(
      deriveEvidenceStatus({
        marketSignals: [],
        reviewCandidates: [],
        latestRefreshAt: freshAt,
        scanned: 100,
      }),
    ).toBe("documented")

    expect(
      deriveEvidenceStatus({
        marketSignals: [],
        reviewCandidates: [],
        latestRefreshAt: null,
        scanned: 0,
      }),
    ).toBe("source_refresh")

    expect(
      deriveEvidenceStatus({
        marketSignals: [],
        reviewCandidates: [],
        latestRefreshAt: "2026-01-01T00:00:00.000Z",
        scanned: 100,
        now: new Date("2026-01-03T00:00:00.000Z"),
      }),
    ).toBe("stale")
  })

  test("keeps review candidates scoped to their policy unit", () => {
    const policies = buildPolicyIntelligence(
      registryData({
        marketDiscoveryCandidates: [candidate("30D"), candidate("")],
      }),
    )

    const evCredits = policies.find((policy) => policy.code === "30D")
    const hydrogen = policies.find((policy) => policy.code === "45V")

    expect(evCredits?.evidenceStatus).toBe("source_review")
    expect(evCredits?.reviewCandidates).toHaveLength(1)
    expect(hydrogen?.evidenceStatus).toBe("documented")
    expect(hydrogen?.reviewCandidates).toHaveLength(0)
  })

  test("uses actual market snapshots only for contextual market state", () => {
    const policies = buildPolicyIntelligence(
      registryData({
        marketSnapshots: [marketSnapshot("45Q")],
        marketDiscoveryCandidates: [candidate("45Q")],
      }),
    )

    const carbonCapture = policies.find((policy) => policy.code === "45Q")

    expect(carbonCapture?.evidenceStatus).toBe("source_review")
    expect(carbonCapture?.marketSignals).toHaveLength(1)
  })

  test("verified policy evidence outranks market context", () => {
    const policies = buildPolicyIntelligence(
      registryData({
        marketSnapshots: [marketSnapshot("45V")],
        policyEvidenceItems: [evidenceItem("45V")],
      }),
    )

    const hydrogen = policies.find((policy) => policy.code === "45V")

    expect(hydrogen?.evidenceStatus).toBe("documented")
    expect(hydrogen?.marketSignals).toHaveLength(1)
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

function candidate(policyCode: string): MarketDiscoveryCandidate {
  return {
    candidate_id: `candidate:${policyCode || "unscoped"}`,
    run_id: "run",
    generated_at: freshAt,
    venue: "polymarket",
    ticker: `ticker-${policyCode || "unscoped"}`,
    event_ticker: null,
    title: policyCode ? `${policyCode} policy eligibility candidate` : "Unscoped fiscal event candidate",
    market_url: null,
    status: "active",
    query_name: "test",
    matched_keywords: policyCode ? [policyCode] : [],
    matched_provisions: policyCode ? [policyCode] : [],
    policy_relevant: Boolean(policyCode),
    resolution_clear: true,
    eligible_snapshot: false,
    rejection_reasons: ["no_policy_context"],
    liquidity_dollars: 1000,
    volume: 2000,
    volume_24h: 10,
  }
}

function marketSnapshot(policyCode: string): MarketSnapshot {
  return {
    snapshot_id: `snapshot:${policyCode}`,
    generated_at: freshAt,
    venue: "kalshi",
    ticker: `KX-${policyCode}`,
    event_ticker: `KX-${policyCode}-EVENT`,
    title: `${policyCode} eligible public market`,
    subtitle: null,
    status: "open",
    result: null,
    yes_bid: 0.44,
    yes_ask: 0.46,
    bid_ask_spread: 0.02,
    market_probability: 0.45,
    liquidity_dollars: 5000,
    volume: 10000,
    volume_24h: 100,
    open_interest: 200,
    close_time: null,
    expected_expiration_time: null,
    latest_expiration_time: null,
    policy_relevant: true,
    resolution_text: "Test resolution",
    query_name: policyCode,
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
