"""Versioned extraction prompt.

If you change the wording or schema below, bump PROMPT_VERSION — every
CaseRecord pins this so results stay reproducible (see CLAUDE.md).
"""

from __future__ import annotations

# Bump on ANY change to the prompt text or fact schema.
PROMPT_VERSION = "p1"

# The exact JSON schema the model must return. Keys mirror contracts.Facts.
# Unknown / not-documented values must be null — the engine treats null as
# "cannot evaluate", never as a guess.
FACT_SCHEMA = """{
  "crl_mm": number | null,                      // crown-rump length in mm
  "cardiac_activity": true | false | null,      // embryonic heartbeat seen?
  "msd_mm": number | null,                       // mean sac diameter in mm
  "embryo_visible": true | false | null,         // any embryo seen?
  "yolk_sac_visible": true | false | null,       // yolk sac seen?
  "yolk_sac_diameter_mm": number | null,         // yolk sac diameter in mm
  "amnion_visible": true | false | null,         // amnion seen?
  "days_since_sac_without_yolk": integer | null, // days since a prior scan that
                                                 //   showed a sac WITHOUT a yolk sac
  "days_since_sac_with_yolk": integer | null,    // days since a prior scan that
                                                 //   showed a sac WITH a yolk sac
  "days_since_lmp": integer | null               // days since last menstrual period
}"""

_PROMPT_TEMPLATE = """You are a clinical data extraction assistant for an early-pregnancy
ultrasound study. Extract ONLY facts that are explicitly stated in the report
below. Do not infer, estimate, or diagnose. If a value is not stated, use null.

Return a single JSON object and nothing else, matching exactly this schema
(comments are for guidance only; do not include them in your output):

{schema}

Rules:
- Use null for anything not explicitly documented.
- Do not convert units; report measurements in millimetres as written.
- "cardiac_activity" is true only if a heartbeat / cardiac motion is reported.
- Never output a determination, impression, or recommendation.

REPORT:
\"\"\"
{note}
\"\"\"
"""


def render_extraction_prompt(note: str) -> str:
    """Render the full extraction prompt for a clinical note/report."""
    return _PROMPT_TEMPLATE.format(schema=FACT_SCHEMA, note=note)
