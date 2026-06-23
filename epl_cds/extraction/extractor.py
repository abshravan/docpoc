"""Turn a clinical note into structured Facts via an injected llm_fn.

The model returns JSON text; this module parses it defensively into a Facts
instance. Only keys defined on Facts are accepted — extra keys are ignored,
missing keys default to None.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from epl_cds.contracts import Facts, LLMFn
from epl_cds.extraction.prompts import render_extraction_prompt

_BOOL_FIELDS = {
    "cardiac_activity",
    "embryo_visible",
    "yolk_sac_visible",
    "amnion_visible",
}
_INT_FIELDS = {
    "days_since_sac_without_yolk",
    "days_since_sac_with_yolk",
    "days_since_lmp",
}
_FLOAT_FIELDS = {"crl_mm", "msd_mm", "yolk_sac_diameter_mm"}


class ExtractionError(ValueError):
    """Raised when the model output cannot be parsed into Facts."""


def extract_facts(note: str, llm_fn: LLMFn) -> Facts:
    """Render the prompt, call the model, and parse its JSON into Facts."""
    prompt = render_extraction_prompt(note)
    raw = llm_fn(prompt)
    payload = _parse_json_object(raw)
    return _coerce_facts(payload)


def _parse_json_object(raw: str) -> dict[str, Any]:
    """Parse a JSON object from raw model output, tolerating surrounding text."""
    if not isinstance(raw, str):
        raise ExtractionError(f"llm_fn must return a string, got {type(raw)!r}")
    text = raw.strip()
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ExtractionError("no JSON object found in model output")
        try:
            obj = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise ExtractionError(f"invalid JSON in model output: {exc}") from exc
    if not isinstance(obj, dict):
        raise ExtractionError("model output JSON is not an object")
    return obj


def _coerce_facts(payload: dict[str, Any]) -> Facts:
    known = set(Facts.field_names())
    kwargs: dict[str, Any] = {}
    for key, value in payload.items():
        if key not in known:
            continue  # ignore anything not in the contract
        kwargs[key] = _coerce_value(key, value)
    return Facts(**kwargs)


def _coerce_value(key: str, value: Any) -> Optional[Any]:
    if value is None:
        return None
    if key in _BOOL_FIELDS:
        if isinstance(value, bool):
            return value
        raise ExtractionError(f"field {key!r} expected boolean or null, got {value!r}")
    if key in _INT_FIELDS:
        if isinstance(value, bool):
            raise ExtractionError(f"field {key!r} expected integer or null, got bool")
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        raise ExtractionError(f"field {key!r} expected integer or null, got {value!r}")
    if key in _FLOAT_FIELDS:
        if isinstance(value, bool):
            raise ExtractionError(f"field {key!r} expected number or null, got bool")
        if isinstance(value, (int, float)):
            return float(value)
        raise ExtractionError(f"field {key!r} expected number or null, got {value!r}")
    return value  # pragma: no cover - all known keys are typed above
