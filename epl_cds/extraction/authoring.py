"""RAG-assisted ruleset *authoring aid* — drafts, never decisions.

============================ READ THIS FIRST ============================
This module uses an LLM to DRAFT a candidate ruleset from a paper's text. It is
an authoring assistant for a human expert, not an autonomous rule generator:

  * The model may only fill numeric thresholds for the KNOWN criteria catalog
    below — it cannot invent new criteria the deterministic engine doesn't
    understand. Unknown ids are rejected with a warning.
  * Every drafted rule is forced to `verify: true`, and the draft status is
    forced to UNVERIFIED/DRAFT.
  * The output is validated structurally and returned as YAML for human review.
    It is written only to a drafts location, NEVER to the live knowledge path,
    and a human must sign off and place it before the engine can ever load it.

LLM use stays under extraction/, per CLAUDE.md. The engine and live rulesets are
untouched by anything here.
========================================================================
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional

import yaml

from epl_cds.contracts import LLMFn
from epl_cds.knowledge.validator import RulesetValidationError, validate_ruleset_data

AUTHORING_PROMPT_VERSION = "a2"

# The criteria the deterministic engine understands. The model fills thresholds
# for these; it does not get to invent ids, tiers, or the comparison logic.
RULE_CATALOG: dict[str, dict[str, Any]] = {
    "crl_no_cardiac": {"tier": "diagnostic", "params": ["crl_mm"],
        "description": "Crown-rump length >= threshold with no cardiac activity."},
    "msd_no_embryo": {"tier": "diagnostic", "params": ["msd_mm"],
        "description": "Mean sac diameter >= threshold with no embryo."},
    "interval_no_yolk": {"tier": "diagnostic", "params": ["days"],
        "description": "No embryo with a heartbeat >= N days after a sac without a yolk sac."},
    "interval_with_yolk": {"tier": "diagnostic", "params": ["days"],
        "description": "No embryo with a heartbeat >= N days after a sac with a yolk sac."},
    "crl_small_no_cardiac": {"tier": "suspicious", "params": ["crl_max_mm"],
        "description": "Crown-rump length < threshold with no cardiac activity."},
    "msd_intermediate_no_embryo": {"tier": "suspicious", "params": ["msd_min_mm", "msd_max_mm"],
        "description": "Mean sac diameter in [min, max) mm with no embryo."},
    "interval_no_yolk_suspicious": {"tier": "suspicious", "params": ["days_min", "days_max"],
        "description": "No embryo with a heartbeat [min, max) days after a sac without a yolk sac."},
    "interval_with_yolk_suspicious": {"tier": "suspicious", "params": ["days_min", "days_max"],
        "description": "No embryo with a heartbeat [min, max) days after a sac with a yolk sac."},
    "enlarged_yolk_sac": {"tier": "suspicious", "params": ["max_mm"],
        "description": "Yolk sac diameter > threshold."},
    "empty_amnion": {"tier": "suspicious", "params": [],
        "description": "Amnion seen adjacent to the yolk sac with no visible embryo."},
    "small_sac_relative_to_embryo": {"tier": "suspicious", "params": ["min_diff_mm"],
        "description": "Difference between mean sac diameter and crown-rump length < threshold."},
    "no_embryo_by_lmp": {"tier": "suspicious", "params": ["days"],
        "description": "No embryo at or beyond N days after the last menstrual period."},
}


@dataclass
class DraftResult:
    yaml_text: str
    data: dict
    warnings: list[str] = field(default_factory=list)
    prompt_version: str = AUTHORING_PROMPT_VERSION
    rule_count: int = 0
    # Novel criteria the source describes that the engine does NOT implement.
    # These are non-executable proposals for human review, never auto-activated.
    proposals: list[dict] = field(default_factory=list)


def _catalog_for_prompt() -> str:
    lines = []
    for rid, meta in RULE_CATALOG.items():
        params = ", ".join(meta["params"]) or "(none)"
        lines.append(f"- {rid} [{meta['tier']}] params: {params}")
    return "\n".join(lines)


_TEMPLATE = """You are helping a clinician DRAFT a candidate early-pregnancy-loss ruleset
from the source text below. You may ONLY assign numeric thresholds to the known
criteria listed; do not invent new criteria. For each criterion the source
supports, give the threshold value(s) and a short citation (section/figure/page).
Omit any criterion the source does not address.

