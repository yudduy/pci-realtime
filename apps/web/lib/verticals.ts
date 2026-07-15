import type { VerticalPci } from "@/lib/data"

const BASELINE_VERTICALS: VerticalPci[] = [
  {
    id: "advanced-manufacturing",
    name: "Advanced Manufacturing",
    coverage_note:
      "Tracks the section 45X production credit only; excludes 48C, tariffs, and state incentives.",
    display_order: 1,
    vertical_pci: 4.67,
    baseline_pci: 4.67,
    weekly_delta: 0,
    as_of_week_start: null,
    last_change_week_start: null,
    provisions: ["45X"],
  },
  {
    id: "clean-hydrogen",
    name: "Clean Hydrogen",
    coverage_note:
      "Tracks the section 45V production credit only; excludes DOE hydrogen hub grants.",
    display_order: 2,
    vertical_pci: 4.33,
    baseline_pci: 4.33,
    weekly_delta: 0,
    as_of_week_start: null,
    last_change_week_start: null,
    provisions: ["45V"],
  },
  {
    id: "carbon-capture",
    name: "Carbon Capture",
    coverage_note:
      "Tracks the section 45Q sequestration credit only; excludes DAC hub programs.",
    display_order: 3,
    vertical_pci: 4.33,
    baseline_pci: 4.33,
    weekly_delta: 0,
    as_of_week_start: null,
    last_change_week_start: null,
    provisions: ["45Q"],
  },
  {
    id: "electric-vehicles",
    name: "Electric Vehicles",
    coverage_note:
      "Tracks the consumer 30D credit only; excludes 45W commercial and 30C charging credits.",
    display_order: 4,
    vertical_pci: 4,
    baseline_pci: 4,
    weekly_delta: 0,
    as_of_week_start: null,
    last_change_week_start: null,
    provisions: ["30D"],
  },
  {
    id: "clean-energy-finance",
    name: "Clean Energy Finance",
    coverage_note:
      "Tracks DOE Loan Programs Office funding (50141) and Energy Infrastructure Reinvestment authority (50144).",
    display_order: 5,
    vertical_pci: 3.17,
    baseline_pci: 3.17,
    weekly_delta: 0,
    as_of_week_start: null,
    last_change_week_start: null,
    provisions: ["50141", "50144"],
  },
]

export const VERTICAL_IDS = BASELINE_VERTICALS.map((vertical) => vertical.id)

export const UNSCORED_VERTICALS = [
  "Solar & Wind Deployment (45Y/48E)",
  "Nuclear (45U)",
  "Storage",
  "AI Data Centers",
]

export function baselineVerticals(): VerticalPci[] {
  return BASELINE_VERTICALS.map((vertical) => ({
    ...vertical,
    provisions: [...vertical.provisions],
  }))
}

export function baselineVertical(verticalId: string): VerticalPci {
  const vertical = BASELINE_VERTICALS.find((item) => item.id === verticalId)
  if (!vertical) throw new Error(`Unknown vertical: ${verticalId}`)
  return { ...vertical, provisions: [...vertical.provisions] }
}

export function isVerticalId(value: string): boolean {
  return VERTICAL_IDS.includes(value)
}
