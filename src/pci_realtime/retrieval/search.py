from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable

from pci_realtime.retrieval.chunks import DocumentChunk
from pci_realtime.retrieval.queries import ProvisionQueryPack


TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class RetrievalResult:
    provision: str
    chunk: DocumentChunk
    score: float
    matched_terms: tuple[str, ...]
    rank: int


def retrieve_for_provision(
    chunks: list[DocumentChunk],
    query_pack: ProvisionQueryPack,
    *,
    top_k: int = 20,
) -> list[RetrievalResult]:
    if not chunks:
        return []
    query_terms = tuple(term.lower() for term in query_pack.all_terms)
    query_tokens = tokenize(" ".join(query_terms))
    docs_tokens = [tokenize(chunk.text) for chunk in chunks]
    doc_freq = document_frequency(docs_tokens)
    avg_len = sum(len(tokens) for tokens in docs_tokens) / max(len(docs_tokens), 1)

    rows: list[RetrievalResult] = []
    for chunk, tokens in zip(chunks, docs_tokens, strict=True):
        text = chunk.text.lower()
        matched_terms = tuple(term for term in query_terms if term and term in text)
        score = bm25_score(tokens, query_tokens, doc_freq, len(chunks), avg_len)
        score += 6.0 * len(matched_terms)
        if query_pack.provision.lower() in text:
            score += 4.0
        if score <= 0:
            continue
        rows.append(
            RetrievalResult(
                provision=query_pack.provision,
                chunk=chunk,
                score=round(score, 6),
                matched_terms=matched_terms,
                rank=0,
            )
        )

    ranked = sorted(
        rows,
        key=lambda row: (-row.score, row.chunk.source_doc_id, row.chunk.chunk_index),
    )[:top_k]
    return [
        RetrievalResult(
            provision=row.provision,
            chunk=row.chunk,
            score=row.score,
            matched_terms=row.matched_terms,
            rank=index,
        )
        for index, row in enumerate(ranked, start=1)
    ]


def retrieve_for_provisions(
    chunks: list[DocumentChunk],
    query_packs: dict[str, ProvisionQueryPack],
    *,
    top_k: int = 20,
) -> dict[str, list[RetrievalResult]]:
    return {
        provision: retrieve_for_provision(chunks, pack, top_k=top_k)
        for provision, pack in sorted(query_packs.items())
    }


def bm25_score(
    document_tokens: list[str],
    query_tokens: Iterable[str],
    doc_freq: dict[str, int],
    n_docs: int,
    avg_doc_len: float,
) -> float:
    if not document_tokens:
        return 0.0
    counts: dict[str, int] = {}
    for token in document_tokens:
        counts[token] = counts.get(token, 0) + 1
    score = 0.0
    k1 = 1.5
    b = 0.75
    doc_len = len(document_tokens)
    for token in set(query_tokens):
        freq = counts.get(token, 0)
        if not freq:
            continue
        df = doc_freq.get(token, 0)
        idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
        denom = freq + k1 * (1 - b + b * doc_len / max(avg_doc_len, 1))
        score += idf * (freq * (k1 + 1)) / denom
    return score


def document_frequency(docs_tokens: list[list[str]]) -> dict[str, int]:
    freq: dict[str, int] = {}
    for tokens in docs_tokens:
        for token in set(tokens):
            freq[token] = freq.get(token, 0) + 1
    return freq


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())
