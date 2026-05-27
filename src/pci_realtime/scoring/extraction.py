from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pci_realtime.config import CACHE_ROOT, LLM_SCREENING_MODEL, LLM_SCREENING_PROVIDER
from pci_realtime.forecast_registry.evidence import excerpt, json_value
from pci_realtime.retrieval.search import RetrievalResult
from pci_realtime.scoring.cache import (
    JsonCache,
    StructuredLLMResponse,
    build_cache_key,
)


EVIDENCE_EXTRACTION_VERSION = "evidence-extraction-v1.0.0"
EVIDENCE_EXTRACTION_PROMPT_VERSION = "evidence-extraction-prompt-v1"
EVIDENCE_EXTRACTION_SCHEMA_VERSION = "evidence-extraction-schema-v1"


@dataclass(frozen=True)
class EvidenceExtractionResult:
    rows: list[dict[str, Any]]
    metrics: dict[str, Any]


class ShadowEvidenceExtractor:
    """Deterministic exact-span extractor for retrieved audit chunks."""

    def __init__(
        self,
        *,
        cache: JsonCache | None = None,
        cache_root: Path = CACHE_ROOT / "evidence_extraction",
        provider: str = LLM_SCREENING_PROVIDER,
        model: str = LLM_SCREENING_MODEL,
        extractor_version: str = EVIDENCE_EXTRACTION_VERSION,
    ) -> None:
        self.cache = cache or JsonCache(cache_root)
        self.provider = provider
        self.model = model
        self.extractor_version = extractor_version

    def extract(
        self,
        retrieval_results: dict[str, list[RetrievalResult]],
        *,
        top_k: int = 10,
    ) -> EvidenceExtractionResult:
        rows: list[dict[str, Any]] = []
        no_evidence_count = 0
        cache_hits = 0
        calls = 0
        by_provision: dict[str, dict[str, int]] = {}
        for provision, results in sorted(retrieval_results.items()):
            by_provision[provision] = {"retrieved": len(results), "extracted": 0}
            for result in results[:top_k]:
                calls += 1
                payload, cached = self.extract_one(result)
                if cached:
                    cache_hits += 1
                if not payload.get("has_evidence"):
                    no_evidence_count += 1
                    continue
                rows.append(self.row_from_payload(result, payload))
                by_provision[provision]["extracted"] += 1
        return EvidenceExtractionResult(
            rows=rows,
            metrics={
                "extractor_version": self.extractor_version,
                "calls": calls,
                "cache_hits": cache_hits,
                "cache_hit_rate": round(cache_hits / calls, 4) if calls else 0.0,
                "extracted_evidence_count": len(rows),
                "no_evidence_count": no_evidence_count,
                "by_provision": by_provision,
            },
        )

    def extract_one(self, result: RetrievalResult) -> tuple[dict[str, Any], bool]:
        input_payload = {
            "chunk_hash": result.chunk.chunk_hash,
            "chunk_id": result.chunk.chunk_id,
            "provision": result.provision,
            "matched_terms": result.matched_terms,
            "text": result.chunk.text,
        }
        cache_key = build_cache_key(
            provider=self.provider,
            model=self.model,
            prompt_version=EVIDENCE_EXTRACTION_PROMPT_VERSION,
            temperature=0.0,
            schema_version=EVIDENCE_EXTRACTION_SCHEMA_VERSION,
            stage="evidence_extraction",
            input_payload=input_payload,
        )
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached.payload, True

        payload = deterministic_payload(result)
        self.cache.set(
            cache_key,
            StructuredLLMResponse(
                payload=payload,
                raw_response="",
                usage={},
                cost_usd=0.0,
            ),
        )
        return payload, False

    def row_from_payload(
        self, result: RetrievalResult, payload: dict[str, Any]
    ) -> dict[str, Any]:
        quote = str(payload.get("quote") or "")
        chunk = result.chunk
        return json_value(
            {
                "evidence_id": (
                    f"evidence:chunk:{result.provision}:"
                    f"{chunk.chunk_hash[:16]}:{result.rank}"
                ),
                "source_doc_id": chunk.source_doc_id,
                "provision": result.provision,
                "evidence_type": payload.get("evidence_type")
                or "retrieved_policy_evidence",
                "snippet": excerpt(quote),
                "normalized_signal": "retrieved evidence",
                "score_dimension": "evidence_retrieval",
                "confidence": payload.get("confidence"),
                "extractor_version": self.extractor_version,
                "raw_public_metadata": {
                    "chunk_id": chunk.chunk_id,
                    "chunk_hash": chunk.chunk_hash,
                    "chunk_index": chunk.chunk_index,
                    "retrieval_rank": result.rank,
                    "retrieval_score": result.score,
                    "matched_terms": list(result.matched_terms),
                    "section_title": chunk.section_title,
                    "extractor_mode": "deterministic_exact_span",
                },
            }
        )


def deterministic_payload(result: RetrievalResult) -> dict[str, Any]:
    quote = quote_from_chunk(result.chunk.text, result.matched_terms)
    if not quote:
        return {
            "has_evidence": False,
            "quote": "",
            "evidence_type": "no_evidence",
            "confidence": 0.0,
            "no_evidence_reason": "no_exact_query_span",
        }
    return {
        "has_evidence": True,
        "quote": quote,
        "evidence_type": "retrieved_policy_evidence",
        "confidence": min(0.95, round(0.55 + min(result.score, 20.0) / 100, 4)),
        "no_evidence_reason": "",
    }


def quote_from_chunk(text: str, matched_terms: tuple[str, ...]) -> str:
    if not matched_terms:
        return ""
    sentences = split_sentences(text)
    lowered_terms = [term.lower() for term in matched_terms if term]
    for sentence in sentences:
        lowered = sentence.lower()
        if any(term in lowered for term in lowered_terms):
            return sentence
    return ""


def split_sentences(text: str) -> list[str]:
    normalized = " ".join(str(text or "").split())
    if not normalized:
        return []
    rows: list[str] = []
    start = 0
    for index, char in enumerate(normalized):
        if (
            char in ".!?"
            and index + 1 < len(normalized)
            and normalized[index + 1] == " "
        ):
            sentence = normalized[start : index + 1].strip()
            if sentence:
                rows.append(sentence)
            start = index + 2
    tail = normalized[start:].strip()
    if tail:
        rows.append(tail)
    return rows or [normalized]
