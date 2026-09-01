"""Config and options flow tests."""

from __future__ import annotations

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ENTITY_ID, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.warning_aggregator.const import (
    CONF_DIRECTION,
    CONF_HELPER_TYPE,
    CONF_KIND,
    CONF_LABELS,
    CONF_MATCH,
    CONF_PROBLEM_STATES,
    CONF_RANGE_HIGH,
    CONF_RANGE_LOW,
    CONF_THRESHOLD,
    CONF_UNAVAILABLE_IS,
    DIRECTION_BELOW,
    DIRECTION_OUTSIDE,
    DOMAIN,
    HELPER_AGGREGATOR,
    HELPER_MONITORED_ENTITY,
    KIND_NUMERIC,
    MATCH_ANY,
    UNAVAILABLE_PROBLEM,
)


async def _menu(hass: HomeAssistant) -> str:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    return result["flow_id"]


async def test_aggregator_flow(hass: HomeAssistant) -> None:
    """Menu -> aggregator -> create entry."""
    flow_id = await _menu(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"next_step_id": HELPER_AGGREGATOR}
    )
    assert result["step_id"] == HELPER_AGGREGATOR

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Critical Systems",
            CONF_LABELS: ["monitored"],
            CONF_MATCH: MATCH_ANY,
            CONF_PROBLEM_STATES: ["warning"],
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Critical Systems"
    assert result["data"][CONF_HELPER_TYPE] == HELPER_AGGREGATOR


async def test_aggregator_flow_requires_a_label(hass: HomeAssistant) -> None:
    flow_id = await _menu(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"next_step_id": HELPER_AGGREGATOR}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Nope",
            CONF_LABELS: [],
            CONF_MATCH: MATCH_ANY,
            CONF_PROBLEM_STATES: ["warning"],
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_LABELS: "labels_required"}


async def _to_numeric_menu(hass: HomeAssistant, entity_id: str, state: str):
    """Walk the flow to the numeric threshold/range menu."""
    flow_id = await _menu(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"next_step_id": HELPER_MONITORED_ENTITY}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ENTITY_ID: entity_id, CONF_LABELS: []}
    )
    # numeric -> a menu: threshold or range, never both.
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "numeric_kind"
    return result


async def test_monitored_entity_flow_numeric_threshold(hass: HomeAssistant) -> None:
    """numeric -> menu -> the threshold form -> create entry (no range fields)."""
    hass.states.async_set(
        "sensor.laptop_battery", "42", {"friendly_name": "Laptop Battery"}
    )
    result = await _to_numeric_menu(hass, "sensor.laptop_battery", "42")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "numeric_threshold"}
    )
    assert result["step_id"] == "numeric_threshold"
    assert set(result["data_schema"].schema) == {
        CONF_DIRECTION,
        CONF_THRESHOLD,
        "hysteresis",
        CONF_UNAVAILABLE_IS,
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_THRESHOLD: 20,
            CONF_DIRECTION: DIRECTION_BELOW,
            CONF_UNAVAILABLE_IS: UNAVAILABLE_PROBLEM,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Laptop Battery status"
    assert result["data"][CONF_KIND] == KIND_NUMERIC
    assert result["data"][CONF_THRESHOLD] == 20
    assert CONF_RANGE_LOW not in result["data"]


async def test_monitored_entity_flow_numeric_range(hass: HomeAssistant) -> None:
    """numeric -> menu -> range form: equal bounds -> error, then create."""
    hass.states.async_set("sensor.fridge_temp", "4")
    result = await _to_numeric_menu(hass, "sensor.fridge_temp", "4")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "numeric_range"}
    )
    assert result["step_id"] == "numeric_range"

    # Equal bounds -> validation error, form re-shown.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DIRECTION: DIRECTION_OUTSIDE,
            CONF_RANGE_LOW: 5,
            CONF_RANGE_HIGH: 5,
            CONF_UNAVAILABLE_IS: UNAVAILABLE_PROBLEM,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_RANGE_LOW: "range_equal"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DIRECTION: DIRECTION_OUTSIDE,
            CONF_RANGE_LOW: 1,
            CONF_RANGE_HIGH: 5,
            CONF_UNAVAILABLE_IS: UNAVAILABLE_PROBLEM,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_RANGE_LOW] == 1
    assert result["data"][CONF_RANGE_HIGH] == 5
    assert CONF_THRESHOLD not in result["data"]


async def test_monitored_entity_options_flow(hass: HomeAssistant) -> None:
    """The options flow re-shows a numeric menu and rewrites the params."""
    hass.states.async_set("sensor.laptop_battery", "42")
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Laptop Battery status",
        data={
            CONF_HELPER_TYPE: HELPER_MONITORED_ENTITY,
            CONF_ENTITY_ID: "sensor.laptop_battery",
            CONF_NAME: "Laptop Battery status",
            CONF_LABELS: [],
            CONF_KIND: KIND_NUMERIC,
            CONF_THRESHOLD: 20,
            CONF_DIRECTION: DIRECTION_BELOW,
            CONF_UNAVAILABLE_IS: UNAVAILABLE_PROBLEM,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "retune_numeric_kind"
    # the current mode (threshold) is marked; range is not
    assert "current" in result["menu_options"]["retune_threshold"]
    assert "current" not in result["menu_options"]["retune_range"]
    assert result["description_placeholders"]["current_mode"] == "a threshold"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "retune_threshold"}
    )
    assert result["step_id"] == "retune_threshold"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_THRESHOLD: 15,
            CONF_DIRECTION: DIRECTION_BELOW,
            CONF_UNAVAILABLE_IS: UNAVAILABLE_PROBLEM,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_THRESHOLD] == 15
