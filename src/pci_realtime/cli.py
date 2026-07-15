"""Command-line interface for the PCIndex agent service."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import typer
from rich.console import Console
from rich.table import Table

from pci_realtime import service
from pci_realtime.env import load_local_env
from pci_realtime.service_errors import ServiceError

load_local_env()


app = typer.Typer(
    name="pci",
    no_args_is_help=True,
    add_completion=False,
    help="PCIndex policy evidence service.",
)
_out = Console()
_err = Console(stderr=True)


def _run(
    fn: Callable[[], dict[str, Any]],
    *,
    as_json: bool,
    table: Callable[[dict[str, Any]], None],
) -> None:
    try:
        payload = fn()
    except ServiceError as exc:
        _err.print(f"error ({exc.code}): {exc.message}")
        raise typer.Exit(code=exc.exit_code) from exc
    if as_json:
        typer.echo(json.dumps(payload, default=str))
    else:
        table(payload)


@app.command()
def status(json_out: bool = typer.Option(False, "--json")) -> None:
    """Check registry reachability."""
    _run(service.status, as_json=json_out, table=_status_table)


@app.command()
def policies(json_out: bool = typer.Option(False, "--json")) -> None:
    """List tracked policy units."""
    _run(service.list_policies, as_json=json_out, table=_policies_table)


@app.command()
def verticals(json_out: bool = typer.Option(False, "--json")) -> None:
    """List climate-tech verticals and their weighted PCI."""
    _run(service.list_verticals, as_json=json_out, table=_verticals_table)


@app.command()
def current(
    code: str | None = typer.Argument(None),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Show current PCI for one policy or all policies."""
    _run(lambda: service.current_pci(code), as_json=json_out, table=_current_table)


@app.command()
def dossier(
    code: str = typer.Argument(...),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Show evidence, events, and submissions for a policy."""
    _run(lambda: service.policy_dossier(code), as_json=json_out, table=_dossier_table)


@app.command()
def submit(
    code: str = typer.Argument(...),
    source_json: Path = typer.Option(..., "--source-json"),
    citation_json: Path = typer.Option(..., "--citation-json"),
    claim: str = typer.Option(..., "--claim"),
    idempotency_key: str = typer.Option(..., "--idempotency-key"),
    agent_run_id: str | None = typer.Option(None, "--agent-run-id"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Submit citeable public evidence into the registry."""
    source = json.loads(source_json.read_text(encoding="utf-8"))
    citation = json.loads(citation_json.read_text(encoding="utf-8"))
    _run(
        lambda: service.submit_policy_evidence(
            provision=code,
            source=source,
            citation=citation,
            claim=claim,
            idempotency_key=idempotency_key,
            agent_run_id=agent_run_id,
        ),
        as_json=json_out,
        table=_submission_table,
    )


def _status_table(payload: dict[str, Any]) -> None:
    _out.print(json.dumps(payload, indent=2, default=str))


def _policies_table(payload: dict[str, Any]) -> None:
    columns = ("code", "name", "type", "baseline_pci")
    table = Table(title=f"Tracked policies ({payload.get('count', 0)})")
    for column in columns:
        table.add_column(column)
    for row in payload.get("policies", []):
        table.add_row(*(str(row.get(column, "")) for column in columns))
    _out.print(table)


def _verticals_table(payload: dict[str, Any]) -> None:
    columns = (
        "id",
        "name",
        "vertical_pci",
        "weekly_delta",
        "as_of_week_start",
        "provisions",
    )
    table = Table(title="Climate-tech verticals")
    for column in columns:
        table.add_column(column)
    for row in payload.get("verticals", []):
        table.add_row(
            *(
                ", ".join(value)
                if isinstance(value, list)
                else ""
                if value is None
                else str(value)
                for value in (row.get(column) for column in columns)
            )
        )
    _out.print(table)
    uncovered = payload.get("uncovered", [])
    if uncovered:
        _out.print(f"Uncovered (methodology pending): {', '.join(uncovered)}")


def _current_table(payload: dict[str, Any]) -> None:
    rows = payload.get("policies") or [payload]
    table = Table(title="Current PCI")
    for column in (
        "code",
        "name",
        "pci",
        "specificity",
        "durability",
        "enforceability",
    ):
        table.add_column(column)
    for row in rows:
        table.add_row(
            *(
                str(row.get(column, ""))
                for column in (
                    "code",
                    "name",
                    "pci",
                    "specificity",
                    "durability",
                    "enforceability",
                )
            )
        )
    _out.print(table)


def _dossier_table(payload: dict[str, Any]) -> None:
    policy = payload.get("policy", {})
    _out.print(f"{policy.get('code')} {policy.get('name')}")
    _out.print(
        f"events={len(payload.get('events', []))} "
        f"evidence={len(payload.get('evidence', []))} "
        f"submissions={len(payload.get('submissions', []))}"
    )


def _submission_table(payload: dict[str, Any]) -> None:
    _out.print(json.dumps(payload, indent=2, default=str))


if __name__ == "__main__":  # pragma: no cover
    app()
