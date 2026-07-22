from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent.parent
DATA_ROOT = PROJECT_ROOT / "data"
RAW_DATA_ROOT = DATA_ROOT / "raw"
PROCESSED_DATA_ROOT = DATA_ROOT / "processed"
CACHE_ROOT = DATA_ROOT / "cache"


TRACKED_PROVISIONS = ("45X", "45V", "45Q", "30D", "50144", "50141")


VERTICALS = {
    "advanced-manufacturing": {
        "name": "Advanced Manufacturing",
        "display_order": 1,
        "provisions": {"45X": 1.0},
        "coverage_note": (
            "Tracks the section 45X production credit only; excludes 48C, tariffs, "
            "and state incentives."
        ),
    },
    "clean-hydrogen": {
        "name": "Clean Hydrogen",
        "display_order": 2,
        "provisions": {"45V": 1.0},
        "coverage_note": (
            "Tracks the section 45V production credit only; excludes DOE hydrogen "
            "hub grants."
        ),
    },
    "carbon-capture": {
        "name": "Carbon Capture",
        "display_order": 3,
        "provisions": {"45Q": 1.0},
        "coverage_note": (
            "Tracks the section 45Q sequestration credit only; excludes DAC hub "
            "programs."
        ),
    },
    "electric-vehicles": {
        "name": "Electric Vehicles",
        "display_order": 4,
        "provisions": {"30D": 1.0},
        "coverage_note": (
            "Tracks the consumer 30D credit only; excludes 45W commercial and 30C "
            "charging credits."
        ),
    },
    "clean-energy-finance": {
        "name": "Clean Energy Finance",
        "display_order": 5,
        "provisions": {"50141": 1.0, "50144": 1.0},
        "coverage_note": (
            "Tracks DOE Loan Programs Office funding (50141) and Energy "
            "Infrastructure Reinvestment authority (50144)."
        ),
    },
}


# These verticals need lab methodology sign-off before scoring.
UNCOVERED_VERTICALS = [
    "Solar & Wind Deployment (45Y/48E)",
    "Nuclear (45U)",
    "Storage",
    "AI Data Centers",
]


PROVISION_DETAILS: dict[str, dict[str, str]] = {
    "45X": {
        "name": "Advanced Manufacturing Production Credit",
        "type": "tax_credit",
        "primary_channel": "domestic clean-energy manufacturing",
        "paper_role": "High-credibility production credit tied to Energy and upstream manufacturing exposure.",
        "obbba_shock": "Wind component elimination and stricter domestic content requirements.",
    },
    "45V": {
        "name": "Clean Hydrogen Production Credit",
        "type": "tax_credit",
        "primary_channel": "clean hydrogen production",
        "paper_role": "High-credibility production credit for hydrogen technologies in the Energy category.",
        "obbba_shock": "Accelerated construction deadline from indefinite eligibility to 2027.",
    },
    "45Q": {
        "name": "Carbon Oxide Sequestration Credit",
        "type": "tax_credit",
        "primary_channel": "carbon capture, utilization, and storage",
        "paper_role": "High-credibility tax credit aligned with Carbon technologies.",
        "obbba_shock": "No proposed OBBBA change in the paper's stress-test window.",
    },
    "30D": {
        "name": "Clean Vehicle Credit",
        "type": "tax_credit",
        "primary_channel": "consumer clean-vehicle adoption",
        "paper_role": "Medium-credibility adoption-side credit; Transportation is treated as less directly exposed in the main design.",
        "obbba_shock": "Early termination in September 2025, ahead of the original 2032 sunset.",
    },
    "50144": {
        "name": "Energy Infrastructure Reinvestment",
        "type": "loan_program",
        "primary_channel": "DOE Loan Programs Office energy infrastructure authority",
        "paper_role": "Lower-credibility discretionary LPO authority relevant to energy infrastructure and capital-intensive deployment.",
        "obbba_shock": "Mission rebranding and revised selection criteria under greater executive discretion.",
    },
    "50141": {
        "name": "Loan Programs Office Funding",
        "type": "appropriation",
        "primary_channel": "DOE loan guarantee program funding",
        "paper_role": "Lower-credibility appropriations-based support and enabling public capital.",
        "obbba_shock": "Rescission of unobligated balances.",
    },
}


LLM_DEFAULT_PROVIDER = os.getenv("PCI_LLM_PROVIDER", "openai")
LLM_SCREENING_PROVIDER = os.getenv("PCI_SCREENING_PROVIDER", LLM_DEFAULT_PROVIDER)
LLM_SCORING_PROVIDER = os.getenv("PCI_SCORING_PROVIDER", LLM_DEFAULT_PROVIDER)
LLM_AUDIT_PROVIDER = os.getenv("PCI_AUDIT_PROVIDER", LLM_DEFAULT_PROVIDER)

LLM_SCREENING_MODEL = os.getenv("PCI_SCREENING_MODEL", "gpt-5.4-nano")
LLM_SCORING_MODEL = os.getenv("PCI_SCORING_MODEL", "gpt-5.4-mini")
LLM_AUDIT_MODEL = os.getenv("PCI_AUDIT_MODEL", "gpt-5.5")

