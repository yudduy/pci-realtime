from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_report_module():
    module_path = (
        Path(__file__).parents[1] / "scripts" / "render_policy_intake_report.py"
    )
    spec = importlib.util.spec_from_file_location(
        "render_policy_intake_report", module_path
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_policy_intake_report_surfaces_concrete_source_details() -> None:
    module = _load_report_module()
    payload = {
        "run_id": "run-1",
        "counts": {
            "pipeline_runs": 1,
            "policy_source_candidates": 1,
            "source_health": 3,
        },
        "rows": {
            "pipeline_runs": [
                {
                    "metadata": {
                        "window_start": "2026-05-24",
                        "window_end": "2026-06-23",
                    }
                }
            ],
            "policy_source_candidates": [
                {
                    "candidate_id": "candidate-1",
                    "canonical_url": "https://www.irs.gov/example",
                    "citation_quote": "This notice provides interim guidance for the credit.",
                    "claim": "IRS changed the substantiation path for a tax credit.",
                    "confidence": 0.97,
                    "decision_relevance": "Affects taxpayer documentation and verifier review.",
                    "promotability": "ledger_candidate",
                    "provision": "45Q",
                    "published_at": "2026-06-10",
                    "review_state": "queued",
                    "source_class": "official",
                    "source_name": "Internal Revenue Service",
                    "title": "IRS interim guidance",
                    "why_it_matters": "Primary source with operational implications.",
                }
            ],
            "source_health": [
                {
                    "source": "irs",
                    "status": "success",
                    "row_count": 1,
                    "last_success_at": "2026-06-24T03:42:11Z",
                },
                {
                    "source": "congress",
                    "status": "disabled",
                    "row_count": 0,
                    "last_error_class": "MissingApiKey",
                    "last_error_summary": "CONGRESS_GOV_API_KEY is not configured",
                },
                {
                    "source": "openai_web_search",
                    "status": "success",
                    "row_count": 1,
                    "details": {"notes": ["No fresh source surfaced for 45V."]},
                },
            ],
        },
    }

    report = module.render_report(payload)

    assert "IRS interim guidance" in report
    assert "https://www.irs.gov/example" in report
    assert "IRS changed the substantiation path" in report
    assert "This notice provides interim guidance" in report
    assert "review quote against the primary source" in report
    assert "CONGRESS_GOV_API_KEY is not configured" in report
    assert "No fresh source surfaced for 45V" in report


def test_policy_intake_report_handles_empty_candidates() -> None:
    module = _load_report_module()
    report = module.render_report(
        {
            "run_id": "run-2",
            "counts": {},
            "rows": {
                "pipeline_runs": [],
                "policy_source_candidates": [],
                "source_health": [],
            },
        }
    )

    assert "No policy source candidates surfaced" in report
    assert "No source-health rows were produced" in report
