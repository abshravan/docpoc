"""Retrieval-augmented evidence lookup over a paper/notes corpus.

This is an *explainability* aid: it retrieves cited passages relevant to a
question (e.g. "what's the evidence for the 7 mm CRL cutoff?") and, if a model
is available, synthesizes a grounded answer that may only use those passages. It
touches no determination — the deterministic engine is untouched. Any LLM use
stays here under `extraction/`, per CLAUDE.md.

Retrieval works fully offline via a deterministic hashing embedder; a real
embedding model can be injected for semantic retrieval. Answer synthesis is
optional — without a model, the retrieved passages are returned as-is.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from typing import Optional

from epl_cds.contracts import EmbedFn, LLMFn

EVIDENCE_PROMPT_VERSION = "e1"


# --------------------------------------------------------------------------- #
# Chunks
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Chunk:
    source: str
    text: str


@dataclass(frozen=True)
class ScoredChunk:
    chunk: Chunk
    score: float


def chunk_text(text: str, source: str, *, max_chars: int = 600) -> list[Chunk]:
    """Split text into paragraph-ish chunks no longer than ~max_chars."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[Chunk] = []
    buf = ""
    for para in paragraphs:
        if buf and len(buf) + len(para) + 1 > max_chars:
            chunks.append(Chunk(source, buf.strip()))
            buf = para
        else:
            buf = f"{buf}\n{para}" if buf else para
    if buf.strip():
        chunks.append(Chunk(source, buf.strip()))
    return chunks


# --------------------------------------------------------------------------- #
# Deterministic offline embedder (feature hashing over tokens)
# --------------------------------------------------------------------------- #
_TOKEN = re.compile(r"[a-z0-9]+")


def hashing_embed_fn(dim: int = 256) -> EmbedFn:
    """A dependency-free, deterministic lexical embedder.

    Feature-hashes tokens into `dim` buckets (L2-normalized). Not semantic, but
    it gives sensible word-overlap retrieval with no model or network — so
    evidence retrieval always works offline.
    """

    def _embed(text: str) -> list[float]:
        vec = [0.0] * dim
        for tok in _TOKEN.findall(text.lower()):
            h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
            vec[h % dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        if norm:
            vec = [v / norm for v in vec]
        return vec

    return _embed


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


# --------------------------------------------------------------------------- #
# Vector store
# --------------------------------------------------------------------------- #
class VectorStore:
    def __init__(self, embed_fn: EmbedFn):
        self._embed = embed_fn
        self._items: list[tuple[Chunk, list[float]]] = []

    @property
    def size(self) -> int:
        return len(self._items)

    @property
    def sources(self) -> list[str]:
        return sorted({c.source for c, _ in self._items})

    def add_text(self, text: str, source: str) -> int:
        chunks = chunk_text(text, source)
        for c in chunks:
            self._items.append((c, self._embed(c.text)))
        return len(chunks)

    def query(self, question: str, k: int = 4) -> list[ScoredChunk]:
        if not self._items:
            return []
        qv = self._embed(question)
        scored = [ScoredChunk(c, cosine(qv, v)) for c, v in self._items]
        scored.sort(key=lambda s: s.score, reverse=True)
        return scored[:k]


# --------------------------------------------------------------------------- #
# Grounded answer
# --------------------------------------------------------------------------- #
@dataclass
class EvidenceAnswer:
    answer: str
    citations: list[Chunk] = field(default_factory=list)
    synthesized: bool = False
    prompt_version: str = EVIDENCE_PROMPT_VERSION


_EVIDENCE_TEMPLATE = """Answer the question using ONLY the numbered passages below. If the
passages do not contain the answer, say "The provided sources do not say." Cite
the passages you use by their [n] number. Do not add outside knowledge.

Question: {question}

Passages:
{passages}

Answer (with [n] citations):"""


def render_evidence_prompt(question: str, passages: list[Chunk]) -> str:
    numbered = "\n\n".join(
        f"[{i + 1}] ({c.source}) {c.text}" for i, c in enumerate(passages)
    )
    return _EVIDENCE_TEMPLATE.format(question=question, passages=numbered)


def answer_question(
    question: str,
    store: VectorStore,
    *,
    llm_fn: Optional[LLMFn] = None,
    k: int = 4,
) -> EvidenceAnswer:
    """Retrieve the top-k passages and (optionally) synthesize a grounded answer.

    Without `llm_fn`, retrieval still works: the passages are returned as the
    answer's citations and `synthesized` is False.
    """
    hits = store.query(question, k=k)
    citations = [h.chunk for h in hits]
    if llm_fn is None or not citations:
        return EvidenceAnswer(answer="", citations=citations, synthesized=False)
    answer = llm_fn(render_evidence_prompt(question, citations))
    return EvidenceAnswer(answer=answer.strip(), citations=citations, synthesized=True)
