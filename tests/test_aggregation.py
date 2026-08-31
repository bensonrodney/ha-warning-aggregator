"""End-to-end behaviour: labelled entities drive the aggregator."""

from __future__ import annotations

from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, label_registry as lr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.warning_aggregator.const import (
    CONF_LABELS,
    CONF_MATCH,
    CONF_PROBLEM_STATES,
    DOMAIN,
    MATCH_ALL,
    MATCH_ANY,
)


def _register_labelled_entity(
    hass: HomeAssistant, object_id: str, label_ids: set[str]
) -> str:
    registry = er.async_get(hass)
    entry = registry.async_get_or_create(
        "sensor", "warning_aggregator_test", object_id, suggested_object_id=object_id
    )
    registry.async_update_entity(entry.entity_id, labels=label_ids)
    return entry.entity_id


async def _setup(hass: HomeAssistant, **settings) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Aggregator",
        data={CONF_NAME: "Test Aggregator", **settings},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_any_label_match(hass: HomeAssistant) -> None:
    """A single tripped entity flips the aggregator on, and back off."""
    labels = lr.async_get(hass)
    monitored = labels.async_create("Monitored")

    e1 = _register_labelled_entity(hass, "check_one", {monitored.label_id})
    e2 = _register_labelled_entity(hass, "check_two", {monitored.label_id})
    hass.states.async_set(e1, "ok")
    hass.states.async_set(e2, "ok")

    await _setup(
        hass,
        **{
            CONF_LABELS: [monitored.label_id],
            CONF_MATCH: MATCH_ANY,
            CONF_PROBLEM_STATES: ["warning"],
        },
    )

    state = hass.states.get("binary_sensor.test_aggregator")
    assert state is not None
    assert state.state == "off"
    assert state.attributes["watched_count"] == 2

    hass.states.async_set(e2, "warning")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_aggregator")
    assert state.state == "on"
    assert state.attributes["problem_entities"] == [e2]
    assert hass.states.get("sensor.test_aggregator_problem_count").state == "1"

    hass.states.async_set(e2, "ok")
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.test_aggregator").state == "off"


async def test_label_added_later_is_picked_up(hass: HomeAssistant) -> None:
    """Labelling a new entity after setup adds it to the watch set."""
    labels = lr.async_get(hass)
    monitored = labels.async_create("Monitored")
    await _setup(
        hass,
        **{
            CONF_LABELS: [monitored.label_id],
            CONF_MATCH: MATCH_ANY,
            CONF_PROBLEM_STATES: ["warning"],
        },
    )
    assert hass.states.get("binary_sensor.test_aggregator").state == "off"

    e1 = _register_labelled_entity(hass, "late_check", {monitored.label_id})
    hass.states.async_set(e1, "warning")
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.test_aggregator").state == "on"


async def test_all_label_match_is_intersection(hass: HomeAssistant) -> None:
    """MATCH_ALL only watches entities carrying every configured label."""
    labels = lr.async_get(hass)
    batteries = labels.async_create("Batteries")
    outdoor = labels.async_create("Outdoor")

    both = _register_labelled_entity(
        hass, "outdoor_battery", {batteries.label_id, outdoor.label_id}
    )
    battery_only = _register_labelled_entity(
        hass, "indoor_battery", {batteries.label_id}
    )
    hass.states.async_set(both, "ok")
    hass.states.async_set(battery_only, "warning")

    await _setup(
        hass,
        **{
            CONF_LABELS: [batteries.label_id, outdoor.label_id],
            CONF_MATCH: MATCH_ALL,
            CONF_PROBLEM_STATES: ["warning"],
        },
    )

    state = hass.states.get("binary_sensor.test_aggregator")
    assert state.attributes["watched_count"] == 1
    assert state.state == "off"

    hass.states.async_set(both, "warning")
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.test_aggregator").state == "on"
