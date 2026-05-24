from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from pci_realtime.ingest.base import SCHEMA_A_COLUMNS
from pci_realtime.scoring.cache import StructuredLLMResponse
from pci_realtime.scoring.scorer import (
    SCHEMA_B_COLUMNS,
    enforce_schema_b,
    parse_scoring_payload,
    run_week,
)


class FakeStructuredClient:
    provider = "fake"

    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self.payloads = payloads

    def create_json(self, **_: object) -> StructuredLLMResponse:
        return StructuredLLMResponse(
            payload=self.payloads.pop(0),
            raw_response="{}",
            usage={},
            cost_usd=0.10,
        )


def _document(doc_id: str = "federal_register:1") -> dict[str, Any]:
    return {
        "doc_id": doc_id,
        "date": pd.Timestamp("2024-10-24").date(),
        "source": "federal_register",
        "agency": "Internal Revenue Service",
        "title": "Section 45X final guidance",
        "body": "Final section 45X advanced manufacturing production credit rules.",
        "body_truncated": False,
        "url": "https://example.test/45x",
        "provisions_mentioned": ["45X"],
        "ingested_at": pd.Timestamp("2026-05-19", tz="UTC"),
        "ingestor_version": "0.1.0",
    }


def _scoring_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "provision": "45X",
        "specificity_delta": 0.5,
        "durability_delta": 0.0,
        "enforceability_delta": 0.4,
        "rationale": "Final guidance clarifies eligibility and process.",
        "confidence": 0.9,
    }
    payload.update(overrides)
    return payload


def test_parse_scoring_payload_validates_delta_range() -> None:
    with pytest.raises(ValueError, match="specificity_delta"):
        parse_scoring_payload(
            _scoring_payload(specificity_delta=2.5),
            document=_document(),
            expected_provision="45X",
            model="gpt-4.1",
            prompt_version="v1",
            temperature=0.3,
            cached=False,
            cost_usd=0.1,
        )


def test_parse_scoring_payload_requires_expected_provision() -> None:
    with pytest.raises(ValueError, match="Expected provision"):
        parse_scoring_payload(
            _scoring_payload(provision="45V"),
            document=_document(),
            expected_provision="45X",
            model="gpt-4.1",
            prompt_version="v1",
            temperature=0.3,
            cached=False,
            cost_usd=0.1,
        )


def test_enforce_schema_b_rejects_duplicate_doc_provision() -> None:
    row = parse_scoring_payload(
        _scoring_payload(),
        document=_document(),
        expected_provision="45X",
        model="gpt-4.1",
        prompt_version="v1",
        temperature=0.3,
        cached=False,
        cost_usd=0.1,
    ).to_row()

    with pytest.raises(ValueError, match="Duplicate"):
        enforce_schema_b([row, row])


def test_run_week_writes_schema_b_for_relevant_docs_only(tmp_path) -> None:
    raw_root = tmp_path / "raw"
    source_dir = raw_root / "federal_register"
    source_dir.mkdir(parents=True)
    raw_df = pd.DataFrame(
        [
            _document("federal_register:relevant"),
            _document("federal_register:ambiguous"),
        ],
        columns=SCHEMA_A_COLUMNS,
    )
    raw_df.to_parquet(source_dir / "federal_register_2024-W44.parquet", index=False)
    client = FakeStructuredClient(
        [
            {
                "status": "relevant",
                "provisions": ["45X"],
                "rationale": "Substantive 45X final rule.",
                "confidence": 0.9,
            },
            _scoring_payload(),
            {
                "status": "ambiguous",
                "provisions": [],
                "rationale": "Cannot determine provision effect.",
                "confidence": 0.5,
            },
        ]
    )

    output_path = run_week(
        week="2024-W44",
        raw_root=raw_root,
        output_dir=tmp_path / "processed" / "scored",
        cache_root=tmp_path / "cache",
        screening_provider="fake",
        screening_model="cheap-screen",
        scoring_provider="fake",
        scoring_model="cheap-score",
        client=client,
        confirm_cost=True,
        audit_log_path=tmp_path / "llm_call_log.jsonl",
    )

    scored = pd.read_parquet(output_path)
    assert list(scored.columns) == SCHEMA_B_COLUMNS
    assert len(scored) == 1
    assert scored.loc[0, "doc_id"] == "federal_register:relevant"
    assert scored.loc[0, "provision"] == "45X"
    assert scored.loc[0, "model"] == "cheap-score"
    assert Path(output_path).name == "scored_2024-W44.parquet"
