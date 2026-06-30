"""Orchestrator: note -> (LLM extraction) -> facts -> (deterministic engine)
-> determination -> traced CaseRecord.

This is the only place the two halves meet. The firewall holds: extraction
produces Facts, the engine consumes Facts; the engine never sees the note or
the model. `llm_fn` is injected so the whole pipeline runs offline in tests.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from epl_cds.contracts import CaseRecord, Determination, Facts, LLMFn, Ruleset
from epl_cds.extraction.extractor import extract_facts
from epl_cds.extraction.prompts import PROMPT_VERSION
from epl_cds.reasoning.engine import evaluate


def run_case(
    case_id: str,
    note: str,
    *,
    llm_fn: LLMFn,
    ruleset: Ruleset,
    extractor_model: str = "stub",
    store_note: bool = False,
    gold_facts: Optional[Facts] = None,
    adjudicated_determination: Optional[Determination] = None,
) -> CaseRecord:
    """Run one case end-to-end and return a fully-traced CaseRecord.

    `store_note` defaults to False: the raw note is NOT persisted unless asked,
    to avoid retaining source text before study de-identification gates pass.
    `gold_facts` / `adjudicated_determination` are optional study references
    (Arm 1 / Arm 2) and never influence the determination.
    """
    facts = extract_facts(note, llm_fn)
    result = evaluate(facts, ruleset)

    # If a manual abstraction is supplied, also run the engine on those gold
    # facts. This is still the deterministic engine, never the LLM — it lets the
    # study measure extraction errors that would have flipped the determination.
    gold_determination = (
        evaluate(gold_facts, ruleset).determination if gold_facts is not None else None
    )

    return CaseRecord(
        case_id=case_id,
        facts=facts,
        result=result,
        extractor_model=extractor_model,
        prompt_version=PROMPT_VERSION,
        ruleset_version=ruleset.version,
        created_at=datetime.now(timezone.utc).isoformat(),
        note=note if store_note else None,
        gold_facts=gold_facts,
        adjudicated_determination=adjudicated_determination,
        gold_determination=gold_determination,
    )
