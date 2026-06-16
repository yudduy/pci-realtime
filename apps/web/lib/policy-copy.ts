export type PolicyCopy = {
  code: string
  name: string
  formalName: string
  question: string
  lane: string
  baseline: number
  specificity: number
  durability: number
  enforceability: number
  attributionDrivers: string[]
  sourceReferences: PolicySourceReference[]
}

export type PolicySourceReference = {
  title: string
  source: string
  url: string
  dimension: "specificity" | "durability" | "enforceability" | "program basis"
  note: string
}

export type SourcePortfolioItem = {
  name: string
  scope: string
}

export const SOURCE_PORTFOLIO: SourcePortfolioItem[] = [
  { name: "Federal Register", scope: "rules, notices, agency guidance" },
  { name: "Treasury and IRS", scope: "tax-credit guidance, forms, FAQs" },
  { name: "Congress", scope: "statutes, amendments, committee movement" },
  { name: "DOE and LPO", scope: "loan authority, project-selection guidance" },
  { name: "OMB and RegInfo", scope: "rulemaking review and regulatory agenda" },
  { name: "Regulations.gov", scope: "dockets, comments, final rule history" },
  { name: "Federal spending", scope: "award, obligation, and program execution" },
  { name: "Court records", scope: "litigation and implementation risk" },
]

const IRS_45X = "https://www.irs.gov/credits-deductions/advanced-manufacturing-production-credit"
const IRS_45V = "https://www.irs.gov/credits-deductions/clean-hydrogen-production-credit"
const IRS_45Q = "https://www.irs.gov/credits-deductions/credit-for-carbon-oxide-sequestration"
const IRS_30D = "https://www.irs.gov/clean-vehicle-tax-credits"
const IRS_30D_NEW = "https://www.irs.gov/credits-deductions/credits-for-new-clean-vehicles-purchased-in-2023-or-after"
const DOE_IRA = "https://www.energy.gov/edf/inflation-reduction-act-2022"
const DOE_EIR = "https://www.energy.gov/edf/title-17-energy-infrastructure-reinvestment-eir-financing"
const DOE_EIR_FAQ = "https://www.energy.gov/edf/title-17-frequently-asked-questions"

