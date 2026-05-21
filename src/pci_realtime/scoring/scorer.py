from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from pci_realtime.config import (
    CACHE_ROOT,
    OPENAI_SCORING_MODEL,
    OPENAI_SCREENING_MODEL,
    PROCESSED_DATA_ROOT,
    PROJECT_ROOT,
    RAW_DATA_ROOT,
    SCORING_ESTIMATED_COST_PER_CALL_USD,
    SCORING_RUN_COST_CEILING_USD,
    SCORING_SCHEMA_VERSION,
    SCORING_TEMPERATURE,
    TRACKED_PROVISIONS,
)
from pci_realtime.scoring.cache import JsonCache, build_cache_key
from pci_realtime.scoring.prompts import (
    SCORING_JSON_SCHEMA,
    SCORING_PROMPT_VERSION,
    SCORING_SYSTEM_PROMPT,
    SCREENING_SYSTEM_PROMPT,
    build_scoring_user_prompt,
    build_screening_user_prompt,
)
from pci_realtime.scoring.screener import (
    DocumentScreener,
    OpenAIStructuredOutputClient,
    StructuredOutputClient,
)


LOGGER = logging.getLogger(__name__)
DELTA_COLUMNS = ["specificity_delta", "durability_delta", "enforceability_delta"]
SCHEMA_B_COLUMNS = [
    "doc_id",
    "provision",
    "specificity_delta",
    "durability_delta",
    "enforceability_delta",
    "rationale",
    "confidence",
    "model",
    "prompt_version",
    "temperature",
    "scored_at",
    "cached",
    "cost_usd",
]


@dataclass(frozen=True)
class ScoringResult:
    doc_id: str
    provision: str
    specificity_delta: float
    durability_delta: float
    enforceability_delta: float
    rationale: str
    confidence: float
    model: str
    prompt_version: str
    temperature: float
    scored_at: pd.Timestamp
    cached: bool
    cost_usd: float
    raw_response: str = ""

    def to_row(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "provision": self.provision,
            "specificity_delta": self.specificity_delta,
            "durability_delta": self.durability_delta,
            "enforceability_delta": self.enforceability_delta,
            "rationale": self.rationale,
            "confidence": self.confidence,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "temperature": self.temperature,
            "scored_at": self.scored_at,
            "cached": self.cached,
            "cost_usd": self.cost_usd,
        }


def _validate_delta(name: str, value: Any) -> float:
    delta = float(value)
    if not -2.0 <= delta <= 2.0:
        msg = f"{name} must be in [-2.0, 2.0], got {delta}"
        raise ValueError(msg)
    return delta


def parse_scoring_payload(
    payload: Mapping[str, Any],
    *,
    document: Mapping[str, Any],
    expected_provision: str,
    model: str,
    prompt_version: str,
    temperature: float,
    cached: bool,
    cost_usd: float,
    scored_at: pd.Timestamp | None = None,
    raw_response: str = "",
) -> ScoringResult:
    provision = str(payload.get("provision", ""))
    if provision != expected_provision:
        msg = f"Expected provision {expected_provision}, got {provision}"
        raise ValueError(msg)
    if provision not in TRACKED_PROVISIONS:
        msg = f"Invalid provision: {provision}"
        raise ValueError(msg)

    confidence = float(payload.get("confidence", -1.0))
    if not 0.0 <= confidence <= 1.0:
        msg = f"Scoring confidence must be in [0, 1], got {confidence}"
        raise ValueError(msg)

    return ScoringResult(
        doc_id=str(document["doc_id"]),
        provision=provision,
        specificity_delta=_validate_delta(
            "specificity_delta", payload.get("specificity_delta")
        ),
        durability_delta=_validate_delta(
            "durability_delta", payload.get("durability_delta")
        ),
        enforceability_delta=_validate_delta(
            "enforceability_delta", payload.get("enforceability_delta")
        ),
        rationale=str(payload.get("rationale", "")),
        confidence=confidence,
        model=model,
        prompt_version=prompt_version,
        temperature=temperature,
        scored_at=scored_at or pd.Timestamp.now(tz="UTC"),
        cached=cached,
        cost_usd=cost_usd,
        raw_response=raw_response,
    )


