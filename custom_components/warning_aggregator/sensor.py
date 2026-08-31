"""Sensor platform: a count of tripped entities, handy for cards and graphs."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WarningAggregatorConfigEntry
from .const import (
    ATTR_PROBLEM_ENTITIES,
    ATTR_PROBLEM_NAMES,
    CONF_HELPER_TYPE,
    HELPER_MONITORED_ENTITY,
)
from .entity import WarningAggregatorEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WarningAggregatorConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the problem-count sensor (aggregator entries only)."""
    if entry.data.get(CONF_HELPER_TYPE) == HELPER_MONITORED_ENTITY:
        return
    async_add_entities([WarningAggregatorProblemCountSensor(entry)])


class WarningAggregatorProblemCountSensor(WarningAggregatorEntity, SensorEntity):
    """Number of watched entities currently in a problem state."""

    _attr_translation_key = "problem_count"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "problems"
    _attr_icon = "mdi:alert-circle-outline"

    def __init__(self, entry: WarningAggregatorConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_problem_count"

    @property
    def native_value(self) -> int:
        """Return the number of tripped entities."""
        return len(self.coordinator.problem_entities)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the tripped entities alongside the count."""
        return {
            ATTR_PROBLEM_ENTITIES: self.coordinator.problem_entities,
            ATTR_PROBLEM_NAMES: self.coordinator.problem_names(),
        }
