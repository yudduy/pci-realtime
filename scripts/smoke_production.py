from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://pcindex.vercel.app"
CORE_SOURCES = {"federal_register", "congress", "regulations_gov", "reginfo"}


def fetch_text(url: str, *, headers: dict[str, str] | None = None) -> str:
    request = Request(url, headers=headers or {})
    try:
        with urlopen(request, timeout=30) as response:
            status = response.getcode()
            body = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{url} returned HTTP {exc.code}: {body[:300]}") from exc
    except URLError as exc:
        raise RuntimeError(f"{url} request failed: {exc}") from exc
    if status >= 400:
        raise RuntimeError(f"{url} returned HTTP {status}: {body[:300]}")
    return body


def fetch_json(url: str, key: str, view: str, query: dict[str, str]) -> list[dict[str, Any]]:
    rest_url = f"{url.rstrip('/')}/rest/v1/{view}?{urlencode(query)}"
    text = fetch_text(
        rest_url,
        headers={
            "apikey": key,
            "authorization": f"Bearer {key}",
        },
    )
    payload = json.loads(text)
    if not isinstance(payload, list):
        raise RuntimeError(f"{view} returned non-list payload")
    return [row for row in payload if isinstance(row, dict)]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def check_pages(base_url: str) -> None:
    expectations = {
        "/": ["Live odds for climate policy credibility.", "Live policy data"],
        "/dashboard": ["IRA credibility markets", "Policy Market Tracker"],
        "/about": ["Industrial policy reshapes venture capital", "BibTeX"],
    }
    for path, terms in expectations.items():
        html = fetch_text(f"{base_url.rstrip('/')}{path}")
        for term in terms:
            require(term in html, f"{path} missing expected text: {term}")
        require("supabase" not in html.lower(), f"{path} leaks implementation name")
        print(f"page ok: {path}")


def check_supabase(url: str, key: str, *, max_stale_hours: float) -> None:
    current_pci = fetch_json(url, key, "v_current_pci", {"select": "*", "order": "code.asc"})
    require(len(current_pci) >= 6, f"v_current_pci has {len(current_pci)} rows, expected >= 6")

    runs = fetch_json(url, key, "v_pipeline_status", {"select": "*", "limit": "1"})
    require(runs, "v_pipeline_status returned no rows")
    latest = runs[0]
    require(latest.get("status") == "success", f"latest pipeline is not successful: {latest}")

    completed_at = parse_timestamp(latest.get("completed_at") or latest.get("started_at"))
    require(completed_at is not None, "latest pipeline timestamp is missing or invalid")
    age_hours = (datetime.now(timezone.utc) - completed_at).total_seconds() / 3600
    require(
        age_hours <= max_stale_hours,
        f"latest pipeline is stale: {age_hours:.1f}h > {max_stale_hours:.1f}h",
    )

    source_health = fetch_json(url, key, "v_source_health", {"select": "*"})
    failed_core = [
        row
        for row in source_health
        if row.get("source") in CORE_SOURCES and row.get("status") == "failed"
    ]
    require(not failed_core, f"core source failures: {failed_core}")
    print(
        "supabase ok: "
        f"{len(current_pci)} current PCI rows, latest pipeline age {age_hours:.1f}h"
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Smoke test the production PCIndex deployment.")
    parser.add_argument("--base-url", default=os.getenv("PRODUCTION_URL", DEFAULT_BASE_URL))
    parser.add_argument("--supabase-url", default=os.getenv("SUPABASE_URL"))
    parser.add_argument(
        "--supabase-key",
        default=(
            os.getenv("SUPABASE_PUBLISHABLE_KEY")
            or os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
            or os.getenv("SUPABASE_ANON_KEY")
        ),
    )
    parser.add_argument("--max-stale-hours", type=float, default=36.0)
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    try:
        check_pages(args.base_url)
        if args.supabase_url and args.supabase_key:
            check_supabase(
                args.supabase_url,
                args.supabase_key,
                max_stale_hours=args.max_stale_hours,
            )
        else:
            print("supabase checks skipped: publishable URL/key not configured")
    except RuntimeError as exc:
        print(f"smoke failed: {exc}", file=sys.stderr)
        return 1
    print("production smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

