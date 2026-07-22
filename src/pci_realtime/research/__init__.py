"""Provider abstractions for per-vertical policy research."""

from pci_realtime.research.base import (
    RequestBudget,
    ResearchBudgetExceeded,
    ResearchProvider,
    ResearchProviderError,
)
from pci_realtime.research.chain import FallbackChain, build_provider_chain
from pci_realtime.research.exa import ExaProvider
from pci_realtime.research.models import (
    CANDIDATE_SCHEMA_VERSION,
    RESEARCH_PROMPT_VERSION,
    LaneBrief,
    ResearchFinding,
    ResearchLaneResult,
    classify_source_class,
    finding_candidate_id,
    finding_idempotency_key,
    is_official_domain,
    promotability_for,
)
from pci_realtime.research.openai_web import (
    OpenAIWebSearchProvider,
    findings_from_evidence_candidates,
)
from pci_realtime.research.parallel import (
    ParallelFinding,
    ParallelLaneOutput,
    ParallelProvider,
)
from pci_realtime.research.prompts import build_lane_research_prompt


__all__ = [
    "CANDIDATE_SCHEMA_VERSION",
    "RESEARCH_PROMPT_VERSION",
    "ExaProvider",
    "FallbackChain",
    "LaneBrief",
    "OpenAIWebSearchProvider",
    "ParallelFinding",
    "ParallelLaneOutput",
    "ParallelProvider",
    "RequestBudget",
    "ResearchBudgetExceeded",
    "ResearchFinding",
    "ResearchLaneResult",
    "ResearchProvider",
    "ResearchProviderError",
    "build_lane_research_prompt",
    "build_provider_chain",
    "classify_source_class",
    "finding_candidate_id",
    "finding_idempotency_key",
    "findings_from_evidence_candidates",
    "is_official_domain",
    "promotability_for",
]
