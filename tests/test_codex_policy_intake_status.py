from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_status_module():
    module_path = (
        Path(__file__).parents[1] / "scripts" / "status_codex_policy_intake_daemon.py"
    )
    spec = importlib.util.spec_from_file_location(
        "status_codex_policy_intake_daemon", module_path
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_codex_policy_intake_status_summarizes_latest_run(tmp_path: Path) -> None:
    module = _load_status_module()
    repo_root = tmp_path / "repo"
    log_root = repo_root / "data" / "private" / "codex-daemon"
    run_dir = log_root / "20260624T033914Z"
    run_dir.mkdir(parents=True)
    (repo_root / ".env").write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=sk-test",
                "SUPABASE_URL=https://example.supabase.co",
                "SUPABASE_SERVICE_ROLE_KEY=service-role",
            ]
        ),
        encoding="utf-8",
    )
    _write_json(
        run_dir / "status.json",
        {
            "state": "completed",
            "started_at": "2026-06-24T03:39:14Z",
            "completed_at": "2026-06-24T03:42:14Z",
            "since_date": "2026-05-25",
            "codex_exit_code": 0,
            "report_exit_code": 0,
            "artifacts": {
                "policy_discovery_payload": str(
                    run_dir / "policy_discovery_payload.json"
                ),
            },
        },
    )
    _write_json(
        run_dir / "policy_discovery_payload.json",
        {
            "run_id": "run-1",
            "counts": {
                "pipeline_runs": 1,
                "policy_source_candidates": 1,
                "source_health": 2,
            },
            "rows": {
                "policy_source_candidates": [
                    {
                        "candidate_id": "candidate-1",
                        "provision": "45V",
                        "review_state": "queued",
                        "promotability": "ledger_candidate",
                        "title": "DOE hydrogen guidance",
                        "canonical_url": "https://www.energy.gov/example",
                    }
                ],
                "source_health": [
                    {"source": "openai_web_search", "status": "success"},
                    {
                        "source": "congress",
                        "status": "disabled",
                        "last_error_summary": "CONGRESS_GOV_API_KEY is not configured",
                    },
                ],
            },
        },
    )

    status = module.build_status(
        repo_root=repo_root,
        log_root=log_root,
        launch_agent_path=tmp_path / "missing.plist",
        check_launchctl=False,
    )
    rendered = module.render_status(status)

    assert status["latest_run"]["run_dir"] == str(run_dir)
    assert status["latest_run"]["codex_exit_code"] == 0
    assert status["credentials"]["OPENAI_API_KEY"] is True
    assert status["credentials"]["REGULATIONS_GOV_API_KEY"] is False
    assert status["discovery"]["candidates"]["total"] == 1
    assert status["discovery"]["source_health"]["by_status"] == {
        "disabled": 1,
        "success": 1,
    }
    assert "DOE hydrogen guidance" in rendered
    assert "CONGRESS_GOV_API_KEY is not configured" in rendered
    assert "Supabase write credentials: configured" in rendered


def test_codex_policy_intake_status_handles_empty_log_root(tmp_path: Path) -> None:
    module = _load_status_module()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    status = module.build_status(
        repo_root=repo_root,
        log_root=tmp_path / "missing-log-root",
        launch_agent_path=tmp_path / "missing.plist",
        check_launchctl=False,
    )
    rendered = module.render_status(status)

    assert status["latest_run"]["run_dir"] is None
    assert "Run directory: `none`" in rendered
    assert "Candidates: `0`" in rendered
    assert "OpenAI web search: missing" in rendered


def test_codex_policy_intake_status_ignores_newer_smoke_runs(tmp_path: Path) -> None:
    module = _load_status_module()
    log_root = tmp_path / "codex-daemon"
    real_run = log_root / "20260624T033914Z"
    incomplete_run = log_root / "20260624T034917Z"
    smoke_run = log_root / "20260624T041714Z"
    real_run.mkdir(parents=True)
    incomplete_run.mkdir(parents=True)
    smoke_run.mkdir(parents=True)
    (incomplete_run / "prompt.md").write_text("prompt", encoding="utf-8")
    _write_json(real_run / "policy_discovery_payload.json", {"run_id": "real-run"})
    _write_json(smoke_run / "status.json", {"state": "smoke"})

    assert module.latest_run_dir(log_root) == real_run
    assert module.latest_run_dir(log_root, include_smoke=True) == smoke_run


def test_codex_policy_intake_status_infers_legacy_payload_window(
    tmp_path: Path,
) -> None:
    module = _load_status_module()
    repo_root = tmp_path / "repo"
    log_root = repo_root / "data" / "private" / "codex-daemon"
    run_dir = log_root / "20260624T033914Z"
    run_dir.mkdir(parents=True)
    _write_json(
        run_dir / "policy_discovery_payload.json",
        {
            "run_id": "legacy-run",
            "rows": {
                "pipeline_runs": [
                    {
                        "status": "failed",
                        "metadata": {
                            "window_start": "2026-05-25",
                            "window_end": "2026-06-24",
                        },
                    }
                ],
                "policy_source_candidates": [],
                "source_health": [],
            },
        },
    )

    status = module.build_status(
        repo_root=repo_root,
        log_root=log_root,
        launch_agent_path=tmp_path / "missing.plist",
        check_launchctl=False,
    )
    rendered = module.render_status(status)

    assert status["latest_run"]["state"] == "completed_legacy"
    assert status["latest_run"]["since_date"] == "2026-05-25"
    assert status["latest_run"]["through_date"] == "2026-06-24"
    assert status["latest_run"]["pipeline_status"] == "failed"
    assert "State: `completed_legacy`" in rendered
    assert "Through date: `2026-06-24`" in rendered
    assert "Pipeline status: `failed`" in rendered


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")
