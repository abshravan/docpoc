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
python scripts/run_study.py # batch-evaluate the example corpus (stub, no API key)
python -m webapp            # clinician-facing demo UI at http://127.0.0.1:5000
```

## Batch evaluation (the study harness)

`scripts/run_study.py` runs a gold-labeled corpus through extraction → engine and
prints both study arms plus the determination-flip report:

- **Arm 1** — per-fact extraction accuracy (LLM facts vs manual abstraction).
- **Arm 2** — determination accuracy (engine vs expert adjudication).
- **Flips** — extraction errors that *changed the engine's output* (the core
  argument for the firewall). Computed by running the engine on the gold facts
  too and comparing — still no LLM in the decision.

```bash
python scripts/run_study.py                       # offline stub (extracts gold verbatim)
python scripts/run_study.py data/cases.jsonl      # your own corpus
EPL_LLM_PROVIDER=ollama EPL_LLM_MODEL=gemma3 \
  python scripts/run_study.py                     # real extraction with local Gemma
```

Corpus format is one JSON object per line — `note`, `gold_facts`, optional
`adjudicated_determination` (see `examples/cases.example.jsonl`). Real corpora
belong under the gitignored `data/` and require the study gates to be satisfied.

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
web/                     Next.js + TS + Tailwind + shadcn/ui frontend (AG-UI client)
config/study_config.yaml safety gates (IRB, de-identification, sign-off)
scripts/run_study.py    offline demo
tests/                  boundary tests pinning clinical thresholds
```

## Clinician-facing UI (`web/`)

A **Next.js + TypeScript + Tailwind + shadcn/ui** front end over the Flask
JSON/SSE API. Four pages, all keeping the firewall visible:

- **Assessment** — upload a scan (OCR) or paste text; the model proposes facts
  (streamed over the **AG-UI protocol**); the clinician verifies; a **guideline
  dropdown** selects the ruleset; **Conclusions** shows the deterministic verdict
  (with citations) beside a non-authoritative **LLM baseline** and a
  disagreement flag; an **advisory chat** discusses the case (never decides).
- **Decision flow** — a grid of every rule/method (grouped by guideline) plus a
  live path-highlighting flowchart.
- **Evidence** — RAG search over uploaded papers, with cited passages.
- **Authoring** — upload a paper → draft a candidate ruleset → clinician sign-off;
  approved thresholds become a selectable guideline, novel criteria are queued as
  non-executable proposals.

### Run it

**Fastest — one-shot setup script** (installs OCR deps, a Python venv, and web deps):

```bash
./scripts/setup-linux.sh     # Debian/Ubuntu/Fedora/Arch
./scripts/setup-macos.sh     # macOS (uses Homebrew)
```

It prints the exact run commands when done. Or set it up manually —
backend (API) + frontend (Next.js dev server) in two terminals:

```bash
# 1) API backend on :5000 — pick a provider, or none for manual-entry mode
EPL_LLM_PROVIDER=ollama EPL_LLM_MODEL=gemma3 python -m webapp   # local Gemma via Ollama
#   EPL_OLLAMA_HOST defaults to http://localhost:11434
#   ANTHROPIC_API_KEY=... python -m webapp                      # or a hosted provider
#   OCR (uploads) needs the tesseract binary: apt-get install tesseract-ocr poppler-utils
#   and: pip install -e ".[ocr]"

# 2) Next.js dev server on :3000 (proxies /api -> :5000)
cd web && npm install && npm run dev
```

Open **http://localhost:3000**. With no provider configured, extraction/chat are
disabled and you enter facts manually to drive the deterministic engine offline.
`EPL_API_TARGET` overrides the API URL the frontend proxies to.

A dependency-free Jinja fallback UI is also served at the API's `/` (handy for a
quick look without Node). It is a research demo — clearly labeled decision
support, not a diagnosis or a medical device.

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
