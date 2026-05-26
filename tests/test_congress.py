from __future__ import annotations

from datetime import date
from typing import Any

from pci_realtime.ingest.congress import CongressIngestor


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeSession:
    def get(self, url: str, *_: Any, **__: Any) -> FakeResponse:
        if url.endswith("/summaries"):
            return FakeResponse(
                {
                    "summaries": [
                        {
                            "actionDate": "2024-05-03",
                            "actionDesc": "Introduced in House",
                            "bill": {
                                "congress": 118,
                                "type": "HR",
                                "number": "1234",
                                "title": "Section 45V clean hydrogen fix",
                                "url": "https://api.congress.gov/v3/bill/118/hr/1234",
                            },
                            "text": "Updates section 45V clean hydrogen production credit implementation.",
                        }
                    ]
                }
            )
        if url.endswith("/text"):
            return FakeResponse(
                {
                    "textVersions": [
                        {
                            "formats": [
                                {
                                    "type": "Formatted Text",
                                    "url": "https://congress.test/bill/hr1234/text",
                                }
                            ]
                        }
                    ]
                }
            )
        return FakeResponse(
            {
                "bill": {
                    "title": "Section 45V clean hydrogen fix",
                    "latestAction": {"text": "Referred to committee"},
                    "policyArea": {"name": "Taxation"},
                    "sponsors": [{"fullName": "Rep. Example"}],
                }
            }
        )


def test_congress_ingestor_normalizes_congress_gov_summaries() -> None:
    df = CongressIngestor(api_key="test-key", session=FakeSession()).collect_documents(
        start_date=date(2024, 5, 1),
        end_date=date(2024, 5, 10),
    )

    assert len(df) == 1
    assert df.loc[0, "source"] == "congress"
    assert df.loc[0, "doc_id"] == "congress:118-hr-1234-2024-05-03"
    assert df.loc[0, "provisions_mentioned"] == ["45V"]
