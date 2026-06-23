"""The deterministic EPL engine.

`evaluate(facts, ruleset)` is a pure function: same inputs => same output, no
side effects, no randomness, no I/O. The numeric thresholds come entirely from
the ruleset; this module only supplies the fixed comparison structure for each
named rule id. Adding a clinical criterion means adding a rule to the YAML AND
registering an evaluator here.

Tier precedence: any diagnostic rule that fires outranks every suspicious rule.
This protects specificity — a diagnostic finding is never downgraded.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

from epl_cds.contracts import (
    Determination,
    DeterminationResult,
    Facts,
    Ruleset,
)

# An evaluator answers a single yes/no question: "given these facts and these
# thresholds, does this criterion fire?" Missing facts => False (never guess).
Evaluator = Callable[[Facts, Mapping[str, Any]], bool]


def _no_embryo_with_heartbeat(f: Facts) -> bool:
    """Absence of an embryo with a heartbeat, per the guideline phrasing.

    True when an embryo is documented absent OR cardiac activity is documented
    absent. Unknown (None) does not satisfy the condition.
    """
    return f.embryo_visible is False or f.cardiac_activity is False


# --------------------------------------------------------------------------- #
# Diagnostic evaluators
# --------------------------------------------------------------------------- #
def _crl_no_cardiac(f: Facts, p: Mapping[str, Any]) -> bool:
    return (
        f.crl_mm is not None
        and f.cardiac_activity is False
        and f.crl_mm >= p["crl_mm"]
    )


def _msd_no_embryo(f: Facts, p: Mapping[str, Any]) -> bool:
    return (
        f.msd_mm is not None
        and f.embryo_visible is False
        and f.msd_mm >= p["msd_mm"]
    )


def _interval_no_yolk(f: Facts, p: Mapping[str, Any]) -> bool:
    d = f.days_since_sac_without_yolk
    return d is not None and d >= p["days"] and _no_embryo_with_heartbeat(f)


def _interval_with_yolk(f: Facts, p: Mapping[str, Any]) -> bool:
    d = f.days_since_sac_with_yolk
    return d is not None and d >= p["days"] and _no_embryo_with_heartbeat(f)


# --------------------------------------------------------------------------- #
# Suspicious evaluators
# --------------------------------------------------------------------------- #
def _crl_small_no_cardiac(f: Facts, p: Mapping[str, Any]) -> bool:
    return (
        f.crl_mm is not None
        and f.crl_mm > 0
        and f.cardiac_activity is False
        and f.crl_mm < p["crl_max_mm"]
    )


def _msd_intermediate_no_embryo(f: Facts, p: Mapping[str, Any]) -> bool:
    return (
        f.msd_mm is not None
        and f.embryo_visible is False
        and p["msd_min_mm"] <= f.msd_mm < p["msd_max_mm"]
    )


def _interval_no_yolk_suspicious(f: Facts, p: Mapping[str, Any]) -> bool:
    d = f.days_since_sac_without_yolk
    return (
        d is not None
        and p["days_min"] <= d < p["days_max"]
        and _no_embryo_with_heartbeat(f)
    )


def _interval_with_yolk_suspicious(f: Facts, p: Mapping[str, Any]) -> bool:
    d = f.days_since_sac_with_yolk
    return (
        d is not None
        and p["days_min"] <= d < p["days_max"]
        and _no_embryo_with_heartbeat(f)
    )


def _enlarged_yolk_sac(f: Facts, p: Mapping[str, Any]) -> bool:
    return (
        f.yolk_sac_diameter_mm is not None
        and f.yolk_sac_diameter_mm > p["max_mm"]
    )


def _empty_amnion(f: Facts, p: Mapping[str, Any]) -> bool:
    return f.amnion_visible is True and f.embryo_visible is False


def _small_sac_relative_to_embryo(f: Facts, p: Mapping[str, Any]) -> bool:
    # Only meaningful when an embryo has been measured (CRL present).
    return (
        f.msd_mm is not None
        and f.crl_mm is not None
        and f.crl_mm > 0
        and (f.msd_mm - f.crl_mm) < p["min_diff_mm"]
    )


def _no_embryo_by_lmp(f: Facts, p: Mapping[str, Any]) -> bool:
    return (
        f.days_since_lmp is not None
        and f.embryo_visible is False
        and f.days_since_lmp >= p["days"]
    )


# Registry: rule id -> evaluator. The loader/validator guarantee structure; the
# engine guarantees every ruleset rule has a registered evaluator (see below).
RULE_EVALUATORS: dict[str, Evaluator] = {
    "crl_no_cardiac": _crl_no_cardiac,
    "msd_no_embryo": _msd_no_embryo,
    "interval_no_yolk": _interval_no_yolk,
    "interval_with_yolk": _interval_with_yolk,
    "crl_small_no_cardiac": _crl_small_no_cardiac,
    "msd_intermediate_no_embryo": _msd_intermediate_no_embryo,
    "interval_no_yolk_suspicious": _interval_no_yolk_suspicious,
    "interval_with_yolk_suspicious": _interval_with_yolk_suspicious,
    "enlarged_yolk_sac": _enlarged_yolk_sac,
    "empty_amnion": _empty_amnion,
    "small_sac_relative_to_embryo": _small_sac_relative_to_embryo,
    "no_embryo_by_lmp": _no_embryo_by_lmp,
}


def evaluate(facts: Facts, ruleset: Ruleset) -> DeterminationResult:
    """Apply every rule in the ruleset to the facts and resolve a tier.

    Raises KeyError if the ruleset names a rule with no registered evaluator —
    that is a code/knowledge mismatch and must fail loudly, never silently pass.
    """
    fired_diagnostic: list[str] = []
    fired_suspicious: list[str] = []

    for rule in ruleset.rules:
        try:
            evaluator = RULE_EVALUATORS[rule.id]
        except KeyError as exc:
            raise KeyError(
                f"ruleset rule {rule.id!r} has no registered evaluator in the "
                f"engine; knowledge and code are out of sync"
            ) from exc

        if evaluator(facts, rule.params):
            if rule.tier == "diagnostic":
                fired_diagnostic.append(rule.id)
            else:
                fired_suspicious.append(rule.id)

    if fired_diagnostic:
        determination = Determination.DIAGNOSTIC_OF_LOSS
        fired = tuple(fired_diagnostic)
        rationale = (
            "Diagnostic criteria met: " + ", ".join(fired_diagnostic) + "."
        )
    elif fired_suspicious:
        determination = Determination.SUSPICIOUS_FOR_LOSS
        fired = tuple(fired_suspicious)
        rationale = (
            "Suspicious criteria met (follow-up recommended): "
            + ", ".join(fired_suspicious)
            + "."
        )
    else:
        determination = Determination.NO_CRITERIA_MET
        fired = ()
        rationale = "No diagnostic or suspicious criteria met on the documented findings."

    return DeterminationResult(
        determination=determination,
        fired_rule_ids=fired,
        ruleset_version=ruleset.version,
        rationale=rationale,
    )
