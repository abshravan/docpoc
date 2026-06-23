"""Boundary tests pinning the clinical thresholds at their exact edges.

A failing test here means the ENGINE is wrong, not the threshold (see CLAUDE.md).
Never edit the ruleset to make one of these pass.
"""

import pytest

from epl_cds.contracts import Determination, Facts
from epl_cds.knowledge import load_ruleset
from epl_cds.reasoning import evaluate


@pytest.fixture(scope="module")
def ruleset():
    return load_ruleset()


def determine(ruleset, **facts) -> Determination:
    return evaluate(Facts(**facts), ruleset).determination


# --------------------------------------------------------------------------- #
# CRL + cardiac activity (diagnostic boundary at 7.0 mm)
# --------------------------------------------------------------------------- #
def test_crl_exactly_7mm_no_cardiac_is_diagnostic(ruleset):
    assert determine(ruleset, crl_mm=7.0, cardiac_activity=False, embryo_visible=True) == (
        Determination.DIAGNOSTIC_OF_LOSS
    )


def test_crl_6_9mm_no_cardiac_is_suspicious(ruleset):
    assert determine(ruleset, crl_mm=6.9, cardiac_activity=False, embryo_visible=True) == (
        Determination.SUSPICIOUS_FOR_LOSS
    )


def test_crl_7mm_with_cardiac_is_no_criteria(ruleset):
    # A heartbeat at any CRL is never a loss diagnosis.
    assert determine(ruleset, crl_mm=7.0, cardiac_activity=True, embryo_visible=True) == (
        Determination.NO_CRITERIA_MET
    )


def test_crl_unknown_cardiac_does_not_fire(ruleset):
    # Missing cardiac status must not be guessed.
    assert determine(ruleset, crl_mm=10.0, embryo_visible=True) == (
        Determination.NO_CRITERIA_MET
    )


# --------------------------------------------------------------------------- #
# MSD + no embryo (diagnostic at 25 mm; suspicious in [16, 25) mm)
# --------------------------------------------------------------------------- #
def test_msd_exactly_25mm_no_embryo_is_diagnostic(ruleset):
    assert determine(ruleset, msd_mm=25.0, embryo_visible=False) == (
        Determination.DIAGNOSTIC_OF_LOSS
    )


def test_msd_24_9mm_no_embryo_is_suspicious(ruleset):
    assert determine(ruleset, msd_mm=24.9, embryo_visible=False) == (
        Determination.SUSPICIOUS_FOR_LOSS
    )


def test_msd_exactly_16mm_no_embryo_is_suspicious(ruleset):
    assert determine(ruleset, msd_mm=16.0, embryo_visible=False) == (
        Determination.SUSPICIOUS_FOR_LOSS
    )


def test_msd_15_9mm_no_embryo_is_no_criteria(ruleset):
    assert determine(ruleset, msd_mm=15.9, embryo_visible=False) == (
        Determination.NO_CRITERIA_MET
    )


# --------------------------------------------------------------------------- #
# Interval criteria: sac WITHOUT yolk (diagnostic >=14 d, suspicious 7-13 d)
# --------------------------------------------------------------------------- #
def test_interval_no_yolk_14d_is_diagnostic(ruleset):
    assert determine(
        ruleset, days_since_sac_without_yolk=14, embryo_visible=False
    ) == Determination.DIAGNOSTIC_OF_LOSS


def test_interval_no_yolk_13d_is_suspicious(ruleset):
    assert determine(
        ruleset, days_since_sac_without_yolk=13, embryo_visible=False
    ) == Determination.SUSPICIOUS_FOR_LOSS


def test_interval_no_yolk_7d_is_suspicious(ruleset):
    assert determine(
        ruleset, days_since_sac_without_yolk=7, embryo_visible=False
    ) == Determination.SUSPICIOUS_FOR_LOSS


def test_interval_no_yolk_6d_is_no_criteria(ruleset):
    assert determine(
        ruleset, days_since_sac_without_yolk=6, embryo_visible=False
    ) == Determination.NO_CRITERIA_MET


# --------------------------------------------------------------------------- #
# Interval criteria: sac WITH yolk (diagnostic >=11 d, suspicious 7-10 d)
# --------------------------------------------------------------------------- #
def test_interval_with_yolk_11d_is_diagnostic(ruleset):
    assert determine(
        ruleset, days_since_sac_with_yolk=11, embryo_visible=False
    ) == Determination.DIAGNOSTIC_OF_LOSS


def test_interval_with_yolk_10d_is_suspicious(ruleset):
    assert determine(
        ruleset, days_since_sac_with_yolk=10, embryo_visible=False
    ) == Determination.SUSPICIOUS_FOR_LOSS


def test_interval_with_yolk_6d_is_no_criteria(ruleset):
    assert determine(
        ruleset, days_since_sac_with_yolk=6, embryo_visible=False
    ) == Determination.NO_CRITERIA_MET


# --------------------------------------------------------------------------- #
# Other suspicious criteria
# --------------------------------------------------------------------------- #
def test_enlarged_yolk_sac_over_7mm_is_suspicious(ruleset):
    assert determine(ruleset, yolk_sac_diameter_mm=7.5, yolk_sac_visible=True) == (
        Determination.SUSPICIOUS_FOR_LOSS
    )


def test_yolk_sac_exactly_7mm_is_no_criteria(ruleset):
    assert determine(ruleset, yolk_sac_diameter_mm=7.0, yolk_sac_visible=True) == (
        Determination.NO_CRITERIA_MET
    )


def test_empty_amnion_is_suspicious(ruleset):
    assert determine(ruleset, amnion_visible=True, embryo_visible=False) == (
        Determination.SUSPICIOUS_FOR_LOSS
    )


def test_no_embryo_42d_after_lmp_is_suspicious(ruleset):
    assert determine(ruleset, days_since_lmp=42, embryo_visible=False) == (
        Determination.SUSPICIOUS_FOR_LOSS
    )


# --------------------------------------------------------------------------- #
# Precedence & empties
# --------------------------------------------------------------------------- #
def test_no_facts_is_no_criteria(ruleset):
    assert determine(ruleset) == Determination.NO_CRITERIA_MET


def test_diagnostic_outranks_suspicious(ruleset):
    # CRL 8 mm no cardiac is diagnostic; small sac (MSD-CRL<5) is suspicious.
    # The diagnostic tier must win.
    result = evaluate(
        Facts(crl_mm=8.0, msd_mm=10.0, cardiac_activity=False, embryo_visible=True),
        ruleset,
    )
    assert result.determination == Determination.DIAGNOSTIC_OF_LOSS
    assert "crl_no_cardiac" in result.fired_rule_ids
    # suspicious rules are not reported once a diagnostic rule fires
    assert "small_sac_relative_to_embryo" not in result.fired_rule_ids
