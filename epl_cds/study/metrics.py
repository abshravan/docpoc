"""Two-arm study metrics, kept strictly separable.

Arm 1 scores the LLM extraction (facts vs gold facts), per fact field.
Arm 2 scores the deterministic engine (determination vs expert adjudication).

Neither function blends the two arms.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from epl_cds.contracts import CaseRecord, Determination, Facts


# --------------------------------------------------------------------------- #
# Arm 1: extraction accuracy (per fact field)
# --------------------------------------------------------------------------- #
@dataclass
class FieldScore:
    correct: int = 0
    total: int = 0  # number of cases where the gold value is documented (not None)

    @property
    def accuracy(self) -> float | None:
        return self.correct / self.total if self.total else None


@dataclass
class Arm1Result:
    by_field: dict[str, FieldScore] = field(default_factory=dict)
    cases_scored: int = 0

    @property
    def overall_accuracy(self) -> float | None:
        correct = sum(s.correct for s in self.by_field.values())
        total = sum(s.total for s in self.by_field.values())
        return correct / total if total else None


def arm1_extraction_accuracy(records: Iterable[CaseRecord]) -> Arm1Result:
    """Per-field extraction accuracy over records that have gold_facts.

    A field is scored only when the gold value is documented (not None); the
    extracted value is correct iff it equals the gold value exactly.
    """
    result = Arm1Result(by_field={name: FieldScore() for name in Facts.field_names()})
    for rec in records:
        if rec.gold_facts is None:
            continue
        result.cases_scored += 1
        for name in Facts.field_names():
            gold = getattr(rec.gold_facts, name)
            if gold is None:
                continue
            score = result.by_field[name]
            score.total += 1
            if getattr(rec.facts, name) == gold:
                score.correct += 1
    return result


# --------------------------------------------------------------------------- #
# Arm 2: reasoning accuracy (determination vs adjudication)
# --------------------------------------------------------------------------- #
@dataclass
class Arm2Result:
    correct: int = 0
    total: int = 0
    # confusion[(adjudicated, engine)] = count
    confusion: dict[tuple[str, str], int] = field(default_factory=dict)

    @property
    def accuracy(self) -> float | None:
        return self.correct / self.total if self.total else None


def arm2_reasoning_accuracy(records: Iterable[CaseRecord]) -> Arm2Result:
    """Engine determination vs expert adjudication, for adjudicated records.

    Arm 2 should approach 100% by construction; any miss is a rule-encoding bug,
    not noise (see CLAUDE.md).
    """
    result = Arm2Result()
    for rec in records:
        if rec.adjudicated_determination is None:
            continue
        result.total += 1
        engine: Determination = rec.result.determination
        adjudicated: Determination = rec.adjudicated_determination
        if engine == adjudicated:
            result.correct += 1
        key = (adjudicated.value, engine.value)
        result.confusion[key] = result.confusion.get(key, 0) + 1
    return result
