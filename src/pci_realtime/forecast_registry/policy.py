from __future__ import annotations

import re
from dataclasses import dataclass


FORECAST_REGISTRY_METHOD_VERSION = "forecast-registry-v1"

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

POLICY_MARKET_KEYWORDS = {
    "ira",
    "inflation reduction act",
    "tax credit",
    "clean energy",
    "climate",
    "hydrogen",
    "carbon capture",
    "electric vehicle",
    "ev",
    "manufacturing",
    "treasury",
    "irs",
    "department of energy",
    "doe",
    "loan programs office",
    "lpo",
    "congress",
    "regulation",
    "federal",
    "agency",
    "rule",
    "guidance",
    "subsidy",
}

ADVERSE_POLICY_TERMS = {
    "repeal",
    "repealed",
    "rescind",
    "rescission",
    "cut",
    "cuts",
    "terminate",
    "termination",
    "end",
    "eliminate",
    "elimination",
    "block",
    "delay",
    "rollback",
    "sunset",
    "expire",
}

SUPPORTIVE_POLICY_TERMS = {
    "extend",
    "extension",
    "preserve",
    "remain",
    "survive",
    "finalize",
    "approve",
    "guidance",
    "implemented",
    "fund",
    "funding",
    "subsidy",
    "credit",
}


@dataclass(frozen=True)
class ProvisionExposure:
    provision: str
    sectors: tuple[str, ...]
    market_keywords: tuple[str, ...]
    exposure_channel: str
    paper_evidence: str


PROVISION_EXPOSURES: dict[str, ProvisionExposure] = {
    "45X": ProvisionExposure(
        provision="45X",
        sectors=("Energy", "Advanced Manufacturing"),
        market_keywords=(
            "45x",
            "advanced manufacturing",
            "manufacturing production credit",
            "battery",
            "solar",
            "wind component",
            "domestic content",
            "tax credit",
        ),
        exposure_channel="Domestic manufacturing credibility affects capital allocation toward upstream clean-energy supply chains.",
        paper_evidence="The paper treats Energy as directly IRA-exposed and finds post-IRA VC allocation increases for treated categories.",
    ),
    "45V": ProvisionExposure(
        provision="45V",
        sectors=("Energy", "Hydrogen"),
        market_keywords=(
            "45v",
            "hydrogen",
            "clean hydrogen",
            "production credit",
            "treasury",
            "irs",
            "tax credit",
        ),
        exposure_channel="Hydrogen production-credit credibility affects expected project economics for clean-hydrogen firms.",
        paper_evidence="The continuous IRA Index design links provision exposure intensity to higher post-IRA VC outcomes.",
    ),
    "45Q": ProvisionExposure(
        provision="45Q",
        sectors=("Carbon", "Carbon Capture"),
        market_keywords=(
            "45q",
            "carbon capture",
            "carbon oxide",
            "sequestration",
            "ccus",
            "tax credit",
        ),
        exposure_channel="Carbon-capture credit credibility affects Carbon category financing expectations.",
        paper_evidence="Carbon is a directly treated category in the paper's main difference-in-differences design.",
    ),
    "30D": ProvisionExposure(
        provision="30D",
        sectors=("Transportation", "Electric Vehicles"),
        market_keywords=(
            "30d",
            "clean vehicle",
            "electric vehicle",
            "ev",
            "vehicle credit",
            "consumer credit",
            "tax credit",
        ),
        exposure_channel="Clean-vehicle credit credibility changes demand-side support for EV adoption.",
        paper_evidence="Transportation is policy-sensitive but less central to the paper's direct Energy/Carbon treatment contrast.",
    ),
    "50144": ProvisionExposure(
        provision="50144",
        sectors=("Energy", "DOE LPO"),
        market_keywords=(
            "50144",
            "energy infrastructure reinvestment",
            "department of energy",
            "doe",
            "loan programs office",
            "lpo",
            "loan guarantee",
        ),
        exposure_channel="LPO authority credibility affects capital-intensive energy-infrastructure financing expectations.",
        paper_evidence="The HMM results emphasize shifts toward non-dilutive and mixed financing regimes after IRA support.",
    ),
    "50141": ProvisionExposure(
        provision="50141",
        sectors=("Energy", "DOE LPO"),
        market_keywords=(
            "50141",
            "loan programs office",
            "lpo",
            "doe",
            "loan guarantee",
            "unobligated balances",
            "appropriation",
        ),
        exposure_channel="LPO funding credibility affects public-capital availability for clean-energy deployment.",
        paper_evidence="The paper's financing-regime evidence links IRA design to shifts in public and private capital mixes.",
    ),
}


def provision_keywords(provision: str) -> tuple[str, ...]:
    exposure = PROVISION_EXPOSURES.get(provision)
    return exposure.market_keywords if exposure else ()


def has_tracked_provision_overlap(text: str) -> bool:
    terms: set[str] = set()
    for provision, exposure in PROVISION_EXPOSURES.items():
        terms.add(provision)
        terms.update(exposure.market_keywords)
    return any(text_contains_keyword(text, term) for term in terms)


def infer_policy_orientation(text: str) -> str:
    lowered = text.lower()
    adverse = sum(1 for term in ADVERSE_POLICY_TERMS if term in lowered)
    supportive = sum(1 for term in SUPPORTIVE_POLICY_TERMS if term in lowered)
    if adverse > supportive:
        return "adverse_policy_change"
    if supportive > adverse:
        return "supportive_policy_continuity"
    return "unknown"


def text_contains_keyword(text: str, keyword: str) -> bool:
    lowered = text.lower()
    normalized = keyword.strip().lower()
    if not normalized:
        return False
    if len(normalized) <= 3 or normalized.replace(" ", "").isalnum():
        pattern = r"(?<![a-z0-9])" + re.escape(normalized) + r"(?![a-z0-9])"
        return bool(re.search(pattern, lowered))
    return normalized in lowered


def is_policy_relevant_text(text: str) -> bool:
    has_policy_context = any(
        text_contains_keyword(text, keyword) for keyword in POLICY_MARKET_KEYWORDS
    )
    return has_policy_context and has_tracked_provision_overlap(text)
