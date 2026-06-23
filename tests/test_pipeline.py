"""End-to-end pipeline + study-layer tests, all offline."""

from epl_cds.contracts import Determination
from epl_cds.knowledge import load_ruleset
from epl_cds.pipeline import run_case
from epl_cds.study.log import append_record, read_log
from epl_cds.study.metrics import arm1_extraction_accuracy, arm2_reasoning_accuracy
from tests.fixtures import DEMO_CASES, make_stub_llm


def _run_all(ruleset):
    records = []
    for case in DEMO_CASES:
        rec = run_case(
            case.case_id,
            case.note,
            llm_fn=make_stub_llm(case.facts),
            ruleset=ruleset,
            extractor_model="stub-llm",
            gold_facts=case.gold_facts,
            adjudicated_determination=case.adjudicated_determination,
        )
        records.append(rec)
    return records


def test_pipeline_produces_traced_record():
    ruleset = load_ruleset()
    case = DEMO_CASES[0]
    rec = run_case(
        case.case_id, case.note, llm_fn=make_stub_llm(case.facts), ruleset=ruleset
    )
    assert rec.case_id == case.case_id
    assert rec.ruleset_version == "v1"
    assert rec.prompt_version  # pinned
    assert rec.created_at  # timestamped
    assert rec.note is None  # not stored by default


def test_pipeline_matches_adjudication_on_demo_panel():
    # Arm 2 should be perfect by construction on the synthetic panel.
    ruleset = load_ruleset()
    records = _run_all(ruleset)
    arm2 = arm2_reasoning_accuracy(records)
    assert arm2.total == len(DEMO_CASES)
    assert arm2.accuracy == 1.0


def test_arm1_perfect_when_stub_matches_gold():
    # The stub 'extracts' exactly the gold facts, so Arm 1 is perfect here.
    ruleset = load_ruleset()
    records = _run_all(ruleset)
    arm1 = arm1_extraction_accuracy(records)
    assert arm1.cases_scored == len(DEMO_CASES)
    assert arm1.overall_accuracy == 1.0


def test_log_roundtrip(tmp_path):
    ruleset = load_ruleset()
    records = _run_all(ruleset)
    log_path = tmp_path / "case_log.jsonl"
    for rec in records:
        append_record(log_path, rec)

    loaded = read_log(log_path)
    assert len(loaded) == len(records)
    assert loaded[0].result.determination == records[0].result.determination
    assert loaded[0].facts == records[0].facts
    assert loaded[0].adjudicated_determination == records[0].adjudicated_determination


def test_arm1_detects_extraction_miss():
    # Feed the engine-correct gold but a stub that mis-extracts one field.
    from epl_cds.contracts import Facts

    ruleset = load_ruleset()
    wrong = Facts(crl_mm=9.0, cardiac_activity=True, embryo_visible=True)  # flipped HB
    gold = Facts(crl_mm=9.0, cardiac_activity=False, embryo_visible=True)
    rec = run_case(
        "miss-001",
        "note",
        llm_fn=make_stub_llm(wrong),
        ruleset=ruleset,
        gold_facts=gold,
    )
    arm1 = arm1_extraction_accuracy([rec])
    assert arm1.by_field["cardiac_activity"].accuracy == 0.0
    assert arm1.by_field["crl_mm"].accuracy == 1.0
