from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit, urlunsplit

import requests

from pci_realtime.config import CACHE_ROOT, REQUEST_TIMEOUT_SECONDS
from pci_realtime.forecast_registry.store import SupabaseRestClient, json_clean


SECRET_KEYS = {
    "api_key",
    "apikey",
    "key",
    "token",
    "access_token",
    "authorization",
    "x-api-key",
}
RATE_LIMIT_HEADERS = {
    "x-ratelimit-limit",
    "x-ratelimit-remaining",
    "x-ratelimit-reset",
    "ratelimit-limit",
    "ratelimit-remaining",
    "ratelimit-reset",
    "retry-after",
}
DEFAULT_TTL_SECONDS = 24 * 60 * 60
LOGGER = logging.getLogger(__name__)


@dataclass
class RequestCacheStats:
    requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    network_requests: int = 0
    rate_limited: int = 0
    total_latency_ms: int = 0
    rate_limit_headers: dict[str, str] = field(default_factory=dict)

    @property
    def hit_rate(self) -> float:
        if self.requests == 0:
            return 0.0
        return round(self.cache_hits / self.requests, 4)

    def to_metadata(self) -> dict[str, Any]:
        return {
            "requests": self.requests,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "network_requests": self.network_requests,
            "cache_hit_rate": self.hit_rate,
            "rate_limited": self.rate_limited,
            "total_latency_ms": self.total_latency_ms,
            "rate_limit_headers": dict(self.rate_limit_headers),
        }


class CachedSession(requests.Session):
    """requests.Session with an audit-friendly local response cache."""

    def __init__(
        self,
        *,
        source: str,
        cache_root: Path = CACHE_ROOT / "source_requests",
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        supabase_client: SupabaseRestClient | None = None,
    ) -> None:
        super().__init__()
        self.source = source
        self.cache_root = cache_root
        self.ttl_seconds = ttl_seconds
        self.supabase_client = supabase_client
        self.stats = RequestCacheStats()

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        self.stats.requests += 1
        timeout = kwargs.pop("timeout", REQUEST_TIMEOUT_SECONDS)
        request_record = build_request_record(
            method=method,
            url=url,
            source=self.source,
            params=kwargs.get("params"),
            data=kwargs.get("data"),
            json_body=kwargs.get("json"),
            headers={**self.headers, **dict(kwargs.get("headers") or {})},
            ttl_seconds=self.ttl_seconds,
        )
        path = self._path_for_key(request_record["request_key"])
        cached = self._read_cached_response(path)
        if cached is not None:
            self.stats.cache_hits += 1
            return response_from_cache(cached, request_record)

        self.stats.cache_misses += 1
        started = time.monotonic()
        response = super().request(method, url, timeout=timeout, **kwargs)
        latency_ms = int((time.monotonic() - started) * 1000)
        self.stats.network_requests += 1
        self.stats.total_latency_ms += latency_ms
        if response.status_code == 429:
            self.stats.rate_limited += 1
        rate_headers = extract_rate_limit_headers(response.headers)
        if rate_headers:
            self.stats.rate_limit_headers.update(rate_headers)

        cache_record = {
            **request_record,
            "status_code": response.status_code,
            "response_headers": sanitize_mapping(dict(response.headers)),
            "rate_limit_headers": rate_headers,
            "response_hash": stable_hash(response.text),
            "response_body": response.text,
            "latency_ms": latency_ms,
            "cache_hit": False,
            "raw_public_metadata": {
                "reason": "network_fetch",
                "encoding": response.encoding,
            },
        }
        self._write_cache_record(path, cache_record)
        self._persist_supabase(cache_record)
        return response

    def _path_for_key(self, key: str) -> Path:
        return self.cache_root / f"{key}.json"

    def _read_cached_response(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as handle:
            record = json.load(handle)
        expires_at = record.get("expires_at")
        if expires_at and datetime.fromisoformat(str(expires_at)) < datetime.now(
            timezone.utc
        ):
            return None
        return dict(record)

    def _write_cache_record(self, path: Path, record: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(json_clean(record), handle, indent=2, sort_keys=True)
            handle.write("\n")
        tmp_path.replace(path)

    def _persist_supabase(self, record: dict[str, Any]) -> None:
        if self.supabase_client is None:
            return
        try:
            self.supabase_client.upsert_rows(
                "source_request_cache",
                [record],
                on_conflict="request_key",
            )
        except Exception as exc:  # pragma: no cover - defensive external boundary
            LOGGER.debug("source_request_cache persistence skipped: %s", exc)


def build_request_record(
    *,
    method: str,
    url: str,
    source: str,
    params: Any = None,
    data: Any = None,
    json_body: Any = None,
    headers: dict[str, Any] | None = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> dict[str, Any]:
    sanitized_params = sanitize_params(url, params)
    sanitized_body = sanitize_body(json_body if json_body is not None else data)
    sanitized_url = strip_query(url)
    fetched_at = datetime.now(timezone.utc)
    expires_at = fetched_at + timedelta(seconds=ttl_seconds)
    request_key = stable_hash(
        source,
        method.upper(),
        sanitized_url,
        canonical_json(sanitized_params),
        canonical_json(sanitized_body),
    )
    return {
        "request_key": request_key,
        "source": source,
        "method": method.upper(),
        "url": sanitized_url,
        "sanitized_params": sanitized_params,
        "sanitized_body_hash": stable_hash(canonical_json(sanitized_body)),
        "request_headers": sanitize_mapping(headers or {}),
        "fetched_at": fetched_at.isoformat(),
        "expires_at": expires_at.isoformat(),
    }


def response_from_cache(
    record: dict[str, Any], request_record: dict[str, Any]
) -> requests.Response:
    response = requests.Response()
    response.status_code = int(record.get("status_code") or 200)
    response._content = str(record.get("response_body") or "").encode("utf-8")
    response.headers.update(
        {
            str(key): str(value)
            for key, value in dict(record.get("response_headers") or {}).items()
        }
    )
    response.url = str(request_record["url"])
    response.encoding = "utf-8"
    return response


def sanitize_params(url: str, params: Any = None) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for key, value in parse_qsl(urlsplit(url).query, keep_blank_values=True):
        merged[key] = value
    if isinstance(params, dict):
        merged.update(params)
    elif params:
        for key, value in parse_qsl(str(params), keep_blank_values=True):
            merged[key] = value
    return sanitize_mapping(merged)


def sanitize_body(value: Any) -> Any:
    if isinstance(value, dict):
        return sanitize_mapping(value)
    if isinstance(value, list):
        return [sanitize_body(item) for item in value]
    if value is None:
        return {}
    return "<body-present>"


def sanitize_mapping(mapping: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in sorted(mapping.items(), key=lambda item: str(item[0])):
        key_text = str(key)
        if key_text.lower() in SECRET_KEYS:
            sanitized[key_text] = "<redacted>"
        elif isinstance(value, dict):
            sanitized[key_text] = sanitize_mapping(value)
        elif isinstance(value, list):
            sanitized[key_text] = [sanitize_body(item) for item in value]
        else:
            sanitized[key_text] = str(value)
    return sanitized


def extract_rate_limit_headers(headers: dict[str, Any]) -> dict[str, str]:
    rows = {}
    for key, value in headers.items():
        lowered = str(key).lower()
        if lowered in RATE_LIMIT_HEADERS:
            rows[lowered] = str(value)
    return rows


def strip_query(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def stable_hash(*parts: Any) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(str(part or "").encode("utf-8", errors="ignore"))
        digest.update(b"\x00")
    return digest.hexdigest()
