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


LLM_DEFAULT_PROVIDER = os.getenv("PCI_LLM_PROVIDER", "openai")
LLM_SCREENING_PROVIDER = os.getenv("PCI_SCREENING_PROVIDER", LLM_DEFAULT_PROVIDER)
LLM_SCORING_PROVIDER = os.getenv("PCI_SCORING_PROVIDER", LLM_DEFAULT_PROVIDER)
LLM_AUDIT_PROVIDER = os.getenv("PCI_AUDIT_PROVIDER", "anthropic")

LLM_SCREENING_MODEL = os.getenv("PCI_SCREENING_MODEL", "gpt-5-mini")
LLM_SCORING_MODEL = os.getenv("PCI_SCORING_MODEL", "gpt-5-mini")
LLM_AUDIT_MODEL = os.getenv("PCI_AUDIT_MODEL", "claude-sonnet-4-6")

# Backward-compatible names for older callers and tests.
OPENAI_SCREENING_MODEL = LLM_SCREENING_MODEL
OPENAI_SCORING_MODEL = LLM_SCORING_MODEL
SCORING_TEMPERATURE = 0.3
SCORING_SCHEMA_VERSION = "schema-b-v1.0.0"
SCORING_ESTIMATED_COST_PER_CALL_USD = 0.03
SCORING_RUN_COST_CEILING_USD = 50.0


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
        "https://home.treasury.gov/policy-issues/inflation-reduction-act",
        "https://home.treasury.gov/news/press-releases",
    ],
    "irs": [
        "https://www.irs.gov/credits-deductions/inflation-reduction-act-of-2022",
        "https://www.irs.gov/newsroom/tax-provisions-in-the-inflation-reduction-act",
    ],
}


PROPUBLICA_CONGRESS_API_URL = "https://api.propublica.org/congress/v1"


OMB_MEMO_PAGES = [
    "https://www.whitehouse.gov/omb/information-for-agencies/memoranda/",
]
