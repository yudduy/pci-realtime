import { expect, test } from "@playwright/test"
import {
  emptyRegistryData,
  type CurrentPci,
  type EvidenceItem,
  type PolicyEvent,
  type RegistryData,
  type SourceLink,
} from "../../lib/data"
import { buildPolicyIntelligence } from "../../lib/intelligence"

const freshAt = "2099-01-01T00:00:00.000Z"

test.describe("PolicyIntelligence evidence derivation", () => {
  test("maps registry scores for every tracked policy unit", () => {
    const policies = buildPolicyIntelligence(
      registryData({ currentPci: [currentPci()] }),
    )

    expect(policies).toHaveLength(6)
    expect(policies.find((policy) => policy.code === "45V")).toMatchObject({
      currentPci: 4.25,
      weeklyDelta: -0.25,
      specificity: 5,
      durability: 4,
      enforceability: 3,
      updatedAt: freshAt,
    })
  })

  test("keeps policy events scoped to their policy unit", () => {
    const policies = buildPolicyIntelligence(
      registryData({
        policyEvents: [
          policyEvent(),
          policyEvent({
            event_id: "event:30D",
            provision: "30D",
            provision_name: "Clean Vehicle Credit",
            title: "Clean vehicle eligibility guidance",
          }),
        ],
      }),
    )

    const hydrogen = policies.find((policy) => policy.code === "45V")
    const evCredits = policies.find((policy) => policy.code === "30D")
    const carbonCapture = policies.find((policy) => policy.code === "45Q")

    expect(hydrogen?.eventCount).toBe(1)
    expect(hydrogen?.latestEvidenceTitle).toBe("Clean hydrogen production credit guidance")
    expect(evCredits?.eventCount).toBe(1)
    expect(evCredits?.latestEvidenceTitle).toBe("Clean vehicle eligibility guidance")
    expect(carbonCapture?.eventCount).toBe(0)
  })

  test("uses linked evidence for the matching policy only", () => {
    const policies = buildPolicyIntelligence(
      registryData({
        policyEvents: [policyEvent()],
        evidenceItems: [evidenceItem()],
        sourceLinks: [sourceLink()],
      }),
    )

    const hydrogen = policies.find((policy) => policy.code === "45V")
    const evCredits = policies.find((policy) => policy.code === "30D")

    expect(hydrogen?.evidenceCount).toBe(1)
    expect(hydrogen?.latestEvidenceTitle).toBe("Linked hydrogen evidence")
    expect(hydrogen?.latestEvidenceSource).toBe("Federal Register")
    expect(hydrogen?.evidenceAnchorCount).toBe(
      (hydrogen?.sourceReferences.length ?? 0) + 1,
    )
    expect(evCredits?.evidenceCount).toBe(0)
  })

  test("adds curated source references to every tracked policy", () => {
    const policies = buildPolicyIntelligence(registryData())
    const hydrogen = policies.find((policy) => policy.code === "45V")

    expect(hydrogen?.evidenceAnchorCount).toBeGreaterThanOrEqual(2)
    expect(hydrogen?.sourceReferences[0]?.source).toBe("Internal Revenue Service")
    expect(hydrogen?.attributionDrivers.length).toBeGreaterThan(0)
  })
})

function registryData(overrides: Partial<RegistryData> = {}): RegistryData {
  return {
    ...emptyRegistryData(),
    connected: true,
    ...overrides,
  }
}

function currentPci(overrides: Partial<CurrentPci> = {}): CurrentPci {
  return {
    code: "45V",
    name: "Clean Hydrogen Production Credit",
    provision_type: "tax_credit",
    primary_channel: "regulation",
    week: "2099-W01",
    week_start: "2099-01-01",
    pci: 4.25,
    specificity: 5,
    durability: 4,
    enforceability: 3,
    delta_this_week: -0.25,
    data_origin: "weekly",
    baseline_pci: 4,
    updated_at: freshAt,
    ...overrides,
  }
}

function policyEvent(overrides: Partial<PolicyEvent> = {}): PolicyEvent {
  return {
    event_id: "event:45V",
    provision: "45V",
    provision_name: "Clean Hydrogen Production Credit",
    week: "2099-W01",
    week_start: "2099-01-01",
    agency: "Treasury Department",
    doc_id: "document:45V",
    doc_source: "federal_register",
    title: "Clean hydrogen production credit guidance",
    url: "https://example.com/policy",
    pci_delta: -0.25,
    dimension_deltas: { specificity: -1 },
    rationale: "Eligibility guidance changed policy specificity.",
    confidence: 0.9,
    created_at: freshAt,
    ...overrides,
  }
}

function evidenceItem(overrides: Partial<EvidenceItem> = {}): EvidenceItem {
  return {
    evidence_id: "evidence:45V",
    source_doc_id: "document:45V",
    provision: null,
    provision_name: null,
    evidence_type: "pci_scoring_rationale",
    snippet: "Linked evidence excerpt.",
    normalized_signal: "specificity decreased",
    score_dimension: "specificity",
    confidence: 0.9,
    extractor_version: "test",
    created_at: freshAt,
    source: "federal_register",
    source_name: "Federal Register",
    source_type: "official_text",
    source_title: "Linked hydrogen evidence",
    agency: "Treasury Department",
    url: "https://example.com/evidence",
    published_at: freshAt,
    fetched_at: freshAt,
    ...overrides,
  }
}

function sourceLink(overrides: Partial<SourceLink> = {}): SourceLink {
  return {
    link_id: "link:45V",
    evidence_id: "evidence:45V",
    target_table: "policy_events",
    target_id: "event:45V",
    link_type: "primary_source",
    created_at: freshAt,
    ...overrides,
  }
}
