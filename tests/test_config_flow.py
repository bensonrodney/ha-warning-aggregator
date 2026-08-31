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
    CONF_THRESHOLD,
    CONF_UNAVAILABLE_IS,
    DIRECTION_BELOW,
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


async def test_monitored_entity_flow_numeric(hass: HomeAssistant) -> None:
    """Menu -> monitored entity -> the numeric check form -> create entry."""
    hass.states.async_set(
        "sensor.laptop_battery", "42", {"friendly_name": "Laptop Battery"}
    )

    flow_id = await _menu(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"next_step_id": HELPER_MONITORED_ENTITY}
    )
    assert result["step_id"] == HELPER_MONITORED_ENTITY

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ENTITY_ID: "sensor.laptop_battery", CONF_LABELS: []},
    )
    # Detected as numeric -> the threshold form.
    assert result["step_id"] == "configure_check"
    assert result["description_placeholders"]["kind"] == KIND_NUMERIC

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
    assert result["data"][CONF_HELPER_TYPE] == HELPER_MONITORED_ENTITY
    assert result["data"][CONF_KIND] == KIND_NUMERIC
    assert result["data"][CONF_THRESHOLD] == 20


async def test_monitored_entity_options_flow(hass: HomeAssistant) -> None:
    """The options flow re-shows the per-kind form and rewrites the params."""
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
    assert result["type"] is FlowResultType.FORM

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
