"""Detect what kind of check an entity needs, and evaluate it.

Pure functions - no Home Assistant wiring - so they are cheap to unit test.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import State

from .const import (
    BOOLEAN_DOMAINS,
    COMPARISON_CONTAINS,
    CONF_BAD_STATE,
    CONF_COMPARISON,
    CONF_DIRECTION,
    CONF_HYSTERESIS,
    CONF_MATCH_MODE,
    CONF_MATCH_TEXT,
    CONF_RANGE_HIGH,
    CONF_RANGE_LOW,
    CONF_THRESHOLD,
    CONF_UNAVAILABLE_IS,
    DIRECTION_BELOW,
    DIRECTION_INSIDE,
    DIRECTION_RANGE,
    KIND_BOOLEAN,
    KIND_NUMERIC,
    KIND_STRING,
    MATCH_IS_BAD,
    UNAVAILABLE_PROBLEM,
)

# States that count as "no value" alongside unavailable / unknown.
_EMPTY_STATES = {"", "none", "null", "nan"}


@dataclass(slots=True)
class CheckResult:
    """Outcome of evaluating a check."""

    problem: bool
    reason: str


def detect_kind(state: State | None) -> str:
    """Best guess at the check kind for an entity from its current state."""
    if state is None:
        return KIND_STRING

    domain = state.entity_id.split(".", 1)[0]
    raw = state.state

    if domain in BOOLEAN_DOMAINS or raw in ("on", "off", "true", "false"):
        return KIND_BOOLEAN

    if _as_float(raw) is not None:
        return KIND_NUMERIC

    return KIND_STRING


def evaluate(
    kind: str,
    params: dict[str, Any],
    state: State | None,
    *,
    currently_problem: bool = False,
) -> CheckResult:
    """Evaluate a check against a watched entity's state.

    ``currently_problem`` is the check's own last output - used for numeric
    hysteresis so the sensor doesn't flap around the threshold.
    """
    unavailable_is_problem = params.get(CONF_UNAVAILABLE_IS, UNAVAILABLE_PROBLEM) == (
        UNAVAILABLE_PROBLEM
    )

    if _is_missing(state):
        return CheckResult(
            unavailable_is_problem,
            "no value" if unavailable_is_problem else "no value (treated as OK)",
        )

    raw = state.state  # type: ignore[union-attr]

    if kind == KIND_BOOLEAN:
        bad = raw.strip().lower() in _bad_boolean_tokens(params[CONF_BAD_STATE])
        return CheckResult(bad, f"state is '{raw}'")

    if kind == KIND_NUMERIC:
        value = _as_float(raw)
        if value is None:
            return CheckResult(
                unavailable_is_problem,
                f"'{raw}' is not a number"
                + ("" if unavailable_is_problem else " (treated as OK)"),
            )
        return _evaluate_numeric(params, value, currently_problem)

    return _evaluate_string(params, raw)


# --------------------------------------------------------------------------


def _evaluate_numeric(
    params: dict[str, Any], value: float, currently_problem: bool
) -> CheckResult:
    hysteresis = abs(float(params.get(CONF_HYSTERESIS) or 0.0))

    if params[CONF_DIRECTION] in DIRECTION_RANGE:
        return _evaluate_range(params, value, currently_problem, hysteresis)

    threshold = float(params[CONF_THRESHOLD])
    below = params[CONF_DIRECTION] == DIRECTION_BELOW

    if below:
        limit = threshold + hysteresis if currently_problem else threshold - hysteresis
        bad = value < limit
        rel = "below" if bad else "at or above"
    else:
        limit = threshold - hysteresis if currently_problem else threshold + hysteresis
        bad = value > limit
        rel = "above" if bad else "at or below"

    return CheckResult(bad, f"{_fmt(value)} is {rel} {_fmt(threshold)}")


def _evaluate_range(
    params: dict[str, Any], value: float, currently_problem: bool, hysteresis: float
) -> CheckResult:
    low = float(params[CONF_RANGE_LOW])
    high = float(params[CONF_RANGE_HIGH])
    if low > high:
        low, high = high, low

    inside_is_bad = params[CONF_DIRECTION] == DIRECTION_INSIDE
    # `currently_problem` tells us the verdict; work out where the value sits now
    # so the deadband is applied to the boundary the value has to cross to flip.
    currently_within = currently_problem if inside_is_bad else not currently_problem
    if currently_within:
        within = (low - hysteresis) <= value <= (high + hysteresis)
    else:
        within = (low + hysteresis) <= value <= (high - hysteresis)

    bad = within if inside_is_bad else not within
    where = "within" if low <= value <= high else "outside"
    return CheckResult(bad, f"{_fmt(value)} is {where} {_fmt(low)} to {_fmt(high)}")


def _evaluate_string(params: dict[str, Any], raw: str) -> CheckResult:
    needle = params[CONF_MATCH_TEXT].strip().lower()
    haystack = raw.strip().lower()

    if params.get(CONF_COMPARISON) == COMPARISON_CONTAINS:
        matched = needle in haystack
    else:
        matched = haystack == needle

    match_is_bad = params.get(CONF_MATCH_MODE, MATCH_IS_BAD) == MATCH_IS_BAD
    bad = matched if match_is_bad else not matched

    text = params[CONF_MATCH_TEXT]
    if match_is_bad:
        reason = (
            f"'{raw}' matches '{text}'" if bad else f"'{raw}' does not match '{text}'"
        )
    else:
        reason = f"'{raw}' is not '{text}'" if bad else f"'{raw}' matches '{text}'"
    return CheckResult(bad, reason)


def _is_missing(state: State | None) -> bool:
    if state is None:
        return True
    return state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN) or (
        state.state.strip().lower() in _EMPTY_STATES
    )


def _bad_boolean_tokens(bad_state: str) -> set[str]:
    return {"on", "true"} if bad_state == "on" else {"off", "false"}


def _as_float(raw: Any) -> float | None:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _fmt(value: float) -> str:
    return f"{value:g}"
