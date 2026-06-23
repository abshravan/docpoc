# CLAUDE.md

Project guidance for Claude Code working in this repository. Read this fully
before making changes.

## What this is

EPL-CDS: an LLM-assisted clinical decision support tool for **early pregnancy
loss (EPL)**, built as a single-site **research/validation study**, not a
production medical device. The deliverable is defensible accuracy evidence, not
a deployed app.

## The one rule that governs everything

> **The LLM extracts facts. A deterministic engine makes the diagnosis.**

The EPL diagnostic criteria (SRU/ACOG/ACR) are fixed numeric thresholds
engineered for ~100% specificity, because a false-positive loss diagnosis can
end a viable pregnancy. A probabilistic model must NEVER make or influence the
diagnostic call.

**Hard constraints — do not violate without explicit human approval:**
- No LLM, no probabilistic logic, and no network call anywhere in
  `epl_cds/reasoning/`. It must stay a pure function of (facts, ruleset).
- The LLM lives in exactly one place: `epl_cds/extraction/`.
- Never edit `epl_cds/knowledge/epl_ruleset_v1.yaml` thresholds to make a test
  pass. The thresholds are clinical truth; a failing test means the code is
  wrong, not the threshold. Threshold changes require expert sign-off and a new
  ruleset version.
- Never invent or alter a clinical criterion from memory. If a criterion is in
  question, stop and ask the human to verify against the cited guideline.

## Architecture (see ARCHITECTURE.md for the full spec)

Layers, each importing ONLY from `epl_cds/contracts.py`, never from a sibling:
- `knowledge/`   frozen versioned ruleset + loader + pre-freeze validator
- `extraction/`  LLM extraction (the only LLM) + versioned prompt
- `reasoning/`   deterministic rule engine
- `study/`       per-case records, append-only log, two-arm metrics
- `pipeline.py`  orchestrator

`contracts.py` holds every cross-layer dataclass. When you add a field that
crosses a layer boundary, put it there — do not create a sibling-to-sibling
import.

## The two-arm study (keep these separable)

- Arm 1 — extraction accuracy: LLM facts vs manual chart abstraction (per-fact).
- Arm 2 — reasoning accuracy: engine determination vs expert adjudication.

Never blend them. Arm 2 should approach 100% by construction; any deviation is a
rule-encoding bug. Arm 1 is where the real signal is. Anything that makes these
two harder to measure independently is a regression.

## How to work

- Read `ARCHITECTURE.md` before structural changes. Read the target layer's
  existing module before editing it.
- TDD for the engine: `tests/test_engine.py` pins clinical thresholds at their
  boundaries (e.g. CRL exactly 7mm = diagnostic, 6.9mm = suspicious). Add a
  failing boundary test before changing engine behavior. Run `pytest -q` after
  every change to reasoning or knowledge.
- Keep extraction testable offline: the `llm_fn` parameter is injectable so the
  pipeline runs against `tests/fixtures.stub_llm` with no API key. Never hardcode
  a real API call into a code path that tests exercise.
- Reproducibility is a feature: every `CaseRecord` pins extractor model + prompt
  version. If you change the prompt, bump `PROMPT_VERSION` in
  `extraction/prompts.py`. If you change thresholds, bump the ruleset `version`.

## Commands

```bash
pip install -e .            # install the package
pytest -q                   # engine boundary tests (run after reasoning/knowledge edits)
python scripts/run_study.py # offline batch demo (deterministic stub, no API key)
USE_LLM=1 ANTHROPIC_API_KEY=... python scripts/run_study.py   # real extraction
```

## Safety / scope guardrails

- This is decision SUPPORT, never autonomous diagnosis. The "suspicious" tier
  recommends follow-up only — it must never escalate to a treatment recommendation.
- No real patient data until the `gates` in `config/study_config.yaml`
  (IRB, de-identification) are satisfied. Do not add code that ingests PHI before then.
- If a task would require giving the LLM the final diagnostic call, weakening the
  extraction/reasoning firewall, or relaxing a specificity-protecting threshold:
  stop and flag it to the human rather than implementing it.

## When unsure

Ask before: changing any clinical threshold, moving the LLM/deterministic
boundary, altering a data contract, or adding a dependency. Prefer a small
focused diff plus a passing test over a large speculative refactor.
