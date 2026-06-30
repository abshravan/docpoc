"""Deterministic rule engine. A pure function of (facts, ruleset).

HARD CONSTRAINT (see CLAUDE.md): no LLM, no probabilistic logic, and no network
call anywhere in this package. Nothing here may import from a sibling layer.
"""

from epl_cds.reasoning.engine import (
    RULE_EVALUATORS,
    compare_rulesets,
    evaluate,
    is_concordant,
)

__all__ = ["evaluate", "compare_rulesets", "is_concordant", "RULE_EVALUATORS"]
