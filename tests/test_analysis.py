"""Tests for per-fact mismatch capture and determination-flip analysis."""

from datetime import datetime, timezone

from epl_cds.contracts import (
    CaseRecord,
    Determination,
    DeterminationResult,
    Facts,
)
from epl_cds.study.metrics import (
    arm1_extraction_accuracy,
    determination_flip_analysis,
)


def _record(case_id, extracted, gold, extracted_det, gold_det):
    return CaseRecord(
        case_id=case_id,
        facts=extracted,
        result=DeterminationResult(extracted_det, (), "v1", ""),
        extractor_model="stub",
        prompt_version="p1",
        ruleset_version="v1",
        created_at=datetime.now(timezone.utc).isoformat(),
        gold_facts=gold,
        gold_determination=gold_det,
    )


def test_field_mismatch_is_captured():
    rec = _record(
        "c1",
        Facts(crl_mm=9.0, cardiac_activity=True),   # extracted: heartbeat present (wrong)
        Facts(crl_mm=9.0, cardiac_activity=False),  # gold: no heartbeat
        Determination.NO_CRITERIA_MET,
        Determination.DIAGNOSTIC_OF_LOSS,
    )
    arm1 = arm1_extraction_accuracy([rec])
    ca = arm1.by_field["cardiac_activity"]
    assert ca.accuracy == 0.0
    assert len(ca.mismatches) == 1
    assert ca.mismatches[0].gold is False and ca.mismatches[0].predicted is True
    assert arm1.by_field["crl_mm"].accuracy == 1.0


def test_determination_flip_detected():
    # The cardiac_activity mis-extraction flips diagnostic -> no_criteria_met.
    flip_rec = _record(
        "flip",
        Facts(crl_mm=9.0, cardiac_activity=True),
        Facts(crl_mm=9.0, cardiac_activity=False),
        Determination.NO_CRITERIA_MET,
        Determination.DIAGNOSTIC_OF_LOSS,
    )
    # A clean case where extraction matches gold -> no flip.
    ok_rec = _record(
        "ok",
        Facts(msd_mm=28.0, embryo_visible=False),
        Facts(msd_mm=28.0, embryo_visible=False),
        Determination.DIAGNOSTIC_OF_LOSS,
        Determination.DIAGNOSTIC_OF_LOSS,
    )
    result = determination_flip_analysis([flip_rec, ok_rec])
    assert result.total == 2
    assert result.flip_count == 1
    assert result.flip_rate == 0.5
    assert result.agreement_rate == 0.5
    flip = result.flips[0]
    assert flip.case_id == "flip"
    assert flip.from_gold == "diagnostic_of_loss"
    assert flip.to_extracted == "no_criteria_met"


def test_flip_ignores_records_without_gold_determination():
    rec = _record(
        "no-gold",
        Facts(crl_mm=9.0, cardiac_activity=False),
        Facts(crl_mm=9.0, cardiac_activity=False),
        Determination.DIAGNOSTIC_OF_LOSS,
        None,
    )
    assert determination_flip_analysis([rec]).total == 0
