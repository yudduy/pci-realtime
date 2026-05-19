from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pci_realtime.config import CACHE_ROOT


@dataclass(frozen=True)
class StructuredLLMResponse:
    payload: dict[str, Any]
    raw_response: str
    usage: dict[str, Any]
    cost_usd: float
    cached: bool = False


def normalize_for_hash(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def build_cache_key(
    *,
    provider: str,
    model: str,
    prompt_version: str,
    temperature: float,
    schema_version: str,
    stage: str,
    input_payload: dict[str, Any],
) -> str:
    payload = {
        "provider": provider,
        "model": model,
        "prompt_version": prompt_version,
        "temperature": temperature,
        "schema_version": schema_version,
        "stage": stage,
        "input": input_payload,
    }
    return hashlib.sha256(normalize_for_hash(payload).encode("utf-8")).hexdigest()


class JsonCache:
    """Small JSON-file cache for audit-friendly LLM responses."""

    def __init__(self, root: Path = CACHE_ROOT) -> None:
        self.root = root

    def path_for_key(self, key: str) -> Path:
        return self.root / f"{key}.json"

    def get(self, key: str) -> StructuredLLMResponse | None:
        path = self.path_for_key(key)
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return StructuredLLMResponse(
            payload=dict(data["payload"]),
            raw_response=str(data.get("raw_response", "")),
            usage=dict(data.get("usage", {})),
            cost_usd=0.0,
            cached=True,
        )

    def set(self, key: str, response: StructuredLLMResponse) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.path_for_key(key)
        tmp_path = path.with_suffix(".tmp")
        payload = {
            "payload": response.payload,
            "raw_response": response.raw_response,
            "usage": response.usage,
            "cost_usd": response.cost_usd,
        }
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        tmp_path.replace(path)
        return path
