"""Pre-freeze structural validation for a ruleset document.

This checks *structure*, not clinical correctness — it cannot tell whether
7.0 mm is the right CRL threshold (only an expert can). It guards against
malformed YAML reaching the engine: missing tiers, blank citations, duplicate
ids, non-positive thresholds, etc.

Imports only from the standard library — never from a sibling layer.
"""

from __future__ import annotations

from typing import Any

VALID_TIERS = {"diagnostic", "suspicious"}
REQUIRED_TOP_LEVEL = ("version", "source", "status", "rules")
REQUIRED_RULE_FIELDS = ("id", "tier", "description", "citation", "verify", "params")


class RulesetValidationError(ValueError):
    """Raised when a ruleset document fails structural validation."""


def validate_ruleset_data(data: Any) -> None:
    """Raise RulesetValidationError if `data` is not a well-formed ruleset.

    Returns None on success.
    """
    if not isinstance(data, dict):
        raise RulesetValidationError("ruleset must be a mapping at the top level")

    for key in REQUIRED_TOP_LEVEL:
        if key not in data:
            raise RulesetValidationError(f"ruleset missing required key: {key!r}")

    if not isinstance(data["version"], str) or not data["version"].strip():
        raise RulesetValidationError("ruleset 'version' must be a non-empty string")

    rules = data["rules"]
    if not isinstance(rules, list) or not rules:
        raise RulesetValidationError("ruleset 'rules' must be a non-empty list")

    seen_ids: set[str] = set()
    for idx, rule in enumerate(rules):
        _validate_rule(rule, idx, seen_ids)


def _validate_rule(rule: Any, idx: int, seen_ids: set[str]) -> None:
    where = f"rules[{idx}]"
    if not isinstance(rule, dict):
        raise RulesetValidationError(f"{where} must be a mapping")

    for fld in REQUIRED_RULE_FIELDS:
        if fld not in rule:
            raise RulesetValidationError(f"{where} missing required field: {fld!r}")

    rid = rule["id"]
    if not isinstance(rid, str) or not rid.strip():
        raise RulesetValidationError(f"{where} 'id' must be a non-empty string")
    if rid in seen_ids:
        raise RulesetValidationError(f"duplicate rule id: {rid!r}")
    seen_ids.add(rid)

    if rule["tier"] not in VALID_TIERS:
        raise RulesetValidationError(
            f"{where} ({rid}) tier {rule['tier']!r} not in {sorted(VALID_TIERS)}"
        )

    for str_field in ("description", "citation"):
        if not isinstance(rule[str_field], str) or not rule[str_field].strip():
            raise RulesetValidationError(
                f"{where} ({rid}) {str_field!r} must be a non-empty string"
            )

    if not isinstance(rule["verify"], bool):
        raise RulesetValidationError(f"{where} ({rid}) 'verify' must be a boolean")

    params = rule["params"]
    if not isinstance(params, dict):
        raise RulesetValidationError(f"{where} ({rid}) 'params' must be a mapping")

    for pkey, pval in params.items():
        if isinstance(pval, bool) or not isinstance(pval, (int, float)):
            raise RulesetValidationError(
                f"{where} ({rid}) param {pkey!r} must be a number, got {pval!r}"
            )
        if pval <= 0:
            raise RulesetValidationError(
                f"{where} ({rid}) param {pkey!r} must be positive, got {pval!r}"
            )