def enforce_schema_b(rows: list[dict[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    df = rows.copy() if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=SCHEMA_B_COLUMNS)

    missing = [column for column in SCHEMA_B_COLUMNS if column not in df.columns]
    if missing:
        msg = f"Schema B missing required columns: {missing}"
        raise ValueError(msg)

    df = df.loc[:, SCHEMA_B_COLUMNS].copy()
    df["doc_id"] = df["doc_id"].astype("string")
    df["provision"] = df["provision"].astype("string")
    invalid = sorted(set(df["provision"].dropna()) - set(TRACKED_PROVISIONS))
    if invalid:
        msg = f"Invalid Schema B provisions: {invalid}"
        raise ValueError(msg)

    duplicates = df.duplicated(["doc_id", "provision"])
    if duplicates.any():
        duplicate_keys = df.loc[duplicates, ["doc_id", "provision"]].to_dict("records")
        msg = f"Duplicate Schema B (doc_id, provision) rows: {duplicate_keys}"
        raise ValueError(msg)

    for column in DELTA_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="raise").astype(float)
        out_of_range = ~df[column].between(-2.0, 2.0)
        if out_of_range.any():
            bad = df.loc[out_of_range, ["doc_id", "provision", column]].to_dict(
                "records"
            )
            msg = f"{column} outside [-2.0, 2.0]: {bad}"
            raise ValueError(msg)

    df["confidence"] = pd.to_numeric(df["confidence"], errors="raise").astype(float)
    bad_confidence = ~df["confidence"].between(0.0, 1.0)
    if bad_confidence.any():
        bad = df.loc[bad_confidence, ["doc_id", "provision", "confidence"]].to_dict(
            "records"
        )
        msg = f"confidence outside [0.0, 1.0]: {bad}"
        raise ValueError(msg)

    for column in ["rationale", "model", "prompt_version"]:
        df[column] = df[column].fillna("").astype("string")
    df["temperature"] = pd.to_numeric(df["temperature"], errors="raise").astype(float)
    df["scored_at"] = pd.to_datetime(df["scored_at"], utc=True)
    df["cached"] = df["cached"].fillna(False).astype(bool)
    df["cost_usd"] = pd.to_numeric(df["cost_usd"], errors="raise").astype(float)
    return df.sort_values(["doc_id", "provision"]).reset_index(drop=True)


class DocumentScorer:
    def __init__(
        self,
        *,
        client: StructuredOutputClient | None = None,
        cache: JsonCache | None = None,
        model: str = OPENAI_SCORING_MODEL,
        prompt_version: str = SCORING_PROMPT_VERSION,
        temperature: float = SCORING_TEMPERATURE,
        schema_version: str = SCORING_SCHEMA_VERSION,
    ) -> None:
        self.client = client or OpenAIStructuredOutputClient()
        self.cache = cache or JsonCache(CACHE_ROOT / "scoring")
        self.model = model
        self.prompt_version = prompt_version
        self.temperature = temperature
        self.schema_version = schema_version

    def score_document(
        self,
        document: Mapping[str, Any],
        provision: str,
        cache_metadata: Mapping[str, Any] | None = None,
    ) -> ScoringResult:
        if provision not in TRACKED_PROVISIONS:
            msg = f"Cannot score unknown provision: {provision}"
            raise ValueError(msg)

        user_prompt = build_scoring_user_prompt(document, provision)
        input_payload = {
            "doc_id": str(document.get("doc_id", "")),
            "provision": provision,
            "title": str(document.get("title", "")),
            "body": str(document.get("body", "")),
            "cache_metadata": dict(cache_metadata or {}),
        }
        cache_key = build_cache_key(
            provider=self.client.provider,
            model=self.model,
            prompt_version=self.prompt_version,
            temperature=self.temperature,
            schema_version=self.schema_version,
            stage="scoring",
            input_payload=input_payload,
        )
        cached = self.cache.get(cache_key)
        if cached is not None:
            return parse_scoring_payload(
                cached.payload,
                document=document,
                expected_provision=provision,
                model=self.model,
                prompt_version=self.prompt_version,
                temperature=self.temperature,
                cached=True,
                cost_usd=0.0,
                raw_response=cached.raw_response,
            )

        response = self.client.create_json(
            model=self.model,
            system_prompt=SCORING_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            json_schema=SCORING_JSON_SCHEMA,
            schema_name="pci_delta_scoring",
            temperature=self.temperature,
        )
        self.cache.set(cache_key, response)
        return parse_scoring_payload(
            response.payload,
            document=document,
            expected_provision=provision,
            model=self.model,
            prompt_version=self.prompt_version,
            temperature=self.temperature,
            cached=False,
            cost_usd=response.cost_usd,
            raw_response=response.raw_response,
        )


def find_raw_week_files(week: str, raw_root: Path = RAW_DATA_ROOT) -> list[Path]:
    return sorted(raw_root.glob(f"*/*_{week}.parquet"))


def output_path_for_week(
    week: str, output_dir: Path = PROCESSED_DATA_ROOT / "scored"
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / f"scored_{week}.parquet"


def read_raw_week(week: str, raw_root: Path = RAW_DATA_ROOT) -> pd.DataFrame:
    files = find_raw_week_files(week, raw_root=raw_root)
    if not files:
        msg = f"No raw Schema A parquet files found for week {week} under {raw_root}"
        raise FileNotFoundError(msg)
    return pd.concat((pd.read_parquet(path) for path in files), ignore_index=True)


def estimated_run_cost(
    n_docs: int,
    *,
    cost_per_call_usd: float = SCORING_ESTIMATED_COST_PER_CALL_USD,
) -> float:
    return n_docs * (1 + len(TRACKED_PROVISIONS)) * cost_per_call_usd


def _cost_ceiling_from_env() -> float:
    return float(
        os.getenv("PCI_LLM_RUN_COST_CEILING_USD", str(SCORING_RUN_COST_CEILING_USD))
    )


def append_audit_log(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, default=str, sort_keys=True))
            handle.write("\n")


def run_week(
    *,
    week: str,
    raw_root: Path = RAW_DATA_ROOT,
    output_dir: Path = PROCESSED_DATA_ROOT / "scored",
    cache_root: Path = CACHE_ROOT,
    screening_model: str = OPENAI_SCREENING_MODEL,
    scoring_model: str = OPENAI_SCORING_MODEL,
    temperature: float = SCORING_TEMPERATURE,
    confirm_cost: bool = False,
    client: StructuredOutputClient | None = None,
    audit_log_path: Path = PROJECT_ROOT / "docs" / "llm_call_log.jsonl",
) -> Path:
    raw_df = read_raw_week(week, raw_root=raw_root)
    estimate = estimated_run_cost(len(raw_df))
    ceiling = _cost_ceiling_from_env()
    if estimate > ceiling and not confirm_cost:
        msg = (
            f"Estimated scoring cost ${estimate:.2f} exceeds ceiling ${ceiling:.2f}. "
            "Pass --confirm-cost to run anyway."
        )
        raise RuntimeError(msg)

    structured_client = client or OpenAIStructuredOutputClient()
    screener = DocumentScreener(
        client=structured_client,
        cache=JsonCache(cache_root / "screening"),
        model=screening_model,
        temperature=temperature,
    )
    scorer = DocumentScorer(
        client=structured_client,
        cache=JsonCache(cache_root / "scoring"),
        model=scoring_model,
        temperature=temperature,
    )

    rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    for document in raw_df.to_dict("records"):
        screening = screener.screen_document(document)
        audit_rows.append(
            {
                "stage": "screening",
                "doc_id": document["doc_id"],
                "model": screening.model,
                "prompt_version": screening.prompt_version,
                "temperature": screening.temperature,
                "system_prompt": SCREENING_SYSTEM_PROMPT,
                "user_prompt": build_screening_user_prompt(document),
                "raw_response": screening.raw_response,
                "cached": screening.cached,
                "cost_usd": screening.cost_usd,
                "logged_at": pd.Timestamp.now(tz="UTC"),
            }
        )
        if not screening.relevant:
            continue
        for provision in screening.provisions:
            result = scorer.score_document(document, provision)
            rows.append(result.to_row())
            audit_rows.append(
                {
                    "stage": "scoring",
                    "doc_id": result.doc_id,
                    "provision": result.provision,
                    "model": result.model,
                    "prompt_version": result.prompt_version,
                    "temperature": result.temperature,
                    "system_prompt": SCORING_SYSTEM_PROMPT,
                    "user_prompt": build_scoring_user_prompt(
                        document, result.provision
                    ),
                    "raw_response": result.raw_response,
                    "cached": result.cached,
                    "cost_usd": result.cost_usd,
                    "logged_at": pd.Timestamp.now(tz="UTC"),
                }
            )

    schema_b = enforce_schema_b(rows)
    output_path = output_path_for_week(week, output_dir=output_dir)
    schema_b.to_parquet(output_path, index=False)
    append_audit_log(audit_log_path, audit_rows)
    return output_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Score PCI document deltas for a week."
    )
    parser.add_argument("--week", required=True, help="ISO week label, e.g. 2024-W44.")
    parser.add_argument("--raw-root", default=str(RAW_DATA_ROOT))
    parser.add_argument("--output-dir", default=str(PROCESSED_DATA_ROOT / "scored"))
    parser.add_argument("--cache-dir", default=str(CACHE_ROOT))
    parser.add_argument("--screening-model", default=OPENAI_SCREENING_MODEL)
    parser.add_argument("--scoring-model", default=OPENAI_SCORING_MODEL)
    parser.add_argument("--temperature", type=float, default=SCORING_TEMPERATURE)
    parser.add_argument("--confirm-cost", action="store_true")
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = build_arg_parser().parse_args()
    output_path = run_week(
        week=args.week,
        raw_root=Path(args.raw_root),
        output_dir=Path(args.output_dir),
        cache_root=Path(args.cache_dir),
        screening_model=args.screening_model,
        scoring_model=args.scoring_model,
        temperature=args.temperature,
        confirm_cost=args.confirm_cost,
    )
    LOGGER.info("Wrote scored Schema B parquet to %s", output_path)


if __name__ == "__main__":
    main()
