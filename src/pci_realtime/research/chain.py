from __future__ import annotations

import logging
import os
from collections.abc import Sequence

import httpx

from pci_realtime.config import RESEARCH_DEFAULT_PROVIDERS
from pci_realtime.research.base import (
    RequestBudget,
    ResearchProvider,
    ResearchProviderError,
)
from pci_realtime.research.models import LaneBrief, ResearchLaneResult
from pci_realtime.research.openai_web import OpenAIWebSearchProvider


LOGGER = logging.getLogger(__name__)
_PROVIDER_FACTORIES = {"openai": OpenAIWebSearchProvider}
_PROVIDER_API_KEYS = {"openai": "OPENAI_API_KEY"}


class FallbackChain:
    def __init__(self, providers: Sequence[ResearchProvider]) -> None:
        if not providers:
            raise ValueError("FallbackChain requires at least one provider.")
        self.providers = tuple(providers)

    @property
    def name(self) -> str:
        return ">".join(provider.name for provider in self.providers)

    def estimated_cost_per_lane_usd(self) -> float:
        return sum(
            provider.estimated_cost_per_lane_usd() for provider in self.providers
        )

    def run_research(
        self,
        brief: LaneBrief,
        *,
        budget: RequestBudget,
    ) -> ResearchLaneResult:
        failed_notes: list[str] = []
        for provider in self.providers:
            try:
                result = provider.run_research(brief, budget=budget)
            except (ResearchProviderError, httpx.HTTPError) as exc:
                note = f"{provider.name} failed: {type(exc).__name__}: {exc}"
                LOGGER.warning(note)
                failed_notes.append(note)
                continue
            if failed_notes:
                return result.model_copy(
                    update={"notes": [*failed_notes, *result.notes]}
                )
            return result
        raise ResearchProviderError(
            "All research providers failed: " + "; ".join(failed_notes)
        )


def build_provider_chain(spec: str | None = None) -> FallbackChain:
    resolved = (
        spec
        or os.getenv("PCI_RESEARCH_PROVIDERS")
        or os.getenv("PCI_RESEARCH_PROVIDER")
        or RESEARCH_DEFAULT_PROVIDERS
    )
    names = [name.strip().lower() for name in resolved.split(",") if name.strip()]
    valid_names = sorted(_PROVIDER_FACTORIES)
    unknown = sorted(set(names) - set(valid_names))
    if unknown:
        raise RuntimeError(
            f"Unknown research provider(s): {', '.join(unknown)}. "
            f"Valid providers: {', '.join(valid_names)}."
        )
    if not names:
        raise RuntimeError(
            f"No research providers requested. Valid providers: {', '.join(valid_names)}."
        )

    providers: list[ResearchProvider] = []
    skipped: list[str] = []
    for name in names:
        env_name = _PROVIDER_API_KEYS[name]
        if not os.getenv(env_name):
            note = f"Skipping research provider {name}: {env_name} is not configured."
            LOGGER.warning(note)
            skipped.append(note)
            continue
        providers.append(_PROVIDER_FACTORIES[name]())

    if not providers:
        details = " ".join(skipped)
        raise RuntimeError(f"No configured research providers are available. {details}")
    return FallbackChain(providers)
