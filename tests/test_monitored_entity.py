"""End-to-end behaviour of a monitored-entity helper."""

from __future__ import annotations

from homeassistant.const import CONF_ENTITY_ID, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, label_registry as lr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.warning_aggregator.const import (
    CONF_BAD_STATE,
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
    KIND_BOOLEAN,
    KIND_NUMERIC,
    MATCH_ANY,
    UNAVAILABLE_OK,
    UNAVAILABLE_PROBLEM,
)


async def _add(hass: HomeAssistant, title: str, data: dict) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=title,
        data={CONF_HELPER_TYPE: HELPER_MONITORED_ENTITY, CONF_NAME: title, **data},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_numeric_monitor_tracks_threshold(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.battery", "55")
    await _add(
        hass,
        "Battery status",
        {
            CONF_ENTITY_ID: "sensor.battery",
            CONF_LABELS: [],
            CONF_KIND: KIND_NUMERIC,
            CONF_THRESHOLD: 20,
            CONF_DIRECTION: DIRECTION_BELOW,
            CONF_UNAVAILABLE_IS: UNAVAILABLE_PROBLEM,
        },
    )

    state = hass.states.get("binary_sensor.warn_agg_battery_status")
    assert state is not None
    assert state.state == "off"
    assert state.attributes["device_class"] == "problem"

    hass.states.async_set("sensor.battery", "12")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.warn_agg_battery_status")
    assert state.state == "on"
    assert "12" in state.attributes["reason"]

    hass.states.async_set("sensor.battery", "unavailable")
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.warn_agg_battery_status").state == "on"


async def test_entity_id_is_prefixed(hass: HomeAssistant) -> None:
    """Monitors get a `warn_agg_` entity_id so they group in the entity list."""
    hass.states.async_set("sensor.battery", "55")
    await _add(
        hass,
        "UPS Battery",
        {
            CONF_ENTITY_ID: "sensor.battery",
            CONF_LABELS: [],
            CONF_KIND: KIND_NUMERIC,
            CONF_THRESHOLD: 20,
            CONF_DIRECTION: DIRECTION_BELOW,
            CONF_UNAVAILABLE_IS: UNAVAILABLE_PROBLEM,
        },
    )

    state = hass.states.get("binary_sensor.warn_agg_ups_battery")
    assert state is not None
    # friendly name stays clean (prefix is only on the entity_id)
    assert state.attributes["friendly_name"] == "UPS Battery"


async def test_unavailable_can_be_treated_as_ok(hass: HomeAssistant) -> None:
    hass.states.async_set("binary_sensor.link", "off")
    await _add(
        hass,
        "Link status",
        {
            CONF_ENTITY_ID: "binary_sensor.link",
            CONF_LABELS: [],
            CONF_KIND: KIND_BOOLEAN,
            CONF_BAD_STATE: "on",
            CONF_UNAVAILABLE_IS: UNAVAILABLE_OK,
        },
    )
    assert hass.states.get("binary_sensor.warn_agg_link_status").state == "off"

    hass.states.async_set("binary_sensor.link", "unavailable")
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.warn_agg_link_status").state == "off"


async def test_labels_applied_and_aggregator_picks_it_up(hass: HomeAssistant) -> None:
    """A labelled monitored-entity sensor trips its aggregator without config."""
    labels = lr.async_get(hass)
    monitored = labels.async_create("Monitored")

    hass.states.async_set("sensor.battery", "10")
    await _add(
        hass,
        "Battery status",
        {
            CONF_ENTITY_ID: "sensor.battery",
            CONF_LABELS: [monitored.label_id],
            CONF_KIND: KIND_NUMERIC,
            CONF_THRESHOLD: 20,
            CONF_DIRECTION: DIRECTION_BELOW,
            CONF_UNAVAILABLE_IS: UNAVAILABLE_PROBLEM,
        },
    )

    registry = er.async_get(hass)
    entity = registry.async_get("binary_sensor.warn_agg_battery_status")
    assert entity is not None
    assert entity.labels == {monitored.label_id}

    agg = MockConfigEntry(
        domain=DOMAIN,
        title="System",
        data={
            CONF_HELPER_TYPE: HELPER_AGGREGATOR,
            CONF_NAME: "System",
            CONF_LABELS: [monitored.label_id],
            CONF_MATCH: MATCH_ANY,
            CONF_PROBLEM_STATES: [],  # rely on device_class problem detection
        },
    )
    agg.add_to_hass(hass)
    assert await hass.config_entries.async_setup(agg.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.system")
    assert state.state == "on"
    assert state.attributes["problem_entities"] == [
        "binary_sensor.warn_agg_battery_status"
    ]
