"""Optional, concrete `llm_fn` providers.

These are the only place a real network-backed model is wired up. They are NOT
imported by the test suite and are loaded lazily, so the package still installs
and tests still run with no provider SDK and no API key (see CLAUDE.md: never
hardcode a real API call into a code path that tests exercise).

The pipeline depends on the `LLMFn` protocol, not on anything here.
"""

from __future__ import annotations

import os
from typing import Optional

from epl_cds.contracts import LLMFn

# Overridable so the demo is not pinned to one model.
DEFAULT_ANTHROPIC_MODEL = os.environ.get("EPL_LLM_MODEL", "claude-sonnet-4-6")


def anthropic_llm_fn(
    model: str = DEFAULT_ANTHROPIC_MODEL,
    *,
    max_tokens: int = 1024,
    api_key: Optional[str] = None,
) -> LLMFn:
    """Return an `llm_fn` backed by the Anthropic API.

    The `anthropic` SDK is imported lazily so importing this module never
    requires it. Extraction-only: the model returns JSON facts and never makes a
    determination.
    """
    from anthropic import Anthropic  # lazy, optional dependency

    client = Anthropic(api_key=api_key) if api_key else Anthropic()

    def _fn(prompt: str) -> str:
        resp = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        # Concatenate any text blocks in the response.
        return "".join(
            block.text for block in resp.content if getattr(block, "type", None) == "text"
        )

    return _fn


def default_llm_fn_from_env() -> Optional[LLMFn]:
    """Resolve an `llm_fn` from the environment, or None if none is configured.

    Returns None (rather than raising) when no provider is set up, so the web
    demo can run extraction-disabled but still drive the deterministic engine
    via manually entered facts.
    """
    provider = os.environ.get("EPL_LLM_PROVIDER", "").strip().lower()

    # Explicit opt-out / offline.
    if provider in {"", "none", "stub", "offline"}:
        if os.environ.get("ANTHROPIC_API_KEY") and provider == "":
            # Convenience: a key alone implies the anthropic provider.
            return anthropic_llm_fn()
        return None

    if provider == "anthropic":
        return anthropic_llm_fn()

    raise ValueError(f"unknown EPL_LLM_PROVIDER: {provider!r}")
