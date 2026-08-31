"""Unit tests for the check detection + evaluation (pure functions)."""

from __future__ import annotations

from homeassistant.core import State
import pytest

from custom_components.warning_aggregator.check import detect_kind, evaluate
from custom_components.warning_aggregator.const import (
    CONF_BAD_STATE,
    CONF_COMPARISON,
    CONF_DIRECTION,
    CONF_HYSTERESIS,
    CONF_MATCH_MODE,
    CONF_MATCH_TEXT,
    CONF_THRESHOLD,
    CONF_UNAVAILABLE_IS,
    DIRECTION_ABOVE,
    DIRECTION_BELOW,
    KIND_BOOLEAN,
    KIND_NUMERIC,
    KIND_STRING,
    MATCH_IS_BAD,
    MATCH_IS_GOOD,
    UNAVAILABLE_OK,
    UNAVAILABLE_PROBLEM,
)


@pytest.mark.parametrize(
    ("entity_id", "state", "expected"),
    [
        ("binary_sensor.door", "off", KIND_BOOLEAN),
        ("switch.pump", "on", KIND_BOOLEAN),
        ("input_boolean.guest", "unavailable", KIND_BOOLEAN),  # domain wins
        ("sensor.battery", "37", KIND_NUMERIC),
        ("sensor.temp", "-4.5", KIND_NUMERIC),
        ("sensor.printer_status", "Ready", KIND_STRING),
        ("sensor.vacuum_error", "none", KIND_STRING),
    ],
)
def test_detect_kind(entity_id, state, expected):
    assert detect_kind(State(entity_id, state)) == expected


def test_detect_kind_no_state_defaults_string():
    assert detect_kind(None) == KIND_STRING


# --- boolean -------------------------------------------------------------


def test_boolean_on_is_bad():
    params = {CONF_BAD_STATE: "on", CONF_UNAVAILABLE_IS: UNAVAILABLE_PROBLEM}
    assert evaluate(KIND_BOOLEAN, params, State("switch.x", "on")).problem is True
    assert evaluate(KIND_BOOLEAN, params, State("switch.x", "off")).problem is False


def test_boolean_off_is_bad():
    params = {CONF_BAD_STATE: "off", CONF_UNAVAILABLE_IS: UNAVAILABLE_PROBLEM}
    assert (
        evaluate(KIND_BOOLEAN, params, State("binary_sensor.x", "off")).problem is True
    )


# --- numeric -----------------------------------------------------------


def test_numeric_below_threshold():
    params = {
        CONF_THRESHOLD: 20,
        CONF_DIRECTION: DIRECTION_BELOW,
        CONF_HYSTERESIS: 0,
        CONF_UNAVAILABLE_IS: UNAVAILABLE_PROBLEM,
    }
    assert evaluate(KIND_NUMERIC, params, State("sensor.b", "12")).problem is True
    assert evaluate(KIND_NUMERIC, params, State("sensor.b", "25")).problem is False


def test_numeric_above_threshold():
    params = {
        CONF_THRESHOLD: 80,
        CONF_DIRECTION: DIRECTION_ABOVE,
        CONF_HYSTERESIS: 0,
        CONF_UNAVAILABLE_IS: UNAVAILABLE_PROBLEM,
    }
    assert evaluate(KIND_NUMERIC, params, State("sensor.t", "90")).problem is True
    assert evaluate(KIND_NUMERIC, params, State("sensor.t", "70")).problem is False


def test_numeric_hysteresis_holds_until_clear_of_the_band():
    params = {
        CONF_THRESHOLD: 20,
        CONF_DIRECTION: DIRECTION_BELOW,
        CONF_HYSTERESIS: 3,
        CONF_UNAVAILABLE_IS: UNAVAILABLE_PROBLEM,
    }
    # Not yet a problem: must drop below 17 to trip.
    assert (
        evaluate(
            KIND_NUMERIC, params, State("s.b", "18"), currently_problem=False
        ).problem
        is False
    )
    assert (
        evaluate(
            KIND_NUMERIC, params, State("s.b", "16"), currently_problem=False
        ).problem
        is True
    )
    # Already a problem: stays tripped until back above 23.
    assert (
        evaluate(
            KIND_NUMERIC, params, State("s.b", "22"), currently_problem=True
        ).problem
        is True
    )
    assert (
        evaluate(
            KIND_NUMERIC, params, State("s.b", "24"), currently_problem=True
        ).problem
        is False
    )


def test_numeric_non_numeric_value_uses_unavailable_rule():
    params = {
        CONF_THRESHOLD: 20,
        CONF_DIRECTION: DIRECTION_BELOW,
        CONF_HYSTERESIS: 0,
        CONF_UNAVAILABLE_IS: UNAVAILABLE_OK,
    }
    assert evaluate(KIND_NUMERIC, params, State("sensor.b", "boom")).problem is False


# --- string ----------------------------------------------------------


def test_string_match_is_bad_case_insensitive():
    params = {
        CONF_MATCH_TEXT: "Error",
        CONF_COMPARISON: "equals",
        CONF_MATCH_MODE: MATCH_IS_BAD,
        CONF_UNAVAILABLE_IS: UNAVAILABLE_PROBLEM,
    }
    assert evaluate(KIND_STRING, params, State("sensor.s", "error")).problem is True
    assert evaluate(KIND_STRING, params, State("sensor.s", "Ready")).problem is False


def test_string_match_is_good():
    params = {
        CONF_MATCH_TEXT: "OK",
        CONF_COMPARISON: "equals",
        CONF_MATCH_MODE: MATCH_IS_GOOD,
        CONF_UNAVAILABLE_IS: UNAVAILABLE_PROBLEM,
    }
    assert evaluate(KIND_STRING, params, State("sensor.s", "ok")).problem is False
    assert evaluate(KIND_STRING, params, State("sensor.s", "degraded")).problem is True


def test_string_contains():
    params = {
        CONF_MATCH_TEXT: "fail",
        CONF_COMPARISON: "contains",
        CONF_MATCH_MODE: MATCH_IS_BAD,
        CONF_UNAVAILABLE_IS: UNAVAILABLE_PROBLEM,
    }
    assert (
        evaluate(KIND_STRING, params, State("s.s", "Self-test FAILED")).problem is True
    )


# --- missing value ---------------------------------------------------


@pytest.mark.parametrize("raw", ["unavailable", "unknown", "none", ""])
def test_missing_value_defaults_to_problem(raw):
    params = {
        CONF_BAD_STATE: "on",
        CONF_UNAVAILABLE_IS: UNAVAILABLE_PROBLEM,
    }
    assert evaluate(KIND_BOOLEAN, params, State("binary_sensor.x", raw)).problem is True


def test_missing_value_can_be_ok():
    params = {CONF_BAD_STATE: "on", CONF_UNAVAILABLE_IS: UNAVAILABLE_OK}
    assert evaluate(KIND_BOOLEAN, params, None).problem is False