export const POLICIES: PolicyCopy[] = [
  {
    code: "45X",
    name: "Advanced Manufacturing Production Credit",
    formalName: "Section 45X Advanced Manufacturing Production Credit",
    question: "Manufacturing credit rules remain specific, durable, and enforceable under current guidance.",
    lane: "Manufacturing",
    baseline: 4.67,
    specificity: 5,
    durability: 4,
    enforceability: 5,
    attributionDrivers: [
      "Credit value is formulaic by eligible component class.",
      "Domestic production and sale requirements make the policy auditable.",
      "Transferability and direct-pay mechanics affect monetization durability.",
    ],
    sourceReferences: [
      {
        title: "Advanced Manufacturing Production Credit",
        source: "Internal Revenue Service",
        url: IRS_45X,
        dimension: "program basis",
        note: "Defines the section 45X credit, payment election, and transferability mechanics.",
      },
      {
        title: "Form 7207 instructions",
        source: "Internal Revenue Service",
        url: "https://www.irs.gov/instructions/i7207",
        dimension: "enforceability",
        note: "Shows the claiming workflow and documentation surface for eligible components.",
      },
    ],
  },
  {
    code: "45V",
    name: "Clean Hydrogen Production Credit",
    formalName: "Section 45V Clean Hydrogen Production Credit",
    question: "Hydrogen credit credibility depends on lifecycle-emissions guidance and enforceable documentation.",
    lane: "Hydrogen",
    baseline: 4.33,
    specificity: 5,
    durability: 4,
    enforceability: 4,
    attributionDrivers: [
      "Lifecycle-emissions tiers determine credit value.",
      "Facility-level production and verification requirements drive enforceability.",
      "Guidance stability affects bankability for long-dated hydrogen projects.",
    ],
    sourceReferences: [
      {
        title: "Clean Hydrogen Production Credit",
        source: "Internal Revenue Service",
        url: IRS_45V,
        dimension: "program basis",
        note: "Defines the section 45V production credit and qualified facility framing.",
      },
      {
        title: "Form 7210 instructions",
        source: "Internal Revenue Service",
        url: "https://www.irs.gov/pub/irs-pdf/i7210.pdf",
        dimension: "enforceability",
        note: "Documents facility-level claiming, verification, and transferability requirements.",
      },
    ],
  },
  {
    code: "45Q",
    name: "Carbon Oxide Sequestration Credit",
    formalName: "Section 45Q Carbon Oxide Sequestration Credit",
    question: "Carbon capture credibility turns on storage verification, transferability, and recapture risk.",
    lane: "Carbon capture",
    baseline: 4.33,
    specificity: 5,
    durability: 4,
    enforceability: 4,
    attributionDrivers: [
      "Credit depends on measured capture, storage, utilization, and recapture rules.",
      "Form-level reporting makes claims auditable after placement in service.",
      "Safe harbors and measurement guidance change execution risk.",
    ],
    sourceReferences: [
      {
        title: "Credit for Carbon Oxide Sequestration",
        source: "Internal Revenue Service",
        url: IRS_45Q,
        dimension: "program basis",
        note: "Explains section 45Q claiming requirements and Form 8933 linkage.",
      },
      {
        title: "About Form 8933",
        source: "Internal Revenue Service",
        url: "https://www.irs.gov/forms-pubs/about-form-8933",
        dimension: "enforceability",
        note: "Shows the filing surface for carbon oxide sequestration credit claims.",
      },
    ],
  },
  {
    code: "30D",
    name: "Clean Vehicle Credit",
    formalName: "Section 30D Clean Vehicle Credit",
    question: "Consumer vehicle credit credibility is shaped by sourcing rules and eligibility enforcement.",
    lane: "Consumer EVs",
    baseline: 4,
    specificity: 4,
    durability: 4,
    enforceability: 4,
    attributionDrivers: [
      "Vehicle eligibility, sourcing rules, and buyer income limits determine specificity.",
      "Dealer reporting and time-of-sale confirmation drive enforceability.",
      "Scheduled statutory changes and phaseouts affect durability week to week.",
    ],
    sourceReferences: [
      {
        title: "Clean vehicle tax credits",
        source: "Internal Revenue Service",
        url: IRS_30D,
        dimension: "program basis",
        note: "Tracks the current clean vehicle credit program surface and eligibility timing.",
      },
      {
        title: "Credits for new clean vehicles purchased in 2023 or after",
        source: "Internal Revenue Service",
        url: IRS_30D_NEW,
        dimension: "specificity",
        note: "Details buyer, vehicle, and use requirements for section 30D.",
      },
    ],
  },
  {
    code: "50144",
    name: "Energy Infrastructure Reinvestment Program",
    formalName: "Section 50144 Energy Infrastructure Reinvestment Program",
    question: "Grid and plant reinvestment credibility depends on appropriation durability and project selection.",
    lane: "Grid and plants",
    baseline: 3.33,
    specificity: 4,
    durability: 3,
    enforceability: 3,
    attributionDrivers: [
      "Title 17 section 1706 eligibility controls project scope.",
      "Loan-guarantee authority depends on credit subsidy and application execution.",
      "Project selection and financing terms determine implementation credibility.",
    ],
    sourceReferences: [
      {
        title: "Title 17 Energy Infrastructure Reinvestment Financing",
        source: "Department of Energy",
        url: DOE_EIR,
        dimension: "program basis",
        note: "Defines the EIR financing program for retooling, repowering, and repurposing energy infrastructure.",
      },
      {
        title: "Title 17 frequently asked questions",
        source: "Department of Energy",
        url: DOE_EIR_FAQ,
        dimension: "specificity",
        note: "Clarifies eligibility categories and application interpretation.",
      },
    ],
  },
  {
    code: "50141",
    name: "Loan Programs Office Funding",
    formalName: "Section 50141 Loan Programs Office Funding",
    question: "Loan authority credibility depends on durable budget authority and enforceable award conditions.",
    lane: "Loan programs",
    baseline: 3,
    specificity: 3,
    durability: 3,
    enforceability: 3,
    attributionDrivers: [
      "Loan authority and credit subsidy set available program capacity.",
      "Commitment authority is meaningful only when application and award pipelines move.",
      "Appropriations durability and portfolio execution drive credibility.",
    ],
    sourceReferences: [
      {
        title: "Inflation Reduction Act of 2022",
        source: "Department of Energy",
        url: DOE_IRA,
        dimension: "program basis",
        note: "Summarizes IRA additions to LPO authority and the EIR program.",
      },
      {
        title: "IRA Title XVII solicitation supplement",
        source: "Department of Energy",
        url: "https://www.energy.gov/sites/default/files/2023-03/IRA%20Title%20XVII%20Solicitation%20Supplement%20-%2003.10.2023.pdf",
        dimension: "durability",
        note: "Shows section 50141 commitment authority and Title 17 implementation mechanics.",
      },
    ],
  },
]

export const POLICY_BY_CODE = Object.fromEntries(
  POLICIES.map((policy) => [policy.code, policy]),
) as Record<string, PolicyCopy>

export function policyCopy(code: string, displayName?: string | null) {
  return (
    POLICY_BY_CODE[code] ?? {
      code,
      name: displayName ?? code,
      formalName: displayName ?? code,
      question: `Will ${displayName ?? code} stay credible?`,
      lane: "Policy",
      baseline: 0,
      specificity: 0,
      durability: 0,
      enforceability: 0,
      attributionDrivers: ["Tracked policy unit."],
      sourceReferences: [],
    }
  )
}
