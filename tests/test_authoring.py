"""Tests for the RAG ruleset-authoring aid (drafts, never activations)."""

import json

import yaml

from epl_cds.extraction.authoring import draft_ruleset
from epl_cds.knowledge.validator import validate_ruleset_data


def _llm(obj):
    return lambda _: json.dumps(obj)


def test_draft_fills_thresholds_and_forces_verify():
    llm = _llm(
        {
            "rules": [
                {"id": "crl_no_cardiac", "params": {"crl_mm": 7}, "citation": "Table 1"},
                {"id": "msd_no_embryo", "params": {"msd_mm": 25}, "citation": "Table 1"},
            ]
        }
    )
    draft = draft_ruleset(llm("x") and "paper text", llm, name="Test", version="draft-v1")
    assert draft.rule_count == 2
    assert all(r["verify"] is True for r in draft.data["rules"])
    assert "DRAFT" in draft.data["status"] and "UNVERIFIED" in draft.data["status"]
    # tier/description come from the catalog, not the model
    crl = next(r for r in draft.data["rules"] if r["id"] == "crl_no_cardiac")
    assert crl["tier"] == "diagnostic"
    # The emitted YAML is parseable and structurally valid.
    parsed = yaml.safe_load(draft.yaml_text)
    validate_ruleset_data(parsed)


def test_draft_rejects_unknown_criteria():
    draft = draft_ruleset(
        "paper",
        _llm({"rules": [{"id": "made_up_rule", "params": {"x": 1}}]}),
        name="T",
        version="draft-v1",
    )
    assert draft.rule_count == 0
    assert any("unknown criterion" in w for w in draft.warnings)


def test_draft_skips_rules_with_missing_params():
    draft = draft_ruleset(
        "paper",
        _llm({"rules": [{"id": "msd_intermediate_no_embryo", "params": {"msd_min_mm": 16}}]}),
        name="T",
        version="draft-v1",
    )
    # msd_max_mm missing -> rule skipped with a warning
    assert draft.rule_count == 0
    assert any("msd_max_mm" in w for w in draft.warnings)


def test_draft_header_warns_do_not_use():
    draft = draft_ruleset(
        "paper",
        _llm({"rules": [{"id": "empty_amnion", "params": {}}]}),
        name="T",
        version="draft-v1",
    )
    assert "DO NOT USE" in draft.yaml_text
    assert draft.rule_count == 1  # empty_amnion needs no params
