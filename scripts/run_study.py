#!/usr/bin/env python3
"""Batch-evaluation harness for the EPL-CDS study.

Runs a gold-labeled corpus through extraction -> deterministic engine, writes an
append-only JSONL log, and prints both study arms plus the determination-flip
report (extraction errors that changed the engine's output).

    python scripts/run_study.py [CORPUS.jsonl]

Provider selection:
  * default: an offline stub that "extracts" the gold facts verbatim, so the
    pipeline runs deterministically with no API key (Arm 1 is perfect by
    construction; the real signal needs a real model).
  * a real model: set EPL_LLM_PROVIDER (e.g. `ollama`) — or USE_LLM=1 with a
    configured provider — to extract with your model instead.

      EPL_LLM_PROVIDER=ollama EPL_LLM_MODEL=gemma3 python scripts/run_study.py
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from epl_cds.contracts import Facts
from epl_cds.extraction.providers import default_llm_fn_from_env
from epl_cds.knowledge import load_ruleset
from epl_cds.pipeline import run_case
from epl_cds.study.corpus import DEFAULT_EXAMPLE_CORPUS, load_cases
from epl_cds.study.log import append_record
from epl_cds.study.metrics import (
    arm1_extraction_accuracy,
    arm2_reasoning_accuracy,
    determination_flip_analysis,
)


def _echo_llm(facts: Facts):
    """An offline stub that returns the gold facts as JSON (perfect extraction)."""
    payload = json.dumps(asdict(facts))
    return lambda _prompt: payload


def _pct(x: float | None) -> str:
    return "  n/a" if x is None else f"{x * 100:5.1f}%"


def main(argv: list[str]) -> int:
    corpus_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_EXAMPLE_CORPUS
    cases = load_cases(corpus_path)
    ruleset = load_ruleset()

    real_llm = default_llm_fn_from_env() if os.environ.get("USE_LLM") != "0" else None
    if real_llm is not None:
        model = os.environ.get("EPL_LLM_MODEL") or os.environ.get("EPL_LLM_PROVIDER", "provider")
        mode = f"real model: {model}"
    else:
        model = "offline-stub"
        mode = "offline stub (extracts gold facts verbatim)"

    print(f"Ruleset {ruleset.version} — {ruleset.status.strip()}")
    print(f"Corpus:     {corpus_path}  ({len(cases)} cases)")
    print(f"Extraction: {mode}\n")

    log_path = Path("data/case_log.jsonl")
    if log_path.exists():
        log_path.unlink()

    records = []
    for c in cases:
        llm_fn = real_llm if real_llm is not None else _echo_llm(c.gold_facts)
        rec = run_case(
            c.case_id,
            c.note,
            llm_fn=llm_fn,
            ruleset=ruleset,
            extractor_model=model,
            gold_facts=c.gold_facts,
            adjudicated_determination=c.adjudicated_determination,
        )
        append_record(log_path, rec)
        records.append(rec)
        flag = "" if rec.result.determination == rec.gold_determination else "  <- FLIP"
        print(f"  {rec.case_id:8}  {rec.result.determination.value:20}"
              f"  [{', '.join(rec.result.fired_rule_ids) or '-'}]{flag}")

    print(f"\nWrote {len(records)} records to {log_path}")
    _report(records)
    return 0


def _report(records: list) -> None:
    arm1 = arm1_extraction_accuracy(records)
    arm2 = arm2_reasoning_accuracy(records)
    flips = determination_flip_analysis(records)

    print("\n── Arm 1 · extraction accuracy (LLM facts vs manual abstraction) ──")
    print(f"  overall per-fact: {_pct(arm1.overall_accuracy)}  over {arm1.cases_scored} cases")
    for name, score in arm1.by_field.items():
        if score.total == 0:
            continue
        miss = f"  ✗{len(score.mismatches)}" if score.mismatches else ""
        print(f"    {name:30} {_pct(score.accuracy)}  ({score.correct}/{score.total}){miss}")

    print("\n── Arm 2 · reasoning accuracy (engine vs expert adjudication) ──")
    print(f"  determination:   {_pct(arm2.accuracy)}  over {arm2.total} cases")
    off = {k: v for k, v in arm2.confusion.items() if k[0] != k[1]}
    for (adj, eng), n in off.items():
        print(f"    MISMATCH adjudicated={adj} engine={eng}: {n}")

    print("\n── Extraction-driven determination flips ──")
    print(f"  flips: {flips.flip_count}/{flips.total}  (agreement {_pct(flips.agreement_rate)})")
    for f in flips.flips:
        print(f"    {f.case_id}: gold→{f.from_gold}  but extracted→{f.to_extracted}")

    if arm1.overall_accuracy == 1.0 and flips.flip_count == 0:
        print("\nNote: perfect Arm 1 / zero flips is expected with the offline stub.")
        print("Run with a real model (EPL_LLM_PROVIDER=ollama) to measure true extraction error.")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
