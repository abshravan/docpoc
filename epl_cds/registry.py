"""Runtime registries for proposed methods and approved rulesets.

These are *runtime artifacts* under a data directory (gitignored), produced by
the human-in-the-loop authoring flow — not part of the frozen package knowledge.

- Proposed methods: novel criteria a paper describes that the engine does NOT
  implement. They are recorded here as NON-EXECUTABLE proposals; activating one
  requires a developer to write a coded evaluator + tests + sign-off. Nothing
  here is ever run against a patient.
- Approved rulesets: threshold-only rulesets a clinician has approved. These use
  existing (coded) rule ids with new numbers, so they are safe to load.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Union


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ProposedMethod:
    """A novel candidate criterion — recorded, never executed."""

    name: str
    description: str
    citation: str = ""
    status: str = "proposed"  # proposed | approved_pending_implementation
    created_at: str = field(default_factory=_now)


def append_proposal(path: Union[str, Path], method: ProposedMethod) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(method)) + "\n")


def load_proposals(path: Union[str, Path]) -> list[ProposedMethod]:
    p = Path(path)
    if not p.exists():
        return []
    out: list[ProposedMethod] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(ProposedMethod(**json.loads(line)))
    return out
