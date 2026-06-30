"""LLM diagnostic *baseline* — a research comparison, NOT part of the CDS.

============================ READ THIS FIRST ============================
This module asks an LLM to render a determination directly from the note. Its
output is a **non-authoritative research baseline only**. It exists to quantify
and demonstrate the gap between an unconstrained model and the deterministic
engine — i.e. to justify the firewall, not to weaken it.

INVARIANTS (do not break):
  * Nothing here is imported by `epl_cds/reasoning/` (which stays pure).
  * Nothing here feeds a `CaseRecord.result` / determination or the pipeline.
  * It lives under `extraction/` so that ALL LLM usage stays in one package,
    per CLAUDE.md ("the LLM lives in exactly one place: epl_cds/extraction/").
The authoritative determination always comes from `reasoning.evaluate`.
========================================================================
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from epl_cds.contracts import BaselineOpinion, Determination, LLMFn

# Bump on any change to the baseline prompt below.
BASELINE_PROMPT_VERSION = "b1"

_VALID = {d.value for d in Determination}

_BASELINE_TEMPLATE = """You are assisting a research study that compares an unconstrained language
model against a deterministic rule engine for early pregnancy loss. For this
baseline, give your OWN best impression directly from the report below.

Respond with a single JSON object and nothing else:
{{
  "determination": "diagnostic_of_loss" | "suspicious_for_loss" | "no_criteria_met",
  "rationale": "one or two sentences"
}}

Definitions:
- "diagnostic_of_loss": findings you believe establish early pregnancy loss.
- "suspicious_for_loss": concerning but not definitive; follow-up warranted.
- "no_criteria_met": neither bar is met on the documented findings.

REPORT:
\"\"\"
{note}
\"\"\"
"""


def render_baseline_prompt(note: str) -> str:
    return _BASELINE_TEMPLATE.format(note=note)


def llm_baseline_opinion(note: str, llm_fn: LLMFn, *, model: str = "unknown") -> BaselineOpinion:
    """Ask the model for a direct determination (research baseline only)."""
    prompt = render_baseline_prompt(note)
    raw = llm_fn(prompt)
    determination, rationale = _parse(raw)
    return BaselineOpinion(
        determination=determination,
        rationale=rationale,
        raw=raw if isinstance(raw, str) else str(raw),
        model=model,
        prompt_version=BASELINE_PROMPT_VERSION,
    )


def _parse(raw: Any) -> tuple[Optional[Determination], str]:
    if not isinstance(raw, str):
        return None, "Model output was not text."
    text = raw.strip()
    obj: Optional[dict] = None
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            obj = parsed
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, dict):
                    obj = parsed
            except json.JSONDecodeError:
                obj = None
    if obj is None:
        return None, text[:300]

    value = obj.get("determination")
    rationale = str(obj.get("rationale", "")).strip()
    if isinstance(value, str) and value in _VALID:
        return Determination(value), rationale
    return None, rationale or f"Unrecognized determination: {value!r}"
