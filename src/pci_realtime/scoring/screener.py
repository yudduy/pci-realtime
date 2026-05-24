from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from pci_realtime.config import (
    CACHE_ROOT,
    LLM_SCREENING_MODEL,
    LLM_SCREENING_PROVIDER,
    SCORING_ESTIMATED_COST_PER_CALL_USD,
    SCORING_SCHEMA_VERSION,
    SCORING_TEMPERATURE,
    TRACKED_PROVISIONS,
)
from pci_realtime.scoring.cache import (
    JsonCache,
    StructuredLLMResponse,
    build_cache_key,
)
from pci_realtime.scoring.prompts import (
    SCREENING_JSON_SCHEMA,
    SCREENING_PROMPT_VERSION,
    SCREENING_SYSTEM_PROMPT,
    build_screening_user_prompt,
)


SCREENING_STATUSES = {"relevant", "irrelevant", "ambiguous"}


class StructuredOutputClient(Protocol):
    provider: str

    def create_json(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
        schema_name: str,
        temperature: float,
    ) -> StructuredLLMResponse: ...


@dataclass(frozen=True)
class ScreeningResult:
    status: str
    provisions: list[str]
    rationale: str
    confidence: float
    model: str
    prompt_version: str
    temperature: float
    cached: bool
    cost_usd: float
    raw_response: str = ""

    @property
    def relevant(self) -> bool:
        return self.status == "relevant"


def _extract_output_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return str(output_text)

    output = getattr(response, "output", None)
    if output:
        for item in output:
            content = getattr(item, "content", None)
            if not content and isinstance(item, dict):
                content = item.get("content")
            for part in content or []:
                text = getattr(part, "text", None)
                if text is None and isinstance(part, dict):
                    text = part.get("text")
                if text:
                    return str(text)

    msg = "OpenAI response did not include output text"
    raise ValueError(msg)


def _usage_to_dict(response: Any) -> dict[str, Any]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {}
    if hasattr(usage, "model_dump"):
        return dict(usage.model_dump())
    if isinstance(usage, dict):
        return dict(usage)
    return dict(vars(usage))


def _anthropic_usage_to_dict(response: Any) -> dict[str, Any]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {}
    if hasattr(usage, "model_dump"):
        return dict(usage.model_dump())
    return dict(vars(usage))


def _extract_anthropic_tool_input(response: Any, schema_name: str) -> dict[str, Any]:
    for block in getattr(response, "content", []) or []:
        block_type = getattr(block, "type", "")
        block_name = getattr(block, "name", "")
        if block_type == "tool_use" and block_name == schema_name:
            payload = getattr(block, "input", None)
            if isinstance(payload, dict):
                return payload
    msg = f"Anthropic response did not include tool input for {schema_name}"
    raise ValueError(msg)


def _response_to_text(response: Any) -> str:
    if hasattr(response, "model_dump_json"):
        return str(response.model_dump_json())
    if hasattr(response, "model_dump"):
        return json.dumps(response.model_dump(), default=str, sort_keys=True)
    return str(response)


class OpenAIStructuredOutputClient:
    provider = "openai"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        estimated_cost_per_call_usd: float = SCORING_ESTIMATED_COST_PER_CALL_USD,
    ) -> None:
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            msg = "OPENAI_API_KEY is required for live scoring runs"
            raise RuntimeError(msg)

        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)
        self.estimated_cost_per_call_usd = estimated_cost_per_call_usd

    def create_json(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
        schema_name: str,
        temperature: float,
    ) -> StructuredLLMResponse:
        response = self.client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            text={
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "schema": json_schema,
                    "strict": True,
                }
            },
        )
        raw_text = _extract_output_text(response)
        return StructuredLLMResponse(
            payload=json.loads(raw_text),
            raw_response=raw_text,
            usage=_usage_to_dict(response),
            cost_usd=self.estimated_cost_per_call_usd,
        )


class AnthropicStructuredOutputClient:
    provider = "anthropic"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        estimated_cost_per_call_usd: float = SCORING_ESTIMATED_COST_PER_CALL_USD,
    ) -> None:
        api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            msg = "ANTHROPIC_API_KEY is required for Anthropic scoring runs"
            raise RuntimeError(msg)

        from anthropic import Anthropic

        self.client = Anthropic(api_key=api_key)
        self.estimated_cost_per_call_usd = estimated_cost_per_call_usd

    def create_json(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
        schema_name: str,
        temperature: float,
    ) -> StructuredLLMResponse:
        response = self.client.messages.create(
            model=model,
            max_tokens=2048,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            tools=[
                {
                    "name": schema_name,
                    "description": "Return the requested PCI scoring payload.",
                    "input_schema": json_schema,
                }
            ],
            tool_choice={"type": "tool", "name": schema_name},
        )
        return StructuredLLMResponse(
            payload=_extract_anthropic_tool_input(response, schema_name),
            raw_response=_response_to_text(response),
            usage=_anthropic_usage_to_dict(response),
            cost_usd=self.estimated_cost_per_call_usd,
        )


