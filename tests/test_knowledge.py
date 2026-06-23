"""Tests for the ruleset loader, validator, and engine/knowledge consistency."""

import pytest

from epl_cds.knowledge import load_ruleset
from epl_cds.knowledge.validator import (
    RulesetValidationError,
    validate_ruleset_data,
)
from epl_cds.reasoning.engine import RULE_EVALUATORS


def test_default_ruleset_loads_and_is_v1():
    rs = load_ruleset()
    assert rs.version == "v1"
    assert len(rs.rules) == 12
    assert all(r.tier in {"diagnostic", "suspicious"} for r in rs.rules)


def test_every_ruleset_rule_has_an_evaluator():
    # Knowledge and code must not drift apart.
    rs = load_ruleset()
    for rule in rs.rules:
        assert rule.id in RULE_EVALUATORS, f"no evaluator for {rule.id}"


def test_all_thresholds_flagged_for_verification():
    rs = load_ruleset()
    assert all(r.verify for r in rs.rules), "every threshold must await sign-off"


def test_validator_rejects_unknown_tier():
    data = {
        "version": "x",
        "source": "s",
        "status": "s",
        "rules": [
            {
                "id": "r",
                "tier": "definitely",
                "description": "d",
                "citation": "c",
                "verify": True,
                "params": {},
            }
        ],
    }
    with pytest.raises(RulesetValidationError):
        validate_ruleset_data(data)


def test_validator_rejects_duplicate_ids():
    rule = {
        "id": "dup",
        "tier": "diagnostic",
        "description": "d",
        "citation": "c",
        "verify": True,
        "params": {},
    }
    data = {"version": "x", "source": "s", "status": "s", "rules": [rule, dict(rule)]}
    with pytest.raises(RulesetValidationError):
        validate_ruleset_data(data)


def test_validator_rejects_non_positive_threshold():
    data = {
        "version": "x",
        "source": "s",
        "status": "s",
        "rules": [
            {
                "id": "r",
                "tier": "diagnostic",
                "description": "d",
                "citation": "c",
                "verify": True,
                "params": {"crl_mm": 0},
            }
        ],
    }
    with pytest.raises(RulesetValidationError):
        validate_ruleset_data(data)
