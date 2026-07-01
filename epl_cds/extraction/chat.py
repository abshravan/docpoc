"""Advisory clinician chat — assistance and explanation, never a decision.

============================ FIREWALL NOTE ============================
This lets a clinician discuss a case with the model, grounded in the patient's
verified facts and the uploaded reference papers. It is ADVISORY ONLY: it never
produces or changes the determination. The deterministic engine remains the sole
source of the verdict; nothing here feeds `reasoning/`. LLM use stays under
`extraction/`, per CLAUDE.md.
======================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from epl_cds.contracts import LLMFn
from epl_cds.extraction.rag import Chunk, VectorStore

CHAT_PROMPT_VERSION = "c1"

_SYSTEM = """You are an advisory assistant for a clinician reviewing an early-pregnancy
ultrasound case. You do NOT make or change any diagnosis or determination — a
separate deterministic engine does that. Discuss and explain only.

Ground your answers in the patient facts and the cited reference passages below.
Cite passages by their [n] number. If something isn't supported, say so. Never
tell the clinician what to diagnose; offer considerations and evidence.

Patient facts (clinician-verified):
{facts}

Reference passages:
{passages}
"""


@dataclass
class ChatReply:
    answer: str
    citations: list[Chunk] = field(default_factory=list)
    prompt_version: str = CHAT_PROMPT_VERSION


def _format_facts(facts: Optional[dict]) -> str:
    if not facts:
        return "(none provided)"
    documented = {k: v for k, v in facts.items() if v is not None}
    if not documented:
        return "(none documented)"
    return "\n".join(f"- {k}: {v}" for k, v in documented.items())


def _render_prompt(messages: list[dict], facts: Optional[dict], passages: list[Chunk]) -> str:
    numbered = "\n\n".join(f"[{i + 1}] ({c.source}) {c.text}" for i, c in enumerate(passages))
    system = _SYSTEM.format(facts=_format_facts(facts), passages=numbered or "(no papers loaded)")
    convo = "\n".join(
        f"{'Clinician' if m.get('role') == 'user' else 'Assistant'}: {m.get('content', '')}"
        for m in messages
    )
    return f"{system}\n\nConversation:\n{convo}\n\nAssistant:"


def advisory_chat(
    messages: list[dict],
    facts: Optional[dict],
    store: VectorStore,
    llm_fn: LLMFn,
    *,
    k: int = 4,
) -> ChatReply:
    """Answer the latest clinician message, grounded in facts + retrieved papers."""
    last_user = next(
        (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"),
        "",
    )
    hits = store.query(last_user, k=k) if last_user else []
    citations = [h.chunk for h in hits]
    answer = llm_fn(_render_prompt(messages, facts, citations))
    return ChatReply(answer=answer.strip(), citations=citations)
