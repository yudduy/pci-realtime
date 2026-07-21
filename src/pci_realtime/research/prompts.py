from __future__ import annotations

from pci_realtime.config import PROVISION_DETAILS
from pci_realtime.research.models import LaneBrief


def build_lane_research_prompt(brief: LaneBrief) -> str:
    lines = [
        f"Research current policy developments for {brief.vertical_name}.",
        f"Coverage boundary: {brief.coverage_note}",
        (
            "Only include sources published or materially updated on or after "
            f"{brief.since.isoformat()}."
        ),
        "Separate official (.gov) sources from news and analysis sources.",
        "For every official source, include a short verbatim quote that supports the claim.",
        "Never invent URLs, dates, or quotes.",
        f"Return at most {brief.max_findings} findings.",
        "",
        "Tracked provisions:",
    ]
    for provision in brief.provisions:
        details = PROVISION_DETAILS[provision]
        lines.append(f"- {provision}: {details['name']} ({details['primary_channel']})")
    lines.extend(
        [
            "",
            "Keyword vocabulary:",
            ", ".join(brief.keywords),
        ]
    )
    return "\n".join(lines)
