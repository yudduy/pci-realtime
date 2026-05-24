from __future__ import annotations

import pytest

from pci_realtime.scoring.cache import StructuredLLMResponse
from pci_realtime.scoring.screener import (
    DocumentScreener,
    create_structured_output_client,
    parse_screening_payload,
)


class FakeStructuredClient:
    provider = "fake"

    def __init__(self, payloads: list[dict]) -> None:
        self.payloads = payloads
        self.calls = 0

    def create_json(self, **_: object) -> StructuredLLMResponse:
        self.calls += 1
        return StructuredLLMResponse(
            payload=self.payloads.pop(0),
            raw_response="{}",
            usage={},
            cost_usd=0.10,
        )


def _document() -> dict:
    return {
        "doc_id": "federal_register:1",
        "title": "Section 45X guidance",
        "body": "Advanced manufacturing production credit guidance.",
        "provisions_mentioned": ["45X"],
    }


def test_parse_screening_payload_rejects_bad_confidence() -> None:
    with pytest.raises(ValueError, match="confidence"):
        parse_screening_payload(
            {
                "status": "relevant",
                "provisions": ["45X"],
                "rationale": "x",
                "confidence": 1.5,
            },
            model="gpt-4.1-mini",
            prompt_version="v1",
            temperature=0.3,
            cached=False,
            cost_usd=0.1,
        )


def test_create_structured_output_client_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        create_structured_output_client("not-a-provider")


def test_screener_returns_ambiguous_skip_state(tmp_path) -> None:
    client = FakeStructuredClient(
        [
            {
                "status": "ambiguous",
                "provisions": [],
                "rationale": "Provision cannot be determined.",
                "confidence": 0.6,
            }
        ]
    )
    screener = DocumentScreener(client=client, cache=None)
    screener.cache.root = tmp_path

    result = screener.screen_document(_document())

    assert result.status == "ambiguous"
    assert result.relevant is False
    assert client.calls == 1


def test_screener_uses_cache_on_second_call(tmp_path) -> None:
    client = FakeStructuredClient(
        [
            {
                "status": "relevant",
                "provisions": ["45X"],
                "rationale": "Substantive guidance.",
                "confidence": 0.9,
            }
        ]
    )
    screener = DocumentScreener(client=client, cache=None)
    screener.cache.root = tmp_path

    first = screener.screen_document(_document())
    second = screener.screen_document(_document())

    assert first.cached is False
    assert first.cost_usd == 0.10
    assert second.cached is True
    assert second.cost_usd == 0.0
    assert client.calls == 1
