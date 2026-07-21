from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pci_realtime.research.models import LaneBrief, ResearchLaneResult


class ResearchProviderError(RuntimeError):
    """A research provider failed in a way that permits fallback."""


class ResearchBudgetExceeded(RuntimeError):
    """The shared provider-request budget would be exceeded."""


@dataclass
class RequestBudget:
    max_requests: int
    used: int = 0

    def spend(self, count: int = 1) -> None:
        if self.used + count > self.max_requests:
            raise ResearchBudgetExceeded(
                f"Research request budget exhausted: {self.used} used, "
                f"{count} requested, {self.max_requests} maximum."
            )
        self.used += count


class ResearchProvider(Protocol):
    name: str

    def estimated_cost_per_lane_usd(self) -> float: ...

    def run_research(
        self,
        brief: LaneBrief,
        *,
        budget: RequestBudget,
    ) -> ResearchLaneResult: ...
