from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from pci_realtime.config import PROJECT_ROOT, TRACKED_PROVISIONS


DEFAULT_QUERY_FILE = PROJECT_ROOT / "config" / "provision_queries.yml"
QUERY_FIELDS = (
    "aliases",
    "statutes",
    "agencies",
    "dockets",
    "litigation",
    "implementation",
)


@dataclass(frozen=True)
class ProvisionQueryPack:
    provision: str
    aliases: tuple[str, ...]
    statutes: tuple[str, ...]
    agencies: tuple[str, ...]
    dockets: tuple[str, ...]
    litigation: tuple[str, ...]
    implementation: tuple[str, ...]

    @property
    def all_terms(self) -> tuple[str, ...]:
        terms: list[str] = []
        for field in QUERY_FIELDS:
            terms.extend(getattr(self, field))
        return tuple(dict.fromkeys(term for term in terms if term))


def load_provision_query_packs(
    path: Path = DEFAULT_QUERY_FILE,
) -> dict[str, ProvisionQueryPack]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw_provisions = payload.get("provisions") or {}
    packs: dict[str, ProvisionQueryPack] = {}
    for provision in TRACKED_PROVISIONS:
        item = raw_provisions.get(provision) or {}
        packs[provision] = ProvisionQueryPack(
            provision=provision,
            aliases=tuple_values(item, "aliases", fallback=(provision,)),
            statutes=tuple_values(item, "statutes"),
            agencies=tuple_values(item, "agencies"),
            dockets=tuple_values(item, "dockets"),
            litigation=tuple_values(item, "litigation"),
            implementation=tuple_values(item, "implementation"),
        )
    return packs


def tuple_values(
    item: dict[str, Any], key: str, fallback: tuple[str, ...] = ()
) -> tuple[str, ...]:
    values = item.get(key)
    if values is None:
        return fallback
    if not isinstance(values, list):
        msg = f"provision query field {key!r} must be a list"
        raise ValueError(msg)
    return tuple(str(value).strip() for value in values if str(value).strip())
