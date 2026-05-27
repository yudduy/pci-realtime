from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from pci_realtime.forecast_registry.evidence import json_value, stable_hash


DEFAULT_CHUNK_CHARS = 1800
DEFAULT_OVERLAP_CHARS = 180


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    source_doc_id: str
    chunk_index: int
    chunk_hash: str
    source: str
    title: str
    section_title: str | None
    text: str
    char_start: int
    char_end: int
    published_at: str | None
    fetched_at: str | None
    raw_public_metadata: dict[str, Any]


def chunks_from_raw_docs(
    raw_docs: dict[str, dict[str, Any]],
    *,
    max_chars: int = DEFAULT_CHUNK_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    for source_doc_id, raw in sorted(raw_docs.items()):
        body = normalize_text(raw.get("body"))
        title = normalize_text(raw.get("title"))
        full_text = "\n\n".join(part for part in [title, body] if part)
        if not full_text:
            continue
        for index, (text, start, end) in enumerate(
            split_text(full_text, max_chars=max_chars, overlap_chars=overlap_chars)
        ):
            chunk_hash = stable_hash(source_doc_id, index, text)
            chunks.append(
                DocumentChunk(
                    chunk_id=f"chunk:{source_doc_id}:{index}:{chunk_hash[:12]}",
                    source_doc_id=source_doc_id,
                    chunk_index=index,
                    chunk_hash=chunk_hash,
                    source=str(raw.get("source") or "unknown"),
                    title=title or source_doc_id,
                    section_title=infer_section_title(text),
                    text=text,
                    char_start=start,
                    char_end=end,
                    published_at=json_value(raw.get("date")),
                    fetched_at=json_value(raw.get("ingested_at")),
                    raw_public_metadata={
                        "body_truncated": bool(raw.get("body_truncated")),
                        "ingestor_version": raw.get("ingestor_version"),
                        "provisions_mentioned": raw.get("provisions_mentioned") or [],
                    },
                )
            )
    return chunks


def document_chunk_rows(chunks: list[DocumentChunk]) -> list[dict[str, Any]]:
    return [
        json_value(
            {
                "chunk_id": chunk.chunk_id,
                "source_doc_id": chunk.source_doc_id,
                "chunk_index": chunk.chunk_index,
                "chunk_hash": chunk.chunk_hash,
                "source": chunk.source,
                "title": chunk.title,
                "section_title": chunk.section_title,
                "text": chunk.text,
                "char_start": chunk.char_start,
                "char_end": chunk.char_end,
                "published_at": chunk.published_at,
                "fetched_at": chunk.fetched_at,
                "raw_public_metadata": chunk.raw_public_metadata,
            }
        )
        for chunk in chunks
    ]


def split_text(
    text: str,
    *,
    max_chars: int = DEFAULT_CHUNK_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> list[tuple[str, int, int]]:
    cleaned = normalize_text(text)
    if not cleaned:
        return []
    if len(cleaned) <= max_chars:
        return [(cleaned, 0, len(cleaned))]

    rows: list[tuple[str, int, int]] = []
    start = 0
    while start < len(cleaned):
        hard_end = min(len(cleaned), start + max_chars)
        end = soft_boundary(cleaned, start=start, hard_end=hard_end)
        chunk = cleaned[start:end].strip()
        if chunk:
            rows.append((chunk, start, end))
        if end >= len(cleaned):
            break
        start = max(end - overlap_chars, start + 1)
    return rows


def soft_boundary(text: str, *, start: int, hard_end: int) -> int:
    if hard_end >= len(text):
        return len(text)
    window = text[start:hard_end]
    for pattern in ("\n\n", ". ", "; "):
        index = window.rfind(pattern)
        if index >= max(200, len(window) // 2):
            return start + index + len(pattern)
    return hard_end


def infer_section_title(text: str) -> str | None:
    first_line = text.strip().splitlines()[0] if text.strip() else ""
    if 0 < len(first_line) <= 120 and not first_line.endswith("."):
        return first_line
    return None


def normalize_text(value: Any) -> str:
    return re.sub(r"[ \t]+", " ", str(value or "").replace("\r\n", "\n")).strip()
