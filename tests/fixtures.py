"""Offline test fixtures: a deterministic stub LLM and synthetic demo cases.

No network, no API key. `make_stub_llm` returns a fixed Facts payload regardless
of the prompt, which lets the pipeline run end-to-end deterministically while
still exercising the real prompt rendering and JSON parsing path.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Optional

from epl_cds.contracts import Determination, Facts, LLMFn


def make_stub_llm(facts: Facts) -> LLMFn:
    """Return an llm_fn that always emits `facts` as JSON, ignoring the prompt."""
    payload = json.dumps(asdict(facts))

    def _stub(prompt: str) -> str:
        return payload

    return _stub


def stub_llm(prompt: str) -> str:
    """A default stub that extracts nothing (all facts null)."""
    return json.dumps(asdict(Facts()))


@dataclass(frozen=True)
class DemoCase:
    """A synthetic case bundling the note, the facts the stub should 'extract',
    and the study references for both arms."""

    case_id: str
    note: str
    facts: Facts
    gold_facts: Facts
    adjudicated_determination: Determination


# A small synthetic panel covering the main tiers. All measurements are
# fictional and for pipeline demonstration only.
DEMO_CASES: tuple[DemoCase, ...] = (
    DemoCase(
        case_id="demo-001",
        note=(
            "Transvaginal US. Single intrauterine gestational sac. Embryo present, "
            "CRL 9 mm. No cardiac activity identified."
        ),
        facts=Facts(crl_mm=9.0, cardiac_activity=False, embryo_visible=True),
        gold_facts=Facts(crl_mm=9.0, cardiac_activity=False, embryo_visible=True),
        adjudicated_determination=Determination.DIAGNOSTIC_OF_LOSS,
    ),
    DemoCase(
        case_id="demo-002",
        note=(
            "Intrauterine gestational sac, mean sac diameter 28 mm. No yolk sac or "
            "embryo identified within the sac."
        ),
        facts=Facts(msd_mm=28.0, embryo_visible=False, yolk_sac_visible=False),
        gold_facts=Facts(msd_mm=28.0, embryo_visible=False, yolk_sac_visible=False),
        adjudicated_determination=Determination.DIAGNOSTIC_OF_LOSS,
    ),
    DemoCase(
        case_id="demo-003",
        note=(
            "Early intrauterine gestational sac, MSD 18 mm, no embryo seen. "
            "Follow-up recommended."
        ),
        facts=Facts(msd_mm=18.0, embryo_visible=False),
        gold_facts=Facts(msd_mm=18.0, embryo_visible=False),
        adjudicated_determination=Determination.SUSPICIOUS_FOR_LOSS,
    ),
    DemoCase(
        case_id="demo-004",
        note=(
            "Live intrauterine pregnancy. Embryo CRL 6 mm with cardiac activity "
            "present."
        ),
        facts=Facts(crl_mm=6.0, cardiac_activity=True, embryo_visible=True),
        gold_facts=Facts(crl_mm=6.0, cardiac_activity=True, embryo_visible=True),
        adjudicated_determination=Determination.NO_CRITERIA_MET,
    ),
)
