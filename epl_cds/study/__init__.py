"""Study layer: per-case records, append-only log, two-arm metrics.

Keeps the two study arms separable (see CLAUDE.md):
  Arm 1 — extraction accuracy (LLM facts vs manual abstraction), per-fact.
  Arm 2 — reasoning accuracy (engine determination vs expert adjudication).
"""

from epl_cds.study.log import append_record, read_log
from epl_cds.study.metrics import arm1_extraction_accuracy, arm2_reasoning_accuracy
from epl_cds.study.records import record_to_dict

__all__ = [
    "append_record",
    "read_log",
    "record_to_dict",
    "arm1_extraction_accuracy",
    "arm2_reasoning_accuracy",
]
