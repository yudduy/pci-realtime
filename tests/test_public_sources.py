from __future__ import annotations

from datetime import date
from typing import Any

from pci_realtime.forecast_registry.polymarket import parse_polymarket_snapshot
from pci_realtime.ingest.public_sources import (
    CourtListenerClient,
    EIAClient,
    FREDClient,
    GovInfoClient,
    RegInfoClient,
    RegulationsGovIngestor,
    USASpendingIngestor,
)


class FakeResponse:
    def __init__(self, payload: Any, *, content: bytes | None = None) -> None:
        self._payload = payload
        self.content = content if content is not None else b""

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self._payload


class FakeSourceSession:
    def get(self, url: str, *_: Any, **__: Any) -> FakeResponse:
        if "/documents" in url:
            return FakeResponse(
                {
                    "data": [
                        {
                            "id": "IRS-2024-0001-0001",
                            "attributes": {
                                "postedDate": "2024-05-03T00:00:00Z",
                                "agencyId": "IRS",
                                "title": "Credit for Production of Clean Hydrogen",
                                "documentType": "Rule",
                                "subtype": "Final Rule",
                                "docketId": "IRS-2024-0001",
                            },
                        }
                    ]
                }
            )
        if "XMLViewFileAction" in url:
            return FakeResponse(
                {},
                content=b"""
                <OIRA_DATA><REGACT>
                  <RIN>1505-AC82</RIN>
                  <TITLE>Clean hydrogen production credit review</TITLE>
                  <STAGE>Final Rule</STAGE>
                  <DATE_RECEIVED>2024-05-03</DATE_RECEIVED>
                </REGACT></OIRA_DATA>
                """,
            )
        if "electricity" in url:
            return FakeResponse(
                {
                    "response": {
                        "data": [
                            {
                                "period": "2026-03",
                                "price": "14.18",
                                "price-units": "cents per kilowatt-hour",
                            }
                        ]
                    }
                }
            )
        if "series/observations" in url:
            return FakeResponse(
                {"observations": [{"date": "2026-05-01", "value": "4.25"}]}
            )
        if "courtlistener" in url:
            return FakeResponse(
                {
                    "results": [
                        {
                            "cluster_id": 123,
                            "caseName": "IRA Tax Credit Challenge",
                            "absolute_url": "/opinion/123/test/",
                            "snippet": "Challenge to Inflation Reduction Act tax credit guidance.",
                            "dateFiled": "2026-05-01",
                        }
                    ]
                }
            )
        if "/collections/" in url:
            return FakeResponse({"packages": [{"packageId": "BILLS-118hr1ih"}]})
        return FakeResponse({"title": "Package summary"})

    def post(self, *_: Any, **__: Any) -> FakeResponse:
        return FakeResponse(
            {
                "results": [
                    {
                        "Award ID": "DE-1",
                        "Recipient Name": "Hydrogen Builder",
                        "Award Amount": 1000,
                        "Awarding Agency": "Department of Energy",
                        "Start Date": "2024-05-04",
                        "Description": "Section 45V clean hydrogen support.",
                    }
                ]
            }
        )


def test_regulations_gov_ingestor_normalizes_documents() -> None:
    df = RegulationsGovIngestor(
        api_key="test", session=FakeSourceSession()
    ).collect_documents(start_date=date(2024, 5, 1), end_date=date(2024, 5, 10))

    assert len(df) == 1
    assert df.loc[0, "source"] == "regulations_gov"
    assert df.loc[0, "provisions_mentioned"] == ["45V"]


def test_reginfo_ingestor_normalizes_oira_xml() -> None:
    rows = RegInfoClient(session=FakeSourceSession()).xml_report("test.xml")

    assert rows[0]["RIN"] == "1505-AC82"


def test_usaspending_ingestor_normalizes_awards() -> None:
    df = USASpendingIngestor(session=FakeSourceSession()).collect_documents(
        start_date=date(2024, 5, 1), end_date=date(2024, 5, 10)
    )

    assert len(df) == 1
    assert df.loc[0, "source"] == "usaspending"
    assert df.loc[0, "provisions_mentioned"] == ["45V"]


def test_scaffolded_public_clients_parse_core_shapes() -> None:
    session = FakeSourceSession()

    assert GovInfoClient(api_key="test", session=session).collection_packages(
        collection="BILLS", start_date_time="2026-05-01T00:00:00Z"
    )["packages"][0]["packageId"]
    assert EIAClient(api_key="test", session=session).latest_electricity_price()[
        "price"
    ]
    assert FREDClient(api_key="test", session=session).observations(series_id="DGS10")
    assert CourtListenerClient(session=session).search(query="IRA")


def test_polymarket_snapshot_is_display_only_market_data() -> None:
    snapshot = parse_polymarket_snapshot(
        {
            "id": "1",
            "slug": "tax-credit-market",
            "question": "Will Congress change a clean energy tax credit?",
            "description": "Resolves on official federal action.",
            "active": True,
            "outcomePrices": '["0.42","0.58"]',
            "liquidity": "1000",
            "volume": "500",
        }
    )

    assert snapshot["venue"] == "polymarket"
    assert snapshot["policy_relevant"] is True
    assert snapshot["market_probability"] == 0.42


def test_fred_client_disables_without_key(monkeypatch) -> None:
    monkeypatch.delenv("FRED_API_KEY", raising=False)

    assert FREDClient(session=FakeSourceSession()).observations(series_id="DGS10") == []
