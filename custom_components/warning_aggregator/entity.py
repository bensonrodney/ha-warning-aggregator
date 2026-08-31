"""Shared base entity for the Warning Aggregator platforms."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from . import WarningAggregatorConfigEntry
from .const import DOMAIN
from .coordinator import WarningAggregatorCoordinator


class WarningAggregatorEntity(Entity):
    """Base class wiring an entity to its coordinator."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: WarningAggregatorConfigEntry) -> None:
        """Initialise common attributes."""
        self.coordinator: WarningAggregatorCoordinator = entry.runtime_data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
