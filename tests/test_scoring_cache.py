from __future__ import annotations

from pci_realtime.scoring.cache import (
    JsonCache,
    StructuredLLMResponse,
    build_cache_key,
)


def test_cache_key_is_stable_for_equivalent_payloads() -> None:
    left = build_cache_key(
        provider="openai",
        model="gpt-4.1",
        prompt_version="v1",
        temperature=0.3,
        schema_version="schema",
        stage="scoring",
        input_payload={"b": 2, "a": 1},
    )
    right = build_cache_key(
        provider="openai",
        model="gpt-4.1",
        prompt_version="v1",
        temperature=0.3,
        schema_version="schema",
        stage="scoring",
        input_payload={"a": 1, "b": 2},
    )

    assert left == right


def test_json_cache_round_trips_response_and_marks_cached(tmp_path) -> None:
    cache = JsonCache(tmp_path)
    key = "abc123"
    cache.set(
        key,
        StructuredLLMResponse(
            payload={"provision": "45X"},
            raw_response='{"provision": "45X"}',
            usage={"input_tokens": 10},
            cost_usd=0.25,
        ),
    )

    cached = cache.get(key)

    assert cached is not None
    assert cached.payload == {"provision": "45X"}
    assert cached.cached is True
    assert cached.cost_usd == 0.0
