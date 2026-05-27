from __future__ import annotations

import pandas as pd

from pci_realtime.retrieval.chunks import chunks_from_raw_docs
from pci_realtime.retrieval.queries import load_provision_query_packs
from pci_realtime.retrieval.search import retrieve_for_provision
from pci_realtime.scoring.extraction import ShadowEvidenceExtractor


def test_chunks_are_stable_and_retrieval_finds_45v_query() -> None:
    raw_docs = {
        "federal_register:45v": {
            "source": "federal_register",
            "title": "Clean hydrogen production credit guidance",
            "body": (
                "Treasury issued final rules for the section 45V clean hydrogen "
                "production credit. The guidance defines lifecycle greenhouse gas "
                "emissions and eligibility documentation."
            ),
            "date": "2026-01-02",
            "ingested_at": pd.Timestamp("2026-01-02T00:00:00Z"),
            "body_truncated": False,
            "ingestor_version": "test",
            "provisions_mentioned": ["45V"],
        },
        "federal_register:other": {
            "source": "federal_register",
            "title": "Unrelated notice",
            "body": "This notice concerns a procedural filing deadline.",
            "date": "2026-01-02",
            "ingested_at": pd.Timestamp("2026-01-02T00:00:00Z"),
            "body_truncated": False,
            "ingestor_version": "test",
            "provisions_mentioned": [],
        },
    }

    chunks = chunks_from_raw_docs(raw_docs)
    again = chunks_from_raw_docs(raw_docs)
    packs = load_provision_query_packs()
    results = retrieve_for_provision(chunks, packs["45V"], top_k=3)

    assert [chunk.chunk_hash for chunk in chunks] == [
        chunk.chunk_hash for chunk in again
    ]
    assert results[0].chunk.source_doc_id == "federal_register:45v"
    assert "clean hydrogen production credit" in results[0].matched_terms


def test_shadow_extraction_writes_chunk_metadata(tmp_path) -> None:
    raw_docs = {
        "federal_register:30d": {
            "source": "federal_register",
            "title": "Clean vehicle credit notice",
            "body": (
                "The IRS notice describes section 30D clean vehicle credit seller "
                "reporting and foreign entity of concern requirements."
            ),
            "date": "2026-02-01",
            "ingested_at": pd.Timestamp("2026-02-01T00:00:00Z"),
            "body_truncated": False,
            "ingestor_version": "test",
            "provisions_mentioned": ["30D"],
        }
    }
    chunks = chunks_from_raw_docs(raw_docs)
    packs = load_provision_query_packs()
    results = {"30D": retrieve_for_provision(chunks, packs["30D"], top_k=1)}
    extractor = ShadowEvidenceExtractor(cache_root=tmp_path)

    extraction = extractor.extract(results, top_k=1)

    assert extraction.rows
    row = extraction.rows[0]
    assert "section 30D clean vehicle credit" in row["snippet"]
    assert row["raw_public_metadata"]["chunk_id"].startswith("chunk:")
    assert row["raw_public_metadata"]["retrieval_rank"] == 1
