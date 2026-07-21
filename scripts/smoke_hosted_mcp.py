from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, NoReturn

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import CallToolResult, TextContent

from pci_realtime.env import load_local_env


DEFAULT_URL = "https://fdxinkqiarezurwofhmz.supabase.co/functions/v1/mcp"
EXPECTED_TOOLS = (
    "status",
    "list_policies",
    "current_pci",
    "policy_dossier",
    "get_evidence_trace",
    "list_verticals",
    "vertical_status",
    "list_changes",
)
EXPECTED_VERTICALS = (
    "advanced-manufacturing",
    "clean-hydrogen",
    "carbon-capture",
    "electric-vehicles",
    "clean-energy-finance",
)
CHANGE_KEYS_PATH = (
    Path(__file__).resolve().parents[1] / "contracts/change-event-keys.json"
)


class SmokeFailure(RuntimeError):
    """A hosted MCP contract check failed."""


def pass_check(message: str) -> None:
    print(f"PASS: {message}")


def fail_check(check: str, detail: str) -> NoReturn:
    print(f"FAIL: {check}: {detail}", file=sys.stderr)
    raise SmokeFailure(detail)


def result_text(result: CallToolResult, check: str) -> str:
    text_parts = [
        content.text for content in result.content if isinstance(content, TextContent)
    ]
    if not text_parts:
        fail_check(check, "tool result contained no text content")
    return "\n".join(text_parts)


def json_payload(result: CallToolResult, check: str) -> dict[str, Any]:
    if result.isError:
        fail_check(check, result_text(result, check))
    try:
        payload = json.loads(result_text(result, check))
    except json.JSONDecodeError as exc:
        fail_check(check, f"tool result was not JSON: {exc}")
    if not isinstance(payload, dict):
        fail_check(check, "tool result JSON was not an object")
    return payload


def load_change_keys() -> set[str]:
    contract = json.loads(CHANGE_KEYS_PATH.read_text(encoding="utf-8"))
    return set(contract["change"])


async def run_smoke(url: str) -> None:
    expected_change_keys = load_change_keys()

    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            initialized = await session.initialize()
            if initialized.serverInfo.name != "pcindex":
                fail_check(
                    "server name",
                    f"expected 'pcindex', got {initialized.serverInfo.name!r}",
                )
            pass_check("server name is pcindex")

            tools = await session.list_tools()
            tool_names = tuple(tool.name for tool in tools.tools)
            if tool_names != EXPECTED_TOOLS:
                fail_check(
                    "tool names/order",
                    f"expected {EXPECTED_TOOLS!r}, got {tool_names!r}",
                )
            pass_check(f"tool names/order are pinned ({len(tool_names)} tools)")

            vertical_result = await session.call_tool("list_verticals", {})
            vertical_payload = json_payload(vertical_result, "vertical IDs/order")
            verticals = vertical_payload.get("verticals")
            if not isinstance(verticals, list) or not all(
                isinstance(vertical, dict) and isinstance(vertical.get("id"), str)
                for vertical in verticals
            ):
                fail_check(
                    "vertical IDs/order",
                    "list_verticals payload had an invalid verticals list",
                )
            vertical_ids = tuple(vertical["id"] for vertical in verticals)
            if vertical_ids != EXPECTED_VERTICALS:
                fail_check(
                    "vertical IDs/order",
                    f"expected {EXPECTED_VERTICALS!r}, got {vertical_ids!r}",
                )
            pass_check("vertical IDs/order match display_order")

            changes_result = await session.call_tool("list_changes", {})
            changes_payload = json_payload(changes_result, "change payload keys")
            changes = changes_payload.get("changes")
            if not isinstance(changes, list):
                fail_check(
                    "change payload keys",
                    "list_changes payload had no changes list",
                )
            for index, change in enumerate(changes):
                if not isinstance(change, dict):
                    fail_check(
                        "change payload keys",
                        f"change {index} was not an object",
                    )
                actual_keys = set(change)
                if actual_keys != expected_change_keys:
                    fail_check(
                        "change payload keys",
                        f"change {index} expected {sorted(expected_change_keys)!r}, "
                        f"got {sorted(actual_keys)!r}",
                    )
            pass_check(f"change payload keys match contract ({len(changes)} changes)")

            invalid_result = await session.call_tool(
                "vertical_status",
                {"vertical_id": "geothermal"},
            )
            if not invalid_result.isError:
                invalid_text = result_text(
                    invalid_result,
                    "invalid vertical handling",
                )
                if not all(
                    vertical_id in invalid_text for vertical_id in EXPECTED_VERTICALS
                ):
                    fail_check(
                        "invalid vertical handling",
                        "result was not an error and did not name every valid vertical ID",
                    )
            pass_check("invalid vertical is rejected or names every valid vertical ID")


def build_parser(default_url: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Smoke test the hosted PCIndex MCP tool contract.",
    )
    parser.add_argument(
        "--url",
        default=default_url,
        help="Hosted streamable HTTP MCP endpoint.",
    )
    return parser


def main() -> None:
    load_local_env()
    default_url = os.environ.get("PCI_HOSTED_MCP_URL") or DEFAULT_URL
    args = build_parser(default_url).parse_args()
    try:
        asyncio.run(run_smoke(args.url))
    except SmokeFailure:
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
