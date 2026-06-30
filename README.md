# EPL-CDS

LLM-assisted clinical decision support for **early pregnancy loss (EPL)**, built
as a single-site **research/validation study** — not a production medical device.

> **The one rule:** the LLM extracts facts; a deterministic engine makes the
> diagnosis. See [`CLAUDE.md`](CLAUDE.md) and [`ARCHITECTURE.md`](ARCHITECTURE.md).

## ⚠️ Clinical-knowledge status

The thresholds in `epl_cds/knowledge/epl_ruleset_v1.yaml` are transcribed from
the SRU 2013 consensus criteria (Doubilet et al., *NEJM* 2013;369:1443) and are
marked **`verify: true` / UNVERIFIED**. They MUST be confirmed by a domain expert
before any study use. Do not edit a threshold to make a test pass.

## Quickstart

```bash
pip install -e .            # install the package (and PyYAML)
pip install -e ".[dev]"     # + pytest + Flask (for the webapp tests)
pytest -q                   # engine boundary tests + layer tests
python scripts/run_study.py # offline batch demo (deterministic stub, no API key)
python -m webapp            # clinician-facing demo UI at http://127.0.0.1:5000
```

## Layout

```
epl_cds/
  contracts.py          cross-layer dataclasses (the only shared import)
  knowledge/            frozen versioned ruleset + loader + validator
  extraction/           the ONLY LLM: text -> Facts (provider-agnostic llm_fn)
  reasoning/            deterministic engine: (Facts, Ruleset) -> Determination
  study/                CaseRecord, append-only JSONL log, two-arm metrics
  pipeline.py           orchestrator (extraction -> reasoning -> record)
config/study_config.yaml safety gates (IRB, de-identification, sign-off)
scripts/run_study.py    offline demo
tests/                  boundary tests pinning clinical thresholds
```

## Clinician-facing demo UI

`python -m webapp` serves a three-panel page that makes the firewall visible:

1. **Extraction (LLM)** — paste a report; the model proposes structured facts only.
2. **Verify facts (clinician)** — an editable form; the engine sees only what you confirm.
3. **Determination (deterministic)** — the tier, the criteria that fired with
   their citations, and the rationale. No AI in this step.

It runs offline: with no provider configured, panel 1 is disabled and you enter
facts manually in panel 2 to drive the engine. To enable extraction, install and
configure a provider:

```bash
# Local model via Ollama (e.g. Gemma) — no API key, no extra Python deps:
EPL_LLM_PROVIDER=ollama EPL_LLM_MODEL=gemma3 python -m webapp
# EPL_OLLAMA_HOST defaults to http://localhost:11434

# Or a hosted provider:
pip install -e ".[webapp,anthropic]"
ANTHROPIC_API_KEY=... python -m webapp        # or EPL_LLM_PROVIDER=anthropic
EPL_LLM_MODEL=...                              # optional model override
```

The UI is a research demo — clearly labeled decision support, not a diagnosis or
a medical device. "Suspicious" recommends follow-up only.

## Plugging in a real model

Extraction is provider-agnostic. Implement any `llm_fn` matching
`contracts.LLMFn` — `(prompt: str) -> str` returning JSON — and pass it to
`pipeline.run_case(..., llm_fn=...)`. Tests and the demo use an offline stub, so
no provider client is bundled.

```python
from epl_cds.knowledge import load_ruleset
from epl_cds.pipeline import run_case

def my_llm_fn(prompt: str) -> str:
    ...  # call your provider, return the model's JSON text

record = run_case("case-1", report_text, llm_fn=my_llm_fn, ruleset=load_ruleset())
print(record.result.determination, record.result.rationale)
```

## Scope & safety

Decision **support**, never autonomous diagnosis. The "suspicious" tier
recommends follow-up only. No real patient data until every gate in
`config/study_config.yaml` is satisfied.
