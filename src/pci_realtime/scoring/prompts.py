from __future__ import annotations

from typing import Any, Mapping

from pci_realtime.config import TRACKED_PROVISIONS


SCREENING_PROMPT_VERSION = "screening-v1.0.0"
SCORING_PROMPT_VERSION = "scoring-v1.0.0"


SCREENING_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "status": {"type": "string", "enum": ["relevant", "irrelevant", "ambiguous"]},
        "provisions": {
            "type": "array",
            "items": {"type": "string", "enum": list(TRACKED_PROVISIONS)},
        },
        "rationale": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["status", "provisions", "rationale", "confidence"],
}


SCORING_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "provision": {"type": "string", "enum": list(TRACKED_PROVISIONS)},
        "specificity_delta": {"type": "number"},
        "durability_delta": {"type": "number"},
        "enforceability_delta": {"type": "number"},
        "rationale": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": [
        "provision",
        "specificity_delta",
        "durability_delta",
        "enforceability_delta",
        "rationale",
        "confidence",
    ],
}


SCREENING_SYSTEM_PROMPT = """You are screening federal policy documents for the Policy Credibility Index realtime monitor.

Classify whether the document has substantive implications for one or more tracked Inflation Reduction Act provisions. Return:
- relevant: the document can affect specificity, durability, or enforceability for at least one tracked provision.
- irrelevant: the document mentions climate, IRA, or agencies but has no substantive connection to tracked provisions.
- ambiguous: the document might matter, but the affected provision or credibility effect cannot be determined from the text.

Never infer a provision that is not supported by the document text. Ambiguous classifications will be skipped downstream."""


SCORING_SYSTEM_PROMPT = """You score document-level deltas for the Policy Credibility Index realtime monitor.

PCI measures institutional design quality, not investor sentiment. Score the document's effect on exactly one tracked IRA provision across:
- specificity: rule-based eligibility versus discretionary allocation;
- durability: statutory horizon and insulation from reversal or annual appropriation;
- enforceability: agency assignment, implementation procedure, and administrative reliability.

Return deltas on the underlying 1-5 dimension scale. Use 0.0 when the document mentions a provision but does not change that dimension. Stay within [-2.0, 2.0]."""


def compact_document(document: Mapping[str, Any], max_body_chars: int = 20_000) -> str:
    body = str(document.get("body", "") or "")
    if len(body) > max_body_chars:
        body = body[:max_body_chars]
    fields = [
        ("doc_id", document.get("doc_id", "")),
        ("date", document.get("date", "")),
        ("source", document.get("source", "")),
        ("agency", document.get("agency", "")),
        ("title", document.get("title", "")),
        ("url", document.get("url", "")),
        ("provisions_mentioned", document.get("provisions_mentioned", [])),
        ("body", body),
    ]
    return "\n".join(f"{name}: {value}" for name, value in fields)


def build_screening_user_prompt(document: Mapping[str, Any]) -> str:
    return (
        "Screen this document against the six tracked provisions only:\n"
        f"{', '.join(TRACKED_PROVISIONS)}\n\n"
        f"{compact_document(document)}"
    )


def build_scoring_user_prompt(document: Mapping[str, Any], provision: str) -> str:
    return (
        f"Score this document for provision {provision} only. "
        "Return the provision field exactly as requested.\n\n"
        f"{compact_document(document)}"
    )
