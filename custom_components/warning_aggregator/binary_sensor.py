"""Binary sensor platform.

* aggregator entry  -> one aggregated `problem` sensor
* monitored_entity entry -> one `problem` sensor for a single watched entity
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import CONF_ENTITY_ID, STATE_ON
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity

from . import WarningAggregatorConfigEntry
from .check import evaluate
from .const import (
    ATTR_KIND,
    ATTR_LABELS,
    ATTR_MATCH,
    ATTR_PROBLEM_COUNT,
    ATTR_PROBLEM_ENTITIES,
    ATTR_PROBLEM_NAMES,
    ATTR_REASON,
    ATTR_WATCHED_COUNT,
    ATTR_WATCHED_ENTITIES,
    ATTR_WATCHED_ENTITY,
    ATTR_WATCHED_STATE,
    CONF_HELPER_TYPE,
    CONF_KIND,
    HELPER_MONITORED_ENTITY,
)
from .entity import WarningAggregatorEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WarningAggregatorConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensor for this entry."""
    if entry.data.get(CONF_HELPER_TYPE) == HELPER_MONITORED_ENTITY:
        async_add_entities([MonitoredEntityBinarySensor(entry)])
    else:
        async_add_entities([WarningAggregatorBinarySensor(entry)])


class WarningAggregatorBinarySensor(WarningAggregatorEntity, BinarySensorEntity):
    """`on` when at least one watched entity is in a problem state."""

    _attr_name = None
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, entry: WarningAggregatorConfigEntry) -> None:
        """Initialise the binary sensor."""
        super().__init__(entry)
        self._attr_unique_id = entry.entry_id

    @property
    def is_on(self) -> bool:
        """Return the aggregated problem state."""
        return self.coordinator.problem

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the breakdown used by cards and notifications."""
        return {
            ATTR_PROBLEM_ENTITIES: self.coordinator.problem_entities,
            ATTR_PROBLEM_NAMES: self.coordinator.problem_names(),
            ATTR_PROBLEM_COUNT: len(self.coordinator.problem_entities),
            ATTR_WATCHED_COUNT: len(self.coordinator.watched_entities),
            ATTR_WATCHED_ENTITIES: sorted(self.coordinator.watched_entities),
            ATTR_LABELS: self.coordinator.label_ids,
            ATTR_MATCH: self.coordinator.match,
        }


class MonitoredEntityBinarySensor(RestoreEntity, BinarySensorEntity):
    """`on` (a problem) when the watched entity fails its check."""

    _attr_should_poll = False
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, entry: WarningAggregatorConfigEntry) -> None:
        """Initialise from the config entry."""
        self._params: dict[str, Any] = {**entry.data, **entry.options}
        self._watched: str = self._params[CONF_ENTITY_ID]
        self._kind: str = self._params[CONF_KIND]
        self._attr_unique_id = entry.entry_id
        self._attr_name = entry.title
        self._attr_is_on = False
        self._reason = "unknown"

    async def async_added_to_hass(self) -> None:
        """Restore prior state, then start tracking the watched entity."""
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            self._attr_is_on = last.state == STATE_ON

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._watched], self._handle_change
            )
        )
        self._recalculate()

    @callback
    def _handle_change(self, event: Event) -> None:
        self._recalculate(write=True)

    @callback
    def _recalculate(self, *, write: bool = False) -> None:
        result = evaluate(
            self._kind,
            self._params,
            self.hass.states.get(self._watched),
            currently_problem=self._attr_is_on,
        )
        self._attr_is_on = result.problem
        self._reason = result.reason
        if write:
            self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose what is being watched and why the check tripped."""
        watched = self.hass.states.get(self._watched)
        return {
            ATTR_WATCHED_ENTITY: self._watched,
            ATTR_WATCHED_STATE: watched.state if watched else None,
            ATTR_KIND: self._kind,
            ATTR_REASON: self._reason,
        }
