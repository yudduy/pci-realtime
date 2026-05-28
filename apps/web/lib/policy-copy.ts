export type PolicyCopy = {
  code: string
  name: string
  formalName: string
  question: string
  lane: string
  baseline: number
  stress: number
  specificity: number
  durability: number
  enforceability: number
}

export const POLICIES: PolicyCopy[] = [
  {
    code: "45X",
    name: "Factory credits",
    formalName: "Advanced Manufacturing Production Credit",
    question: "Will factory production credits remain in place?",
    lane: "Manufacturing",
    baseline: 4.67,
    stress: 3.67,
    specificity: 5,
    durability: 4,
    enforceability: 5,
  },
  {
    code: "45V",
    name: "Hydrogen",
    formalName: "Clean Hydrogen Production Credit",
    question: "Will clean hydrogen credits remain in place?",
    lane: "Hydrogen",
    baseline: 4.33,
    stress: 3.33,
    specificity: 5,
    durability: 4,
    enforceability: 4,
  },
  {
    code: "45Q",
    name: "Carbon capture",
    formalName: "Carbon Oxide Sequestration Credit",
    question: "Will carbon capture credits remain in place?",
    lane: "Carbon capture",
    baseline: 4.33,
    stress: 4.33,
    specificity: 5,
    durability: 4,
    enforceability: 4,
  },
  {
    code: "30D",
    name: "EV credits",
    formalName: "Clean Vehicle Credit",
    question: "Will EV tax credits remain in place?",
    lane: "Consumer EVs",
    baseline: 4,
    stress: 3,
    specificity: 4,
    durability: 4,
    enforceability: 4,
  },
  {
    code: "50144",
    name: "Reinvestment",
    formalName: "Energy Infrastructure Reinvestment",
    question: "Will energy reinvestment loans remain funded?",
    lane: "Grid and plants",
    baseline: 3.33,
    stress: 2,
    specificity: 4,
    durability: 3,
    enforceability: 3,
  },
  {
    code: "50141",
    name: "Energy loans",
    formalName: "Loan Programs Office Funding",
    question: "Will DOE loan-program funding remain available?",
    lane: "Loan programs",
    baseline: 3,
    stress: 2.33,
    specificity: 3,
    durability: 3,
    enforceability: 3,
  },
]

export const POLICY_BY_CODE = Object.fromEntries(
  POLICIES.map((policy) => [policy.code, policy]),
) as Record<string, PolicyCopy>

export function policyCopy(code: string, fallbackName?: string | null) {
  return (
    POLICY_BY_CODE[code] ?? {
      code,
      name: fallbackName ?? code,
      formalName: fallbackName ?? code,
      question: `Will ${fallbackName ?? code} stay credible?`,
      lane: "Policy",
      baseline: 0,
      stress: 0,
      specificity: 0,
      durability: 0,
      enforceability: 0,
    }
  )
}
