"""MCP server exposing PCIndex policy reads and evidence intake."""

from __future__ import annotations

import os
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

from pci_realtime import service
from pci_realtime.env import load_local_env
from pci_realtime.service_errors import ServiceError


load_local_env()


mcp = FastMCP("pcindex")
_READ = ToolAnnotations(readOnlyHint=True, openWorldHint=True)
_WRITE = ToolAnnotations(readOnlyHint=False, openWorldHint=True)
_LOCAL_READ = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
_Transport = Literal["stdio", "sse", "streamable-http"]
_SUPPORTED_TRANSPORTS: set[str] = {"stdio", "sse", "streamable-http"}


def _safe(call) -> dict[str, Any]:
    try:
        return call()
    except ServiceError as exc:
        raise ToolError(f"[{exc.code}] {exc.message}") from exc


@mcp.tool(annotations=_READ)
def status() -> dict[str, Any]:
    """Check registry connectivity and write readiness."""
    return service.status()


@mcp.tool(annotations=_LOCAL_READ)
def list_policies() -> dict[str, Any]:
    """List tracked PCIndex policy units."""
    return _safe(service.list_policies)


@mcp.tool(annotations=_READ)
def current_pci(code: str | None = None) -> dict[str, Any]:
    """Read current PCI for one tracked policy or all policies."""
    return _safe(lambda: service.current_pci(code))


@mcp.tool(annotations=_READ)
def policy_dossier(code: str) -> dict[str, Any]:
    """Read a policy dossier with events, evidence, and submissions."""
    return _safe(lambda: service.policy_dossier(code))


@mcp.tool(annotations=_WRITE)
def submit_policy_evidence(
    provision: str,
    source: dict[str, Any],
    citation: dict[str, Any],
    claim: str,
    idempotency_key: str,
    agent_run_id: str | None = None,
    agent_name: str | None = None,
    question: str | None = None,
) -> dict[str, Any]:
    """Submit citeable public policy evidence for automatic promotion."""
    return _safe(
        lambda: service.submit_policy_evidence(
            provision=provision,
            source=source,
            citation=citation,
            claim=claim,
            idempotency_key=idempotency_key,
            agent_run_id=agent_run_id,
            agent_name=agent_name,
            question=question,
        )
    )


@mcp.tool(annotations=_WRITE)
def ingest_source_url(
    provision: str,
    url: str,
    rationale: str,
    idempotency_key: str,
    agent_run_id: str | None = None,
    agent_name: str | None = None,
    question: str | None = None,
) -> dict[str, Any]:
    """Fetch a public URL and submit its text as policy evidence."""
    return _safe(
        lambda: service.ingest_source_url(
            provision=provision,
            url=url,
            rationale=rationale,
            idempotency_key=idempotency_key,
            agent_run_id=agent_run_id,
            agent_name=agent_name,
            question=question,
        )
    )


@mcp.tool(annotations=_READ)
def get_evidence_trace(
    provision: str,
    evidence_id: str | None = None,
) -> dict[str, Any]:
    """Read evidence rows and trace links for a policy."""
    return _safe(
        lambda: service.get_evidence_trace(
            provision=provision,
            evidence_id=evidence_id,
        )
    )


def configured_transport() -> _Transport:
    """Return the requested MCP transport, defaulting to local stdio."""
    value = os.environ.get("PCINDEX_MCP_TRANSPORT", "stdio").strip().lower()
    if value not in _SUPPORTED_TRANSPORTS:
        options = ", ".join(sorted(_SUPPORTED_TRANSPORTS))
        raise SystemExit(
            f"Unsupported PCINDEX_MCP_TRANSPORT={value!r}. Use one of: {options}."
        )
    return value  # type: ignore[return-value]


def configured_mount_path() -> str | None:
    """Return the mount path used by streamable HTTP or SSE transports."""
    value = os.environ.get("PCINDEX_MCP_MOUNT_PATH", "").strip()
    return value or None


def main() -> None:  # pragma: no cover
    mcp.run(transport=configured_transport(), mount_path=configured_mount_path())


if __name__ == "__main__":  # pragma: no cover
    main()
