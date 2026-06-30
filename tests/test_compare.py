"""Tests for multi-ruleset loading and deterministic comparison."""

from epl_cds.contracts import Determination, Facts
from epl_cds.knowledge import load_all_rulesets
from epl_cds.knowledge.validator import validate_ruleset_data
from epl_cds.reasoning import compare_rulesets, is_concordant


def test_load_all_rulesets_includes_default_first():
    rulesets = load_all_rulesets()
    assert len(rulesets) >= 2
    assert rulesets[0].version == "v1"  # default sorts first
    labels = {rs.label for rs in rulesets}
    assert "SRU 2013" in labels


def test_every_ruleset_passes_structural_validation():
    # Loading already validates; assert the variant is well-formed too.
    rulesets = load_all_rulesets()
    versions = {rs.version for rs in rulesets}
    assert "legacy-strict-example-v1" in versions


def test_concordant_case():
    # MSD 28 mm, no embryo: diagnostic under both SRU (>=25) and legacy (>=16).
    entries = compare_rulesets(Facts(msd_mm=28.0, embryo_visible=False), load_all_rulesets())
    assert is_concordant(entries)
    assert all(e.result.determination == Determination.DIAGNOSTIC_OF_LOSS for e in entries)


def test_divergent_case_is_flagged():
    # MSD 18 mm, no embryo: SRU -> suspicious (16-24), legacy -> diagnostic (>=16).
    entries = compare_rulesets(Facts(msd_mm=18.0, embryo_visible=False), load_all_rulesets())
    assert not is_concordant(entries)
    by_label = {e.ruleset_label: e.result.determination for e in entries}
    assert by_label["SRU 2013"] == Determination.SUSPICIOUS_FOR_LOSS
    assert by_label["Legacy strict (EXAMPLE)"] == Determination.DIAGNOSTIC_OF_LOSS


def test_comparison_entries_carry_version_and_result():
    entries = compare_rulesets(Facts(), load_all_rulesets())
    for e in entries:
        assert e.ruleset_version
        assert e.result.determination == Determination.NO_CRITERIA_MET
