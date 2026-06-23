"""Append-only JSONL log of CaseRecords.

Append-only by construction: records are only ever added, never rewritten in
place. This is the study's audit trail.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Union

from epl_cds.contracts import CaseRecord
from epl_cds.study.records import record_from_dict, record_to_dict


def append_record(path: Union[str, Path], record: CaseRecord) -> None:
    """Append one CaseRecord as a JSON line."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record_to_dict(record), sort_keys=True))
        fh.write("\n")


def read_log(path: Union[str, Path]) -> list[CaseRecord]:
    """Read all CaseRecords from a JSONL log (empty list if missing)."""
    p = Path(path)
    if not p.exists():
        return []
    records: list[CaseRecord] = []
    with p.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            records.append(record_from_dict(json.loads(line)))
    return records