def create_structured_output_client(
    provider: str | None = None,
) -> StructuredOutputClient:
    selected = (provider or LLM_SCREENING_PROVIDER).strip().lower()
    if selected == "openai":
        return OpenAIStructuredOutputClient()
    if selected == "anthropic":
        return AnthropicStructuredOutputClient()
    msg = f"Unsupported LLM provider: {provider!r}. Expected one of: openai, anthropic"
    raise ValueError(msg)


def parse_screening_payload(
    payload: Mapping[str, Any],
    *,
    model: str,
    prompt_version: str,
    temperature: float,
    cached: bool,
    cost_usd: float,
    raw_response: str = "",
) -> ScreeningResult:
    status = str(payload.get("status", ""))
    if status not in SCREENING_STATUSES:
        msg = f"Invalid screening status: {status!r}"
        raise ValueError(msg)

    provisions = [str(value) for value in payload.get("provisions", [])]
    invalid = sorted(set(provisions) - set(TRACKED_PROVISIONS))
    if invalid:
        msg = f"Invalid screening provisions: {invalid}"
        raise ValueError(msg)

    confidence = float(payload.get("confidence", -1.0))
    if not 0.0 <= confidence <= 1.0:
        msg = f"Screening confidence must be in [0, 1], got {confidence}"
        raise ValueError(msg)

    provisions = sorted(set(provisions))
    if status == "relevant" and not provisions:
        msg = "Relevant screening result must include at least one provision"
        raise ValueError(msg)

    return ScreeningResult(
        status=status,
        provisions=provisions,
        rationale=str(payload.get("rationale", "")),
        confidence=confidence,
        model=model,
        prompt_version=prompt_version,
        temperature=temperature,
        cached=cached,
        cost_usd=cost_usd,
        raw_response=raw_response,
    )


class DocumentScreener:
    def __init__(
        self,
        *,
        client: StructuredOutputClient | None = None,
        cache: JsonCache | None = None,
        provider: str = LLM_SCREENING_PROVIDER,
        model: str = LLM_SCREENING_MODEL,
        prompt_version: str = SCREENING_PROMPT_VERSION,
        temperature: float = SCORING_TEMPERATURE,
        schema_version: str = SCORING_SCHEMA_VERSION,
    ) -> None:
        self.client = client or create_structured_output_client(provider)
        self.cache = cache or JsonCache(CACHE_ROOT / "screening")
        self.model = model
        self.prompt_version = prompt_version
        self.temperature = temperature
        self.schema_version = schema_version

    def screen_document(self, document: Mapping[str, Any]) -> ScreeningResult:
        user_prompt = build_screening_user_prompt(document)
        input_payload = {
            "doc_id": str(document.get("doc_id", "")),
            "title": str(document.get("title", "")),
            "body": str(document.get("body", "")),
            "provisions_mentioned": list(
                document.get("provisions_mentioned", []) or []
            ),
        }
        cache_key = build_cache_key(
            provider=self.client.provider,
            model=self.model,
            prompt_version=self.prompt_version,
            temperature=self.temperature,
            schema_version=self.schema_version,
            stage="screening",
            input_payload=input_payload,
        )
        cached = self.cache.get(cache_key)
        if cached is not None:
            return parse_screening_payload(
                cached.payload,
                model=self.model,
                prompt_version=self.prompt_version,
                temperature=self.temperature,
                cached=True,
                cost_usd=0.0,
                raw_response=cached.raw_response,
            )

        response = self.client.create_json(
            model=self.model,
            system_prompt=SCREENING_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            json_schema=SCREENING_JSON_SCHEMA,
            schema_name="pci_document_screening",
            temperature=self.temperature,
        )
        self.cache.set(cache_key, response)
        return parse_screening_payload(
            response.payload,
            model=self.model,
            prompt_version=self.prompt_version,
            temperature=self.temperature,
            cached=False,
            cost_usd=response.cost_usd,
            raw_response=response.raw_response,
        )
