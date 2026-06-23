"""Load the frozen ruleset YAML into an immutable Ruleset (contracts).

The loader runs the structural validator before constructing the dataclass, so
a malformed ruleset can never reach the engine.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

import yaml

from epl_cds.contracts import Rule, Ruleset
from epl_cds.knowledge.validator import validate_ruleset_data

DEFAULT_RULESET_PATH = Path(__file__).with_name("epl_ruleset_v1.yaml")


def load_ruleset(path: Optional[Union[str, Path]] = None) -> Ruleset:
    """Read, validate, and freeze the ruleset at `path` (default: v1)."""
    ruleset_path = Path(path) if path is not None else DEFAULT_RULESET_PATH
    with ruleset_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    validate_ruleset_data(data)

    rules = tuple(
        Rule(
            id=r["id"],
            tier=r["tier"],
            description=r["description"].strip(),
            citation=r["citation"].strip(),
            verify=r["verify"],
            params=dict(r["params"]),
        )
        for r in data["rules"]
    )

    return Ruleset(
        version=data["version"],
        source=data["source"].strip(),
        status=data["status"].strip(),
        rules=rules,
    )
