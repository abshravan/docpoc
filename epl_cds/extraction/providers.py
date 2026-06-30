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

from epl_cds.contracts import EmbedFn, LLMFn

# Overridable so the demo is not pinned to one model.
DEFAULT_ANTHROPIC_MODEL = os.environ.get("EPL_LLM_MODEL", "claude-sonnet-4-6")
DEFAULT_OLLAMA_MODEL = os.environ.get("EPL_LLM_MODEL", "gemma3")
DEFAULT_OLLAMA_HOST = os.environ.get("EPL_OLLAMA_HOST", "http://localhost:11434")
DEFAULT_EMBED_MODEL = os.environ.get("EPL_EMBED_MODEL", "nomic-embed-text")


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


def ollama_llm_fn(
    model: str = DEFAULT_OLLAMA_MODEL,
    *,
    host: str = DEFAULT_OLLAMA_HOST,
    timeout: float = 120.0,
    temperature: float = 0.0,
) -> LLMFn:
    """Return an `llm_fn` backed by a local Ollama server (e.g. Gemma).

    Uses Ollama's HTTP API via the standard library only — no extra dependency.
    `format=json` constrains the model to valid JSON, and `temperature=0` keeps
    extraction as reproducible as a local model allows. Extraction-only: the
    model returns JSON facts and never makes a determination.
    """
    import json
    import urllib.request

    base = host.rstrip("/")

    def _fn(prompt: str) -> str:
        body = json.dumps(
            {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": temperature},
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{base}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return payload.get("response", "")

    return _fn


def ollama_embed_fn(
    model: str = DEFAULT_EMBED_MODEL,
    *,
    host: str = DEFAULT_OLLAMA_HOST,
    timeout: float = 60.0,
) -> EmbedFn:
    """Return an embedding function backed by a local Ollama embedding model.

    Stdlib-only. Requires an embedding model pulled in Ollama (e.g.
    `nomic-embed-text`); set EPL_EMBED_MODEL to override.
    """
    import json
    import urllib.request

    base = host.rstrip("/")

    def _embed(text: str) -> list[float]:
        body = json.dumps({"model": model, "prompt": text}).encode("utf-8")
        req = urllib.request.Request(
            f"{base}/api/embeddings",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return [float(x) for x in payload.get("embedding", [])]

    return _embed


def default_embed_fn_from_env() -> Optional[EmbedFn]:
    """Resolve an embedding function from the environment.

    EPL_EMBED_PROVIDER=ollama uses the local embedding model. Otherwise returns
    None and callers fall back to the offline hashing embedder.
    """
    provider = os.environ.get("EPL_EMBED_PROVIDER", "").strip().lower()
    if provider == "ollama":
        return ollama_embed_fn()
    return None


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

    if provider == "ollama":
        return ollama_llm_fn()

    raise ValueError(f"unknown EPL_LLM_PROVIDER: {provider!r}")
