"""Tests for the gold-case corpus loader and the shipped example corpus."""

import json
from dataclasses import asdict

import pytest

from epl_cds.contracts import Facts
from epl_cds.knowledge import load_ruleset
from epl_cds.pipeline import run_case
from epl_cds.study.corpus import CorpusError, load_cases
from epl_cds.study.metrics import (
    arm2_reasoning_accuracy,
    determination_flip_analysis,
)


def _echo_llm(facts: Facts):
    payload = json.dumps(asdict(facts))
    return lambda _: payload


def test_example_corpus_loads():
    cases = load_cases()
    assert len(cases) == 12
    ex001 = next(c for c in cases if c.case_id == "ex-001")
    assert ex001.gold_facts.crl_mm == 9.0
    assert ex001.adjudicated_determination.value == "diagnostic_of_loss"


def test_corpus_rejects_unknown_field(tmp_path):
    p = tmp_path / "bad.jsonl"
    p.write_text(json.dumps({"case_id": "x", "note": "n", "gold_facts": {"bogus": 1}}) + "\n")
    with pytest.raises(CorpusError):
        load_cases(p)


def test_corpus_rejects_bad_determination(tmp_path):
    p = tmp_path / "bad.jsonl"
    p.write_text(
        json.dumps({"case_id": "x", "note": "n", "adjudicated_determination": "loss"}) + "\n"
    )
    with pytest.raises(CorpusError):
        load_cases(p)


def test_example_corpus_is_engine_consistent():
    """Each case's expert label must equal the engine's verdict on its gold
    facts — otherwise either the label or the engine encoding is wrong. With a
    stub that extracts the gold facts verbatim, Arm 2 is perfect and there are
    zero determination flips. This guards the example data against mislabeling.
    """
    ruleset = load_ruleset()
    records = [
        run_case(
            c.case_id,
            c.note,
            llm_fn=_echo_llm(c.gold_facts),
            ruleset=ruleset,
            gold_facts=c.gold_facts,
            adjudicated_determination=c.adjudicated_determination,
        )
        for c in load_cases()
    ]
    arm2 = arm2_reasoning_accuracy(records)
    assert arm2.accuracy == 1.0, f"mislabeled case(s): {arm2.confusion}"
    assert determination_flip_analysis(records).flip_count == 0
