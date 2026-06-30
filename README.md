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
    providers.py        optional real llm_fn adapters (Anthropic, Ollama/Gemma)
    baseline.py         NON-authoritative LLM opinion (research comparison only)
  reasoning/            deterministic engine: (Facts, Ruleset) -> Determination
  study/                CaseRecord, append-only JSONL log, two-arm metrics
  pipeline.py           orchestrator (extraction -> reasoning -> record)
webapp/                 Flask JSON/SSE API (+ AG-UI extract stream, Jinja fallback)
frontend/               React + TS + Tailwind + shadcn/ui SPA (AG-UI client)
config/study_config.yaml safety gates (IRB, de-identification, sign-off)
scripts/run_study.py    offline demo
tests/                  boundary tests pinning clinical thresholds
```

## Clinician-facing demo UI

A React (Vite + TypeScript + Tailwind + shadcn/ui) front end with a Flask JSON/SSE
API backend. Three panels make the firewall visible:

1. **Extraction (LLM)** — paste a report; the model proposes structured facts only,
   streamed to the UI over the **AG-UI protocol** (`@ag-ui/core` events via SSE).
2. **Verify facts (clinician)** — an editable form bound to the AG-UI agent state;
   the engine sees only what you confirm.
3. **Conclusions** — the **deterministic engine** determination (authoritative,
   with fired-rule citations) shown next to a **non-authoritative LLM baseline**
   ("what an unconstrained model would say — not used for the decision"), with a
   badge flagging when the two disagree.

The LLM baseline is a research comparison only; it never feeds the engine or the
CaseRecord determination (`epl_cds/extraction/baseline.py`).

### Run it

Backend (API) + frontend (Vite dev server) in two terminals:

```bash
# 1) API backend on :5000  — pick a provider, or none for manual-entry mode
EPL_LLM_PROVIDER=ollama EPL_LLM_MODEL=gemma3 python -m webapp   # local Gemma via Ollama
#   EPL_OLLAMA_HOST defaults to http://localhost:11434
#   ANTHROPIC_API_KEY=... python -m webapp                      # or a hosted provider

# 2) Frontend dev server on :5173 (proxies /api -> :5000)
cd frontend && npm install && npm run dev
```

Open **http://localhost:5173**. With no provider configured, panel 1 is disabled
and you enter facts manually in panel 2 to drive the engine offline.

Single-process production (Flask serves the built SPA):

```bash
cd frontend && npm run build && cd ..
EPL_SERVE_FRONTEND=1 EPL_LLM_PROVIDER=ollama python -m webapp   # serves UI + API on :5000
```

There is also a dependency-free Jinja fallback UI at `/` when `EPL_SERVE_FRONTEND`
is unset (handy for a quick look without Node). It is a research demo — clearly
labeled decision support, not a diagnosis or a medical device.

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
