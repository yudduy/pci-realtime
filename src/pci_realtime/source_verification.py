from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import httpx

from pci_realtime.forecast_registry.evidence import excerpt, stable_hash
from pci_realtime.forecast_registry.engine import utc_now_iso


@dataclass(frozen=True)
class SourceVerification:
    status: str
    quote_verified_against_source: bool
    retrieved_at: str | None
    retrieval_method: str
    source_content_hash: str | None
    quote_hash: str
    quote_locator_type: str | None
    quote_locator_value: str | None
    source_text_excerpt: str | None = None
    error_class: str | None = None
    error_summary: str | None = None

    def to_row(self) -> dict[str, Any]:
        return {
            "verification_status": self.status,
            "quote_verified_against_source": self.quote_verified_against_source,
            "source_retrieved_at": self.retrieved_at,
            "source_retrieval_method": self.retrieval_method,
            "source_content_hash": self.source_content_hash,
            "quote_hash": self.quote_hash,
            "quote_locator_type": self.quote_locator_type,
            "quote_locator_value": self.quote_locator_value,
            "source_text_excerpt": self.source_text_excerpt,
            "error_class": self.error_class,
            "error_summary": self.error_summary,
        }


HttpGet = Callable[..., httpx.Response]


def verify_quote_against_source(
    *,
    url: str,
    quote: str,
    source_text: str | None = None,
    http_get: HttpGet | None = None,
    timeout: float = 30.0,
) -> SourceVerification:
    quote_hash = quote_verification_hash(quote)
    if source_text is not None:
        return verification_from_text(
            quote=quote,
            text=source_text,
            quote_hash=quote_hash,
            retrieval_method="provided_text",
        )

    try:
        getter = http_get or httpx.get
        response = getter(url, timeout=timeout, follow_redirects=True)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001 - callers persist or expose status.
        return SourceVerification(
            status="unverified",
            quote_verified_against_source=False,
            retrieved_at=utc_now_iso(),
            retrieval_method="http_get",
            source_content_hash=None,
            quote_hash=quote_hash,
            quote_locator_type=None,
            quote_locator_value=None,
            error_class=type(exc).__name__,
            error_summary=str(exc),
        )
    return verification_from_text(
        quote=quote,
        text=response.text,
        quote_hash=quote_hash,
        retrieval_method="http_get",
    )


def verification_from_text(
    *,
    quote: str,
    text: str,
    quote_hash: str | None = None,
    retrieval_method: str = "provided_text",
) -> SourceVerification:
    normalized_quote = _normalize_text(quote)
    normalized_text = _normalize_text(text)
    offset = normalized_text.find(normalized_quote) if normalized_quote else -1
    verified = offset >= 0
    return SourceVerification(
        status="verified" if verified else "unverified",
        quote_verified_against_source=verified,
        retrieved_at=utc_now_iso(),
        retrieval_method=retrieval_method,
        source_content_hash=stable_hash("source-text", normalized_text),
        quote_hash=quote_hash or quote_verification_hash(quote),
        quote_locator_type="text_match" if verified else "not_found",
        quote_locator_value=f"normalized_offset:{offset}" if verified else None,
        source_text_excerpt=excerpt(text, max_chars=900),
    )


def override_source_verification(
    *,
    quote: str,
    reason: str,
) -> SourceVerification:
    return SourceVerification(
        status="override",
        quote_verified_against_source=False,
        retrieved_at=utc_now_iso(),
        retrieval_method="operator_override",
        source_content_hash=None,
        quote_hash=quote_verification_hash(quote),
        quote_locator_type="operator_override",
        quote_locator_value=reason,
    )


def quote_verification_hash(quote: str) -> str:
    return stable_hash("citation-quote", _normalize_text(quote))


def _normalize_text(value: str) -> str:
    return " ".join(str(value or "").split()).casefold()
