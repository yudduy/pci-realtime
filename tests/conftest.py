from __future__ import annotations

from typing import Any


class RecordingSupabaseClient:
    def __init__(self, *, fail_on_table: str | None = None) -> None:
        self.calls: list[tuple[str, str, list[dict[str, Any]], str | None]] = []
        self.fail_on_table = fail_on_table

    def insert_rows(self, table: str, rows: list[dict[str, Any]]) -> None:
        self._record("insert", table, rows, None)

    def upsert_rows(
        self,
        table: str,
        rows: list[dict[str, Any]],
        *,
        on_conflict: str | None = None,
    ) -> None:
        self._record("upsert", table, rows, on_conflict)

    def _record(
        self,
        method: str,
        table: str,
        rows: list[dict[str, Any]],
        on_conflict: str | None,
    ) -> None:
        self.calls.append((method, table, rows, on_conflict))
        if table == self.fail_on_table:
            raise RuntimeError(f"forced failure for {table}")


class SelectingSupabaseClient:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, str, dict[str, str] | None]] = []

    def select_rows(
        self,
        table: str,
        *,
        columns: str = "*",
        params: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        self.calls.append((table, columns, params))
        return self.rows
