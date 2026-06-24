# ARCHITECTURE

EPL-CDS is a research/validation tool for **early pregnancy loss (EPL)**. Its
defining property is a firewall: **the LLM extracts facts; a deterministic
engine makes the diagnosis.** This document specifies the layers, the data
contract, and the invariants that keep that firewall intact.

## Layering

Every layer imports ONLY from `epl_cds/contracts.py`, never from a sibling.

```
                 ┌─────────────────────────────────────────────┐
   free text ──▶ │ extraction/   (the ONLY LLM)                 │ ──▶ Facts
                 └─────────────────────────────────────────────┘
                                     │ Facts
                                     ▼
                 ┌─────────────────────────────────────────────┐
   ruleset  ───▶ │ reasoning/    (pure, deterministic engine)   │ ──▶ DeterminationResult
                 └─────────────────────────────────────────────┘
                                     │
                                     ▼
                 ┌─────────────────────────────────────────────┐
                 │ study/        (CaseRecord, log, metrics)     │
                 └─────────────────────────────────────────────┘

   knowledge/  loads + validates + freezes the versioned ruleset (no LLM)
   pipeline.py orchestrates extraction → reasoning → CaseRecord
   contracts.py holds every cross-layer dataclass
```

| Layer        | Responsibility                                              | May contain LLM? | May call network? |
|--------------|-------------------------------------------------------------|------------------|-------------------|
| `knowledge/` | load/validate/freeze the versioned ruleset                  | no               | no                |
| `extraction/`| text → `Facts` via injected `llm_fn`                         | **yes (only here)** | only via injected `llm_fn` |
| `reasoning/` | `(Facts, Ruleset) → DeterminationResult`, pure function     | **never**        | **never**         |
| `study/`     | `CaseRecord`, append-only log, two-arm metrics              | no               | no                |
| `pipeline.py`| orchestration + provenance stamping                         | no (delegates)   | no                |

## The contract (`contracts.py`)

- `Facts` — all-Optional structured observations. `None` means *not documented*;
  the engine must never guess a `None`.
- `Rule` / `Ruleset` — frozen, versioned knowledge. `Rule.params` holds the
  numeric thresholds; the engine holds the comparison logic.
- `DeterminationResult` — `determination` tier + `fired_rule_ids` + ruleset
  version + human-readable rationale.
- `Determination` — `DIAGNOSTIC_OF_LOSS` / `SUSPICIOUS_FOR_LOSS` /
  `NO_CRITERIA_MET`. There is deliberately no "viable" tier.
- `CaseRecord` — one fully traced case, pinning extractor model, prompt version,
  and ruleset version for reproducibility, plus optional Arm-1/Arm-2 references.
- `LLMFn` — `(prompt: str) -> str`. The single injection point for any model.

## The engine (`reasoning/engine.py`)

`evaluate(facts, ruleset)` iterates every rule, looks up its evaluator in
`RULE_EVALUATORS`, and collects which fired. **Tier precedence:** if any
`diagnostic` rule fires, the result is `DIAGNOSTIC_OF_LOSS` and suspicious rules
are not reported — a diagnostic finding is never downgraded (specificity guard).
A ruleset rule with no registered evaluator raises immediately: knowledge and
code are never allowed to drift silently.

Thresholds live in YAML; the engine supplies only the fixed comparison shape
(`>=`, `<`, ranges). To add a criterion: add a rule to the YAML **and** register
an evaluator. Never edit a threshold to make a test pass.

## Knowledge (`knowledge/`)

`load_ruleset()` reads `epl_ruleset_v1.yaml`, runs the structural
`validate_ruleset_data()` (tiers, non-empty citations, unique ids, positive
thresholds), then freezes it into a `Ruleset`. The validator checks *structure*,
not clinical correctness — only an expert can confirm a threshold value, which
is why every rule carries `verify: true` and a `citation`.

## The two-arm study (`study/metrics.py`)

Kept strictly separable:

- **Arm 1 — extraction accuracy:** `arm1_extraction_accuracy` scores extracted
  `Facts` against gold `Facts`, per field. This is where the real signal is.
- **Arm 2 — reasoning accuracy:** `arm2_reasoning_accuracy` scores the engine's
  determination against expert adjudication. Should approach 100% by
  construction; any miss is a rule-encoding bug.

Neither function blends the arms.

## Presentation (`webapp/`, optional)

A thin Flask demo that consumes only the public API (`pipeline`, `extraction`,
`reasoning`, `knowledge`) — it adds no clinical logic. Its three panels mirror
the firewall: `/api/extract` runs the LLM (optional, needs a provider),
`/api/evaluate` runs the pure engine (always available). The extracted facts are
human-editable between the two, so the model never reaches the determination
unmediated. Real providers live in `extraction/providers.py` (lazy import,
optional dependency) and are never touched by the test suite.

## Reproducibility & safety invariants

1. The engine is a pure function of `(Facts, Ruleset)` — no LLM, no randomness,
   no I/O, no network.
2. The LLM lives only in `extraction/`, behind an injected `llm_fn`; tests run
   offline against a stub.
3. Every `CaseRecord` pins `extractor_model`, `prompt_version`,
   `ruleset_version`. Changing the prompt bumps `PROMPT_VERSION`; changing a
   threshold bumps the ruleset `version`.
4. No PHI ingestion until all `gates` in `config/study_config.yaml` are true.
5. "Suspicious" recommends follow-up only — it must never escalate to treatment.
