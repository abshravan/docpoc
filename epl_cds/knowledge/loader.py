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
        name=str(data.get("name", "")).strip(),
    )


def load_all_rulesets(
    directory: Optional[Union[str, Path]] = None,
    extra_dirs: Optional[list[Union[str, Path]]] = None,
) -> list[Ruleset]:
    """Load every packaged `epl_ruleset_*.yaml`, plus any `*.yaml` in `extra_dirs`.

    The default ruleset (v1) sorts first; the rest follow. `extra_dirs` is where
    clinician-approved (threshold-only) rulesets live at runtime, outside the
    frozen package knowledge.
    """
    base = Path(directory) if directory is not None else DEFAULT_RULESET_PATH.parent
    paths = list(base.glob("epl_ruleset_*.yaml"))
    for extra in extra_dirs or []:
        extra_path = Path(extra)
        if extra_path.is_dir():
            paths.extend(sorted(extra_path.glob("*.yaml")))
    # Keep the default ruleset first for a stable, predictable ordering.
    paths.sort(key=lambda p: (p != DEFAULT_RULESET_PATH, str(p)))
    seen: set[str] = set()
    rulesets: list[Ruleset] = []
    for p in paths:
        rs = load_ruleset(p)
        if rs.version in seen:
            continue  # first occurrence wins (packaged over approved)
        seen.add(rs.version)
        rulesets.append(rs)
    return rulesets
