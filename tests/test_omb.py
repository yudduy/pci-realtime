from __future__ import annotations

from datetime import date
from typing import Any

from pci_realtime.config import OMB_MEMO_PAGES
from pci_realtime.ingest.omb import OmbIngestor


class FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        return None


class FakeSession:
    def __init__(self, responses: dict[str, FakeResponse]) -> None:
        self.responses = responses

    def get(self, url: str, **_: Any) -> FakeResponse:
        return self.responses[url]


def test_omb_ingestor_parses_memo_page(monkeypatch) -> None:
    index_url = "https://omb.test/memos"
    doc_url = "https://omb.test/memos/ira-lpo"
    monkeypatch.setattr("pci_realtime.ingest.omb.OMB_MEMO_PAGES", [index_url])
    monkeypatch.setattr("pci_realtime.config.OMB_MEMO_PAGES", [index_url])
    session = FakeSession(
        {
            index_url: FakeResponse(
                "<a href='/memos/ira-lpo'>Inflation Reduction Act section 50144 memo</a>"
            ),
            doc_url: FakeResponse(
                """
                <html><body>
                  <time datetime="2024-06-04"></time>
                  <h1>OMB implementation memo</h1>
                  <p>Section 50144 energy infrastructure reinvestment guidance.</p>
                </body></html>
                """
            ),
        }
    )

    df = OmbIngestor(session=session).collect_documents(
        start_date=date(2024, 6, 1),
        end_date=date(2024, 6, 10),
    )

    assert OMB_MEMO_PAGES
    assert len(df) == 1
    assert df.loc[0, "source"] == "omb"
    assert df.loc[0, "doc_id"] == "omb:memos-ira-lpo"
    assert df.loc[0, "provisions_mentioned"] == ["50144"]