# Backward-compatible names for older callers and tests.
OPENAI_SCREENING_MODEL = LLM_SCREENING_MODEL
OPENAI_SCORING_MODEL = LLM_SCORING_MODEL
SCORING_TEMPERATURE = 0.3
SCORING_SCHEMA_VERSION = "schema-b-v1.0.0"
SCORING_ESTIMATED_COST_PER_CALL_USD = 0.03
SCORING_RUN_COST_CEILING_USD = 50.0

RESEARCH_DEFAULT_PROVIDERS = os.getenv(
    "PCI_RESEARCH_PROVIDERS",
    os.getenv("PCI_RESEARCH_PROVIDER", "parallel,openai"),
)
RESEARCH_PARALLEL_PROCESSOR = os.getenv("PCI_PARALLEL_PROCESSOR", "base")
RESEARCH_UNIT_COSTS_USD = {
    "parallel:lite": 0.005,
    "parallel:base": 0.01,
    "parallel:core": 0.025,
    "exa": 0.007,
    "openai": 0.05,
}
RESEARCH_RUN_COST_CEILING_USD = 2.0
RESEARCH_MAX_REQUESTS_PER_RUN = 25
RESEARCH_MAX_PROMOTIONS_PER_LANE = 3


BASELINE_PCI = {
    "45X": {"specificity": 5.0, "durability": 4.0, "enforceability": 5.0, "pci": 4.67},
    "45V": {"specificity": 5.0, "durability": 4.0, "enforceability": 4.0, "pci": 4.33},
    "45Q": {"specificity": 5.0, "durability": 4.0, "enforceability": 4.0, "pci": 4.33},
    "30D": {"specificity": 4.0, "durability": 4.0, "enforceability": 4.0, "pci": 4.00},
    "50144": {
        "specificity": 4.0,
        "durability": 3.0,
        "enforceability": 3.0,
        "pci": 3.33,
    },
    "50141": {
        "specificity": 3.0,
        "durability": 3.0,
        "enforceability": 3.0,
        "pci": 3.00,
    },
}


OBBBA_PCI_DELTAS = {
    "45X": -1.00,
    "45V": -1.00,
    "45Q": 0.00,
    "30D": -1.00,
    "50144": -1.33,
    "50141": -0.67,
}


PROVISION_KEYWORDS = {
    "45X": [
        "section 45x",
        "45x",
        "advanced manufacturing production credit",
    ],
    "45V": [
        "section 45v",
        "45v",
        "clean hydrogen production credit",
        "clean hydrogen",
    ],
    "45Q": [
        "section 45q",
        "45q",
        "carbon oxide sequestration credit",
        "carbon dioxide sequestration credit",
        "carbon capture credit",
    ],
    "30D": [
        "section 30d",
        "30d",
        "clean vehicle credit",
        "new clean vehicle credit",
    ],
    "50144": [
        "section 50144",
        "50144",
        "energy infrastructure reinvestment",
    ],
    "50141": [
        "section 50141",
        "50141",
        "loan programs office",
        "lpo funding",
        "loan guarantees for clean energy projects",
    ],
}


FEDERAL_REGISTER_TERMS = [
    "Inflation Reduction Act",
    "section 45X",
    "advanced manufacturing production credit",
    "section 45V",
    "clean hydrogen production credit",
    "section 45Q",
    "carbon oxide sequestration credit",
    "section 30D",
    "clean vehicle credit",
    "section 6417 elective payment of applicable credits",
    "section 6418 transfer of certain credits",
    "section 50141",
    "loan programs office",
    "section 50144",
    "energy infrastructure reinvestment",
]


ALLOWED_FEDERAL_REGISTER_AGENCY_SLUGS = {
    "treasury-department",
    "internal-revenue-service",
    "energy-department",
    "environmental-protection-agency",
}


@dataclass(frozen=True)
class FederalRegisterConfig:
    base_url: str = "https://www.federalregister.gov/api/v1/documents.json"
    default_per_page: int = 100
    max_pages: int = 20
    timeout_seconds: int = 30


FEDERAL_REGISTER_CONFIG = FederalRegisterConfig()


REQUEST_TIMEOUT_SECONDS = 30


TREASURY_GUIDANCE_PAGES = {
    "treasury": [
        "https://home.treasury.gov/news/press-releases",
        "https://home.treasury.gov/news/press-releases?search_api_fulltext=Inflation+Reduction+Act",
    ],
    "irs": [
        "https://www.irs.gov/credits-deductions/clean-vehicle-and-energy-credits",
        "https://www.irs.gov/clean-vehicle-tax-credits",
        "https://www.irs.gov/credits-deductions/clean-electricity-production-credit",
        "https://www.irs.gov/newsroom/posters-guides-and-toolkits-for-the-inflation-reduction-act-credits",
        "https://www.irs.gov/newsroom/one-big-beautiful-bill-provisions-individuals-and-workers",
    ],
}


PROPUBLICA_CONGRESS_API_URL = "https://api.propublica.org/congress/v1"


OMB_MEMO_PAGES = [
    "https://www.whitehouse.gov/omb/information-for-agencies/memoranda/",
]
