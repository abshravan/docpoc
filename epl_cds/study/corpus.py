"""Load a gold-labeled case corpus from JSONL.

Each line is one case:

    {
      "case_id": "ex-001",
      "note": "Transvaginal US. Embryo CRL 9 mm, no cardiac activity.",
      "gold_facts": {"crl_mm": 9.0, "cardiac_activity": false, "embryo_visible": true},
      "adjudicated_determination": "diagnostic_of_loss"
    }

`gold_facts` is the manual chart abstraction (Arm 1 reference); only documented
fields need be present. `adjudicated_determination` is the expert call (Arm 2
reference) and is optional.

Real study corpora live under a gitignored `data/` directory and require the
study gates (IRB, de-identification) to be satisfied. A small synthetic example
ships at `examples/cases.example.jsonl`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from epl_cds.contracts import Determination, Facts

DEFAULT_EXAMPLE_CORPUS = (
    Path(__file__).resolve().parents[2] / "examples" / "cases.example.jsonl"
)

_KNOWN_FIELDS = set(Facts.field_names())


@dataclass(frozen=True)
class CaseSpec:
    """One corpus case: the raw note plus its Arm-1 and Arm-2 references."""

    case_id: str
    note: str
    gold_facts: Facts
    adjudicated_determination: Optional[Determination] = None


class CorpusError(ValueError):
    """Raised when a corpus file or row is malformed."""


def load_cases(path: Union[str, Path, None] = None) -> list[CaseSpec]:
    """Read all cases from a JSONL corpus (default: the shipped example)."""
    corpus_path = Path(path) if path is not None else DEFAULT_EXAMPLE_CORPUS
    if not corpus_path.exists():
        raise CorpusError(f"corpus not found: {corpus_path}")

    cases: list[CaseSpec] = []
    with corpus_path.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CorpusError(f"{corpus_path}:{lineno}: invalid JSON: {exc}") from exc
            cases.append(_to_spec(row, corpus_path, lineno))
    return cases


def _to_spec(row: dict, path: Path, lineno: int) -> CaseSpec:
    if not isinstance(row, dict) or "case_id" not in row or "note" not in row:
        raise CorpusError(f"{path}:{lineno}: each case needs 'case_id' and 'note'")

    gold_raw = row.get("gold_facts") or {}
    unknown = set(gold_raw) - _KNOWN_FIELDS
    if unknown:
        raise CorpusError(f"{path}:{lineno}: unknown gold_facts fields: {sorted(unknown)}")
    gold_facts = Facts(**gold_raw)

    adjudicated = row.get("adjudicated_determination")
    determination: Optional[Determination] = None
    if adjudicated is not None:
        try:
            determination = Determination(adjudicated)
        except ValueError as exc:
            raise CorpusError(
                f"{path}:{lineno}: bad adjudicated_determination {adjudicated!r}"
            ) from exc

    return CaseSpec(
        case_id=str(row["case_id"]),
        note=str(row["note"]),
        gold_facts=gold_facts,
        adjudicated_determination=determination,
    )
