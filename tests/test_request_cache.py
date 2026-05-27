from __future__ import annotations

from pathlib import Path
from typing import Any

import requests

from pci_realtime.ingest.request_cache import (
    CachedSession,
    build_request_record,
)


def _response(text: str, headers: dict[str, str] | None = None) -> requests.Response:
    response = requests.Response()
    response.status_code = 200
    response._content = text.encode("utf-8")
    response.headers.update(headers or {})
    response.url = "https://api.example.test/data"
    response.encoding = "utf-8"
    return response


def test_request_record_redacts_secret_params_and_headers() -> None:
    record = build_request_record(
        method="GET",
        source="eia",
        url="https://api.example.test/data?api_key=secret&q=45V",
        params={"token": "also-secret", "series_id": "DGS10"},
        headers={"Authorization": "Token secret", "User-Agent": "pci-test"},
    )

    assert record["sanitized_params"]["api_key"] == "<redacted>"
    assert record["sanitized_params"]["token"] == "<redacted>"
    assert record["request_headers"]["Authorization"] == "<redacted>"
    assert record["request_headers"]["User-Agent"] == "pci-test"
    assert "secret" not in repr(record)


def test_cached_session_reuses_local_response_and_captures_rate_limits(
    tmp_path: Path, monkeypatch
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_request(
        self: requests.Session,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> requests.Response:
        del self, method, url
        calls.append(kwargs)
        return _response(
            '{"ok": true}',
            headers={
                "x-ratelimit-limit": "100",
                "x-ratelimit-remaining": "99",
            },
        )

    monkeypatch.setattr(requests.Session, "request", fake_request)
    session = CachedSession(source="eia", cache_root=tmp_path)

    first = session.get("https://api.example.test/data", params={"api_key": "one"})
    second = session.get("https://api.example.test/data", params={"api_key": "two"})

    assert first.json() == {"ok": True}
    assert second.json() == {"ok": True}
    assert len(calls) == 1
    assert session.stats.requests == 2
    assert session.stats.cache_hits == 1
    assert session.stats.cache_misses == 1
    assert session.stats.rate_limit_headers["x-ratelimit-limit"] == "100"


def test_supabase_cache_persistence_is_best_effort(tmp_path: Path, monkeypatch) -> None:
    class FailingClient:
        def upsert_rows(self, *args: Any, **kwargs: Any) -> None:
            del args, kwargs
            raise RuntimeError("migration not applied")

    def fake_request(
        self: requests.Session,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> requests.Response:
        del self, method, url, kwargs
        return _response('{"ok": true}')

    monkeypatch.setattr(requests.Session, "request", fake_request)
    session = CachedSession(
        source="eia",
        cache_root=tmp_path,
        supabase_client=FailingClient(),  # type: ignore[arg-type]
    )

    response = session.get("https://api.example.test/data")

    assert response.json() == {"ok": True}
    assert session.stats.network_requests == 1
