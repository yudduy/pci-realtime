from __future__ import annotations

from datetime import date

import pandas as pd

from pci_realtime.ingest.base import BaseIngestor, SCHEMA_A_COLUMNS


class DummyIngestor(BaseIngestor):
    source = "treasury"
    agency = "Dummy agency"


def test_base_ingestor_builds_and_enforces_schema_a() -> None:
    ingestor = DummyIngestor(ingested_at=pd.Timestamp("2026-05-07", tz="UTC"))
    row = ingestor.build_record(
        source="treasury",
        native_id="notice-1",
        date_value="2024-05-03",
        agency="Treasury",
        title="Section 45X guidance",
        body="x" * 50_001,
        url="https://example.test/notice-1",
        provisions_mentioned=["45X", "45X"],
    )

    df = ingestor.enforce_schema([row])

    assert list(df.columns) == SCHEMA_A_COLUMNS
    assert df.loc[0, "doc_id"] == "treasury:notice-1"
    assert df.loc[0, "date"] == date(2024, 5, 3)
    assert bool(df.loc[0, "body_truncated"]) is True
    assert len(df.loc[0, "body"]) == 50_000
    assert df.loc[0, "provisions_mentioned"] == ["45X"]
