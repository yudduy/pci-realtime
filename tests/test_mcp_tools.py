from __future__ import annotations

import asyncio

from pci_realtime.mcp_server import mcp


CANONICAL_TOOL_NAMES = [
    "status",
    "list_policies",
    "current_pci",
    "policy_dossier",
    "get_evidence_trace",
    "submit_policy_evidence",
    "ingest_source_url",
    "list_verticals",
    "vertical_status",
]


def test_fastmcp_tool_names_match_canonical_surface() -> None:
    tools = asyncio.run(mcp.list_tools())

    assert [tool.name for tool in tools] == CANONICAL_TOOL_NAMES
