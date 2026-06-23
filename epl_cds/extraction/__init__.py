"""LLM extraction — the ONLY place a language model is allowed to run.

The model is injected as an `llm_fn` (see contracts.LLMFn); this package never
hardcodes a provider or makes a network call on a tested code path. It turns
free text into structured Facts and nothing more — it does not decide anything.
"""

from epl_cds.extraction.extractor import extract_facts
from epl_cds.extraction.prompts import PROMPT_VERSION, render_extraction_prompt

__all__ = ["extract_facts", "PROMPT_VERSION", "render_extraction_prompt"]
