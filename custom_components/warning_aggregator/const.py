"""Constants for the Warning Aggregator integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "warning_aggregator"

# Frontend card
CARD_FILENAME: Final = "warning-aggregator-card.js"
CARD_URL: Final = f"/{DOMAIN}/{CARD_FILENAME}"
DATA_CARD_REGISTERED: Final = f"{DOMAIN}_card_registered"

# --- helper type (this integration ships two) -------------------------------
CONF_HELPER_TYPE: Final = "helper_type"
HELPER_AGGREGATOR: Final = "aggregator"
HELPER_MONITORED_ENTITY: Final = "monitored_entity"

# --- aggregator config keys ------------------------------------------------
CONF_LABELS: Final = "labels"
CONF_MATCH: Final = "match"
CONF_PROBLEM_STATES: Final = "problem_states"

MATCH_ANY: Final = "any"
MATCH_ALL: Final = "all"
MATCH_OPTIONS: Final[list[str]] = [MATCH_ANY, MATCH_ALL]

DEFAULT_MATCH: Final = MATCH_ANY
DEFAULT_PROBLEM_STATES: Final[list[str]] = ["warning"]

# Attributes on the aggregator entities
ATTR_PROBLEM_ENTITIES: Final = "problem_entities"
ATTR_PROBLEM_NAMES: Final = "problem_names"
ATTR_PROBLEM_COUNT: Final = "problem_count"
ATTR_WATCHED_COUNT: Final = "watched_count"
ATTR_WATCHED_ENTITIES: Final = "watched_entities"
ATTR_LABELS: Final = "labels"
ATTR_MATCH: Final = "match"

# --- monitored-entity config keys ----------------------------------------
CONF_KIND: Final = "kind"
CONF_UNAVAILABLE_IS: Final = "unavailable_is"

KIND_BOOLEAN: Final = "boolean"
KIND_NUMERIC: Final = "numeric"
KIND_STRING: Final = "string"

UNAVAILABLE_PROBLEM: Final = "problem"
UNAVAILABLE_OK: Final = "ok"
UNAVAILABLE_OPTIONS: Final[list[str]] = [UNAVAILABLE_PROBLEM, UNAVAILABLE_OK]

# boolean
CONF_BAD_STATE: Final = "bad_state"
BAD_STATE_OPTIONS: Final[list[str]] = ["on", "off"]

# numeric
CONF_THRESHOLD: Final = "threshold"
CONF_DIRECTION: Final = "direction"
CONF_HYSTERESIS: Final = "hysteresis"
DIRECTION_BELOW: Final = "below"
DIRECTION_ABOVE: Final = "above"
DIRECTION_OPTIONS: Final[list[str]] = [DIRECTION_BELOW, DIRECTION_ABOVE]

# string
CONF_MATCH_TEXT: Final = "match_text"
CONF_MATCH_MODE: Final = "match_mode"
CONF_COMPARISON: Final = "comparison"
MATCH_IS_BAD: Final = "match_is_bad"
MATCH_IS_GOOD: Final = "match_is_good"
MATCH_MODE_OPTIONS: Final[list[str]] = [MATCH_IS_BAD, MATCH_IS_GOOD]
COMPARISON_EQUALS: Final = "equals"
COMPARISON_CONTAINS: Final = "contains"
COMPARISON_OPTIONS: Final[list[str]] = [COMPARISON_EQUALS, COMPARISON_CONTAINS]

# Domains whose state is boolean-shaped even when currently unavailable
BOOLEAN_DOMAINS: Final[frozenset[str]] = frozenset(
    {
        "binary_sensor",
        "input_boolean",
        "switch",
        "light",
        "fan",
        "lock",
        "siren",
        "valve",
        "humidifier",
        "update",
        "schedule",
    }
)

# Attributes on the monitored-entity binary sensor
ATTR_WATCHED_ENTITY: Final = "watched_entity"
ATTR_WATCHED_STATE: Final = "watched_state"
ATTR_REASON: Final = "reason"
ATTR_KIND: Final = "kind"
