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
    def get(self, *_: Any, **__: Any) -> FakeResponse:
        return FakeResponse(
            {
                "results": [
                    {
                        "bills": [
                            {
                                "bill_id": "hr1234-118",
                                "latest_major_action_date": "2024-05-03",
                                "introduced_date": "2024-04-30",
                                "short_title": "Section 45V clean hydrogen fix",
                                "title": "A bill to amend clean hydrogen rules",
                                "summary": "Updates section 45V clean hydrogen production credit implementation.",
                                "latest_major_action": "Referred to committee",
                                "congressdotgov_url": "https://congress.test/bill/hr1234",
                            }
                        ]
                    }
                ]
            }
        )


def test_congress_ingestor_normalizes_propublica_search_results() -> None:
    df = CongressIngestor(api_key="test-key", session=FakeSession()).collect_documents(
        start_date=date(2024, 5, 1),
        end_date=date(2024, 5, 10),
    )

    assert len(df) == 1
    assert df.loc[0, "source"] == "congress"
    assert df.loc[0, "doc_id"] == "congress:hr1234-118"
    assert df.loc[0, "provisions_mentioned"] == ["45V"]
