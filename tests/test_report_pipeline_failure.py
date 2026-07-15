from __future__ import annotations

import runpy
from pathlib import Path

from conftest import RecordingSupabaseClient


REPORT_FAILURE = runpy.run_path(
    str(Path(__file__).parents[1] / "scripts" / "report_pipeline_failure.py")
)["report_failure"]


def test_report_failure_writes_pipeline_run_and_source_health(monkeypatch) -> None:
    client = RecordingSupabaseClient()
    run_url = "https://github.com/example/pci-realtime/actions/runs/12345"
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("GITHUB_REPOSITORY", "example/pci-realtime")
    monkeypatch.setenv("GITHUB_RUN_ID", "12345")

    REPORT_FAILURE("weekly", client=client)  # type: ignore[arg-type]

    assert [
        (method, table, conflict) for method, table, _, conflict in client.calls
    ] == [
        ("insert", "pipeline_runs", None),
        ("upsert", "source_health", "source"),
    ]
    pipeline_run = client.calls[0][2][0]
    assert pipeline_run["run_type"] == "weekly"
    assert pipeline_run["status"] == "failed"
    assert pipeline_run["source"] == "github-actions"
    assert pipeline_run["completed_at"]
    assert pipeline_run["metadata"] == {
        "github_run_id": "12345",
        "github_run_url": run_url,
    }
    health = client.calls[1][2][0]
    assert health["source"] == "pipeline"
    assert health["status"] == "failed"
    assert health["last_attempt_at"] == pipeline_run["completed_at"]
    assert health["last_error_class"] == "GitHubActionsFailure"
    assert health["last_error_summary"] == run_url
    assert health["details"] == {"notes": run_url}


def test_report_failure_attempts_health_upsert_after_run_insert_failure(capsys) -> None:
    client = RecordingSupabaseClient(fail_on_table="pipeline_runs")

    REPORT_FAILURE("weekly", client=client)  # type: ignore[arg-type]

    assert [table for _, table, _, _ in client.calls] == [
        "pipeline_runs",
        "source_health",
    ]
    assert "warning: failure report incomplete" in capsys.readouterr().out
