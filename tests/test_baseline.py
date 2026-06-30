"""Tests for the LLM research baseline — and that it stays firewalled."""

import json
from pathlib import Path

from epl_cds.contracts import Determination
from epl_cds.extraction.baseline import (
    BASELINE_PROMPT_VERSION,
    llm_baseline_opinion,
    render_baseline_prompt,
)


def _llm(payload):
    return lambda _: json.dumps(payload)


def test_baseline_parses_known_tier():
    op = llm_baseline_opinion(
        "CRL 9mm no FHR",
        _llm({"determination": "diagnostic_of_loss", "rationale": "no cardiac"}),
        model="gemma3",
    )
    assert op.determination == Determination.DIAGNOSTIC_OF_LOSS
    assert op.rationale == "no cardiac"
    assert op.model == "gemma3"
    assert op.prompt_version == BASELINE_PROMPT_VERSION


def test_baseline_unknown_tier_is_none():
    op = llm_baseline_opinion("x", _llm({"determination": "loss", "rationale": "r"}))
    assert op.determination is None


def test_baseline_non_json_is_none():
    op = llm_baseline_opinion("x", lambda _: "I think this is a miscarriage.")
    assert op.determination is None
    assert op.raw


def test_baseline_prompt_includes_note():
    assert "CRL 9mm" in render_baseline_prompt("CRL 9mm")


def test_reasoning_never_imports_the_baseline_or_an_llm():
    # The deterministic engine must remain a pure function of (facts, ruleset).
    engine_src = Path("epl_cds/reasoning/engine.py").read_text()
    for forbidden in ("baseline", "llm", "anthropic", "ollama", "requests", "urllib"):
        assert forbidden not in engine_src.lower(), f"reasoning must not reference {forbidden!r}"
