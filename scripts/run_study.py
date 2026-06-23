#!/usr/bin/env python3
"""Offline batch demo of the EPL-CDS pipeline.

Runs the synthetic demo panel through extraction -> reasoning, writes an
append-only JSONL log, and prints both study-arm metrics. Deterministic and
needs no API key.

    python scripts/run_study.py

With a real provider you would set USE_LLM=1 and inject a real llm_fn; this
script only ships the offline stub so the demo always reproduces.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Allow running from a source checkout without installing.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from epl_cds.knowledge import load_ruleset
from epl_cds.pipeline import run_case
from epl_cds.study.log import append_record
from epl_cds.study.metrics import arm1_extraction_accuracy, arm2_reasoning_accuracy
from tests.fixtures import DEMO_CASES, make_stub_llm


def main() -> int:
    if os.environ.get("USE_LLM") == "1":
        print(
            "USE_LLM=1 is set, but this demo ships only the offline stub. Wire a "
            "real provider-backed llm_fn into run_case() to use a live model.",
            file=sys.stderr,
        )

    ruleset = load_ruleset()
    print(f"Ruleset {ruleset.version} loaded ({len(ruleset.rules)} rules).")
    print(f"  status: {ruleset.status.strip()}\n")

    log_path = Path("data/case_log.jsonl")
    if log_path.exists():
        log_path.unlink()  # fresh demo run

    records = []
    for case in DEMO_CASES:
        rec = run_case(
            case.case_id,
            case.note,
            llm_fn=make_stub_llm(case.facts),
            ruleset=ruleset,
            extractor_model="offline-stub",
            gold_facts=case.gold_facts,
            adjudicated_determination=case.adjudicated_determination,
        )
        append_record(log_path, rec)
        records.append(rec)
        print(
            f"  {rec.case_id}: {rec.result.determination.value:20s} "
            f"[{', '.join(rec.result.fired_rule_ids) or '-'}]"
        )

    print(f"\nWrote {len(records)} records to {log_path}\n")

    arm1 = arm1_extraction_accuracy(records)
    arm2 = arm2_reasoning_accuracy(records)

    print("Arm 1 — extraction accuracy (LLM facts vs manual abstraction):")
    print(f"  overall per-fact accuracy: {_pct(arm1.overall_accuracy)} "
          f"over {arm1.cases_scored} cases")
    print("Arm 2 — reasoning accuracy (engine vs expert adjudication):")
    print(f"  determination accuracy:    {_pct(arm2.accuracy)} "
          f"over {arm2.total} cases")
    print(
        "\nNote: Arm 2 is ~100% by construction; Arm 1 here is perfect only "
        "because the offline stub returns the gold facts verbatim."
    )
    return 0


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.1f}%"


if __name__ == "__main__":
    raise SystemExit(main())