Known criteria (id [tier] params):
{catalog}

Also list any additional diagnostic criteria the source describes that are NOT
in the known list — these are proposals for a human to review, not something you
should force into a known id.

Return a single JSON object and nothing else:
{{
  "rules": [
    {{"id": "<known id>", "params": {{"<param>": <number>}}, "citation": "<where in source>"}}
  ],
  "proposals": [
    {{"name": "<short name>", "description": "<what/threshold>", "citation": "<where in source>"}}
  ]
}}

SOURCE TEXT:
\"\"\"
{source}
\"\"\"
"""


def render_authoring_prompt(source_text: str, context_passages: Optional[list[str]] = None) -> str:
    source = source_text
    if context_passages:
        source = "\n\n".join(context_passages) + "\n\n" + source_text
    return _TEMPLATE.format(catalog=_catalog_for_prompt(), source=source)


def draft_ruleset(
    source_text: str,
    llm_fn: LLMFn,
    *,
    name: str,
    version: str,
    source_label: str = "drafted from source",
    context_passages: Optional[list[str]] = None,
) -> DraftResult:
    """Draft a candidate ruleset from source text. Returns YAML for human review.

    The result is UNVERIFIED with `verify: true` on every rule. It is never a
    live ruleset and never reaches the engine without explicit human sign-off.
    """
    raw = llm_fn(render_authoring_prompt(source_text, context_passages))
    payload = _parse_obj(raw)
    warnings: list[str] = []

    rules: list[dict] = []
    for entry in payload.get("rules", []) if isinstance(payload, dict) else []:
        if not isinstance(entry, dict):
            continue
        rid = entry.get("id")
        meta = RULE_CATALOG.get(rid)
        if meta is None:
            warnings.append(f"dropped unknown criterion id: {rid!r}")
            continue
        params_in = entry.get("params") or {}
        params: dict[str, float] = {}
        ok = True
        for key in meta["params"]:
            val = params_in.get(key)
            if not isinstance(val, (int, float)) or isinstance(val, bool) or val <= 0:
                warnings.append(f"{rid}: missing/invalid param {key!r}; rule skipped")
                ok = False
                break
            params[key] = float(val)
        if not ok:
            continue
        rules.append(
            {
                "id": rid,
                "tier": meta["tier"],          # tier from catalog, not the model
                "description": meta["description"],
                "citation": str(entry.get("citation") or source_label).strip(),
                "verify": True,                # ALWAYS — awaits expert sign-off
                "params": params,
            }
        )

    if not rules:
        warnings.append("no usable rules were drafted from the source")

    data = {
        "version": version,
        "name": name,
        "source": f"DRAFT {source_label}",
        "status": (
            "DRAFT / UNVERIFIED — machine-drafted from source text; every "
            "threshold requires expert sign-off before any use."
        ),
        "rules": rules,
    }

    # Structural validation (raises if malformed). Empty rule lists are allowed
    # here as a draft, so only validate when there is at least one rule.
    if rules:
        try:
            validate_ruleset_data(data)
        except RulesetValidationError as exc:
            warnings.append(f"draft failed structural validation: {exc}")

    proposals: list[dict] = []
    for entry in payload.get("proposals", []) if isinstance(payload, dict) else []:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        if not name:
            continue
        proposals.append(
            {
                "name": name,
                "description": str(entry.get("description") or "").strip(),
                "citation": str(entry.get("citation") or source_label).strip(),
            }
        )

    yaml_text = _to_yaml(data)
    return DraftResult(
        yaml_text=yaml_text,
        data=data,
        warnings=warnings,
        rule_count=len(rules),
        proposals=proposals,
    )


_DRAFT_HEADER = (
    "# MACHINE-DRAFTED CANDIDATE RULESET — DO NOT USE.\n"
    "# Every threshold below was proposed by a language model from source text\n"
    "# and is UNVERIFIED. A domain expert must review, correct, and sign off\n"
    "# before this is placed in epl_cds/knowledge/ and loaded by the engine.\n\n"
)


def _to_yaml(data: dict) -> str:
    body = yaml.safe_dump(data, sort_keys=False, default_flow_style=False, width=88)
    return _DRAFT_HEADER + body


def _parse_obj(raw: Any) -> dict:
    if not isinstance(raw, str):
        return {}
    text = raw.strip()
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return {}
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
            return {}
    return obj if isinstance(obj, dict) else {}
