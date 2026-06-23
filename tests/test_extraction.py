"""Tests for the provider-agnostic extraction layer."""

import json

import pytest

from epl_cds.contracts import Facts
from epl_cds.extraction import PROMPT_VERSION, render_extraction_prompt
from epl_cds.extraction.extractor import ExtractionError, extract_facts


def test_prompt_includes_note_and_schema():
    prompt = render_extraction_prompt("MSD 30 mm, no embryo.")
    assert "MSD 30 mm, no embryo." in prompt
    assert "crl_mm" in prompt
    assert PROMPT_VERSION  # exists / non-empty


def test_extract_parses_clean_json():
    payload = {"crl_mm": 7.0, "cardiac_activity": False, "embryo_visible": True}
    facts = extract_facts("note", lambda _: json.dumps(payload))
    assert facts == Facts(crl_mm=7.0, cardiac_activity=False, embryo_visible=True)


def test_extract_tolerates_surrounding_text():
    raw = 'Here is the JSON:\n{"msd_mm": 25, "embryo_visible": false}\nDone.'
    facts = extract_facts("note", lambda _: raw)
    assert facts.msd_mm == 25.0
    assert facts.embryo_visible is False


def test_extract_ignores_unknown_keys():
    raw = json.dumps({"crl_mm": 5, "impression": "loss", "foo": 1})
    facts = extract_facts("note", lambda _: raw)
    assert facts.crl_mm == 5.0


def test_extract_rejects_non_json():
    with pytest.raises(ExtractionError):
        extract_facts("note", lambda _: "no json here")


def test_extract_rejects_wrong_type_for_bool_field():
    raw = json.dumps({"cardiac_activity": "yes"})
    with pytest.raises(ExtractionError):
        extract_facts("note", lambda _: raw)


def test_extract_null_is_none():
    raw = json.dumps({"crl_mm": None, "cardiac_activity": None})
    facts = extract_facts("note", lambda _: raw)
    assert facts.crl_mm is None
    assert facts.cardiac_activity is None
