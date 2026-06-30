"""Cross-layer data contracts for EPL-CDS.

Every dataclass that crosses a layer boundary lives here. Layers import ONLY
from this module, never from a sibling layer (see CLAUDE.md / ARCHITECTURE.md).

Nothing in this module performs I/O, network calls, or probabilistic logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional, Protocol


# --------------------------------------------------------------------------- #
# Determination tiers
# --------------------------------------------------------------------------- #
class Determination(str, Enum):
    """The three tiers the deterministic engine can return.

    These mirror the guideline language exactly: a finding is either
    *diagnostic of* loss, *suspicious for* loss, or meets neither bar. There is
    deliberately no "viable"/"normal" tier — this is decision support for loss,
    not a viability verdict.
    """

    DIAGNOSTIC_OF_LOSS = "diagnostic_of_loss"
    SUSPICIOUS_FOR_LOSS = "suspicious_for_loss"
    NO_CRITERIA_MET = "no_criteria_met"


# --------------------------------------------------------------------------- #
# Facts: what the LLM extracts (the ONLY place probabilistic output enters)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Facts:
    """Structured clinical observations extracted from a chart/report.

    Every field is Optional: absent means "not documented / not extracted",
    which the engine treats as "cannot fire a rule that needs it". The engine
    must never guess a missing value.
    """

    # Single-scan ultrasound measurements
    crl_mm: Optional[float] = None            # crown-rump length, mm
    cardiac_activity: Optional[bool] = None   # embryonic heartbeat seen?
    msd_mm: Optional[float] = None            # mean sac diameter, mm
    embryo_visible: Optional[bool] = None     # any embryo seen?
    yolk_sac_visible: Optional[bool] = None   # yolk sac seen?
    yolk_sac_diameter_mm: Optional[float] = None
    amnion_visible: Optional[bool] = None     # amnion seen (empty-amnion sign)?

    # Serial-scan / interval findings
    days_since_sac_without_yolk: Optional[int] = None  # days since a prior scan
    days_since_sac_with_yolk: Optional[int] = None     #   showed sac (no/with yolk)
    days_since_lmp: Optional[int] = None               # days since last menses

    # Names of the fields a study can score for Arm 1 (per-fact accuracy).
    @classmethod
    def field_names(cls) -> tuple[str, ...]:
        return tuple(f.name for f in cls.__dataclass_fields__.values())  # type: ignore[attr-defined]


# --------------------------------------------------------------------------- #
# Ruleset: frozen, versioned clinical knowledge
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Rule:
    """One clinical criterion. `params` carries the numeric thresholds; the
    deterministic comparison logic lives in the engine's evaluator registry."""

    id: str
    tier: str            # "diagnostic" | "suspicious"
    description: str
    citation: str
    verify: bool         # True => threshold awaits expert sign-off
    params: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Ruleset:
    version: str
    source: str
    status: str
    rules: tuple[Rule, ...]
    name: str = ""  # human label (e.g. "SRU 2013"); falls back to version

    def rule_ids(self) -> tuple[str, ...]:
        return tuple(r.id for r in self.rules)

    @property
    def label(self) -> str:
        return self.name or self.version


# --------------------------------------------------------------------------- #
# DeterminationResult: the engine's output
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class DeterminationResult:
    determination: Determination
    fired_rule_ids: tuple[str, ...]
    ruleset_version: str
    rationale: str


@dataclass(frozen=True)
class ComparisonEntry:
    """One ruleset's deterministic verdict on a case, for cross-guideline
    comparison. Each entry is a pure engine evaluation — no LLM, no voting."""

    ruleset_label: str
    ruleset_version: str
    result: DeterminationResult


# --------------------------------------------------------------------------- #
# BaselineOpinion: a NON-AUTHORITATIVE, end-to-end LLM verdict (research only)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class BaselineOpinion:
    """What an unconstrained LLM would conclude directly from the note.

    This exists ONLY as a research comparison baseline — it demonstrates why the
    deterministic engine is needed and where a raw model diverges. It MUST NEVER
    feed a determination, a CaseRecord, or anything in `reasoning/`. `determination`
    is None when the model output could not be parsed into a known tier.
    """

    determination: Optional[Determination]
    rationale: str
    raw: str
    model: str
    prompt_version: str


# --------------------------------------------------------------------------- #
# CaseRecord: one fully-traced case (links both study arms)
# --------------------------------------------------------------------------- #
@dataclass
class CaseRecord:
    case_id: str
    facts: Facts
    result: DeterminationResult

    # Reproducibility provenance — pinned per case.
    extractor_model: str
    prompt_version: str
    ruleset_version: str
    created_at: str  # ISO-8601 UTC

    # Optional raw source (synthetic only until study gates are satisfied).
    note: Optional[str] = None

    # Arm 1 reference: manual chart abstraction (gold facts).
    gold_facts: Optional[Facts] = None
    # Arm 2 reference: expert adjudication of the determination.
    adjudicated_determination: Optional[Determination] = None
    # Engine determination on the gold facts (set when gold_facts is provided).
    # Comparing this to `result.determination` isolates how much an extraction
    # error changed the engine's output (the determination-flip metric).
    gold_determination: Optional[Determination] = None


# --------------------------------------------------------------------------- #
# LLMFn: the single injection point for the language model
# --------------------------------------------------------------------------- #
class LLMFn(Protocol):
    """A provider-agnostic callable: takes a fully-rendered prompt, returns the
    model's raw text response (expected to be JSON). Injected into the pipeline
    so tests run offline against a stub with no API key."""

    def __call__(self, prompt: str) -> str: ...  # pragma: no cover - protocol


class EmbedFn(Protocol):
    """A provider-agnostic embedding callable: text -> dense vector. Injected
    into the RAG store so retrieval runs offline against a deterministic local
    embedder (no network) or against a real embedding model."""

    def __call__(self, text: str) -> list[float]: ...  # pragma: no cover - protocol
