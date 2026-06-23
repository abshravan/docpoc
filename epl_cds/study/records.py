"""Serialization for CaseRecord <-> plain dict (for JSONL logging)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from epl_cds.contracts import (
    CaseRecord,
    Determination,
    DeterminationResult,
    Facts,
)


def record_to_dict(record: CaseRecord) -> dict[str, Any]:
    """Convert a CaseRecord to a JSON-serializable dict.

    `Determination` is a str-Enum, so it serializes to its value directly.
    """
    return asdict(record)


def record_from_dict(data: dict[str, Any]) -> CaseRecord:
    """Reconstruct a CaseRecord from a logged dict."""
    facts = Facts(**data["facts"])
    result_data = dict(data["result"])
    result = DeterminationResult(
        determination=Determination(result_data["determination"]),
        fired_rule_ids=tuple(result_data["fired_rule_ids"]),
        ruleset_version=result_data["ruleset_version"],
        rationale=result_data["rationale"],
    )
    gold_facts = Facts(**data["gold_facts"]) if data.get("gold_facts") else None
    adjudicated = (
        Determination(data["adjudicated_determination"])
        if data.get("adjudicated_determination")
        else None
    )
    return CaseRecord(
        case_id=data["case_id"],
        facts=facts,
        result=result,
        extractor_model=data["extractor_model"],
        prompt_version=data["prompt_version"],
        ruleset_version=data["ruleset_version"],
        created_at=data["created_at"],
        note=data.get("note"),
        gold_facts=gold_facts,
        adjudicated_determination=adjudicated,
    )
