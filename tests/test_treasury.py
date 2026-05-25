from __future__ import annotations

from datetime import date
from typing import Any

from pci_realtime.config import TREASURY_GUIDANCE_PAGES
from pci_realtime.ingest.treasury import TreasuryIngestor, extract_page_date


class FakeResponse:
    def __init__(self, text: str = "", payload: dict[str, Any] | None = None) -> None:
        self.text = text
        self._payload = payload or {}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeSession:
    def __init__(self, responses: dict[str, FakeResponse]) -> None:
        self.responses = responses

    def get(self, url: str, **_: Any) -> FakeResponse:
        return self.responses[url]


def test_treasury_ingestor_parses_guidance_page(monkeypatch) -> None:
    index_url = "https://treasury.test/index"
    doc_url = "https://treasury.test/guidance/45x"
    monkeypatch.setitem(TREASURY_GUIDANCE_PAGES, "treasury", [index_url])
    session = FakeSession(
        {
            index_url: FakeResponse(
                "<a href='/guidance/45x'>Inflation Reduction Act section 45X</a>"
            ),
            doc_url: FakeResponse(
                """
                <html><head><title>45X notice</title></head>
                <body>
                  <time datetime="2024-05-03"></time>
                  <h1>Advanced manufacturing production credit guidance</h1>
                  <p>Section 45X guidance under the Inflation Reduction Act.</p>
                </body></html>
                """
            ),
        }
    )

    df = TreasuryIngestor(session=session).collect_documents(
        start_date=date(2024, 5, 1),
        end_date=date(2024, 5, 10),
    )

    assert len(df) == 1
    assert df.loc[0, "source"] == "treasury"
    assert df.loc[0, "doc_id"] == "treasury:guidance-45x"
    assert df.loc[0, "provisions_mentioned"] == ["45X"]


def test_extract_page_date_ignores_invalid_candidate_dates() -> None:
    assert extract_page_date(
        """
            <html><body>
              <p>Archive marker 2023-04-00 should not crash parsing.</p>
              <p>Updated May 3, 2024.</p>
            </body></html>
            """
    ) == date(2024, 5, 3)
