from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


ROOT = Path(__file__).resolve().parents[1]


def load_env(path: Path) -> dict[str, str]:
    env = os.environ.copy()
    if not path.exists():
        return env
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def parse_tool_result(result: Any) -> dict[str, Any] | str:
    if result.isError:
        return {
            "is_error": True,
            "message": result.content[0].text if result.content else "",
        }
    text = result.content[0].text if result.content else ""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


async def call_tool(
    session: ClientSession,
    name: str,
    args: dict[str, Any] | None = None,
) -> dict[str, Any] | str:
    return parse_tool_result(await session.call_tool(name, args or {}))


async def run_smoke(write_smoke: bool) -> int:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "pci_realtime.mcp_server"],
        cwd=str(ROOT),
        env=load_env(ROOT / ".env"),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            tools = await session.list_tools()
            print(f"MCP server: {init.serverInfo.name} {init.serverInfo.version}")
            print("Tools:", ", ".join(tool.name for tool in tools.tools))

            status = await call_tool(session, "status")
            print("Status:", json.dumps(status, indent=2))

            policies = await call_tool(session, "list_policies")
            if not isinstance(policies, dict):
                print("Could not read policies.")
                return 1
            print(f"Tracked policies: {policies.get('count')}")

            current = await call_tool(session, "current_pci", {"code": "45V"})
            print("45V current:", json.dumps(current, indent=2))

            trace = await call_tool(session, "get_evidence_trace", {"provision": "45V"})
            if isinstance(trace, dict):
                print(
                    "45V trace:",
                    json.dumps(
                        {
                            "evidence": len(trace.get("evidence", [])),
                            "links": len(trace.get("links", [])),
                            "events": len(trace.get("events", [])),
                        },
                        indent=2,
                    ),
                )

            if not write_smoke:
                return 0

            write_result = await call_tool(
                session,
                "submit_policy_evidence",
                {
                    "provision": "45V",
                    "source": {
                        "url": "https://www.irs.gov/forms-pubs/about-form-7210",
                        "title": "About Form 7210, Clean Hydrogen Production Credit",
                        "source_name": "Internal Revenue Service",
                        "published_at": "2026-02-20",
                    },
                    "citation": {
                        "quote": (
                            "Use Form 7210 to claim the section 45V credit for "
                            "the production of qualified clean hydrogen"
                        ),
                        "section": "About Form 7210",
                    },
                    "claim": (
                        "MCP smoke test: IRS directs taxpayers to use Form 7210 "
                        "to claim the section 45V clean hydrogen production credit."
                    ),
                    "idempotency_key": "mcp-smoke-45v-form-7210-2026-02-20",
                    "agent_name": "mcp-smoke-test",
                    "question": (
                        "Can the MCP server submit cited 45V evidence end to end?"
                    ),
                },
            )
            print("Write smoke:", json.dumps(write_result, indent=2))
            return (
                1
                if isinstance(write_result, dict) and write_result.get("is_error")
                else 0
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test the PCIndex MCP server.")
    parser.add_argument(
        "--write-smoke",
        action="store_true",
        help="Attempt a real write through submit_policy_evidence.",
    )
    args = parser.parse_args()
    raise SystemExit(anyio.run(run_smoke, args.write_smoke))


if __name__ == "__main__":
    main()
