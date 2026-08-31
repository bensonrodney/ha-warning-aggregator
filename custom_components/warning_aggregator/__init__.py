"""The Warning Aggregator integration."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.loader import async_get_integration

from .const import (
    CARD_FILENAME,
    CARD_URL,
    CONF_HELPER_TYPE,
    CONF_LABELS,
    CONF_MATCH,
    CONF_PROBLEM_STATES,
    DATA_CARD_REGISTERED,
    DEFAULT_MATCH,
    DEFAULT_PROBLEM_STATES,
    DOMAIN,
    HELPER_AGGREGATOR,
    HELPER_MONITORED_ENTITY,
)
from .coordinator import WarningAggregatorCoordinator

_LOGGER = logging.getLogger(__name__)

AGGREGATOR_PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]
MONITORED_ENTITY_PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR]

type WarningAggregatorConfigEntry = ConfigEntry[WarningAggregatorCoordinator]


def _helper_type(entry: ConfigEntry) -> str:
    return entry.data.get(CONF_HELPER_TYPE, HELPER_AGGREGATOR)


def _platforms(entry: ConfigEntry) -> list[Platform]:
    if _helper_type(entry) == HELPER_MONITORED_ENTITY:
        return MONITORED_ENTITY_PLATFORMS
    return AGGREGATOR_PLATFORMS


async def async_setup_entry(
    hass: HomeAssistant, entry: WarningAggregatorConfigEntry
) -> bool:
    """Set up a helper from a config entry."""
    await _async_register_card(hass)

    if _helper_type(entry) == HELPER_AGGREGATOR:
        settings = {**entry.data, **entry.options}
        coordinator = WarningAggregatorCoordinator(
            hass,
            name=entry.title,
            label_ids=settings.get(CONF_LABELS, []),
            match=settings.get(CONF_MATCH, DEFAULT_MATCH),
            problem_states=settings.get(CONF_PROBLEM_STATES, DEFAULT_PROBLEM_STATES),
        )
        coordinator.async_start()
        entry.runtime_data = coordinator

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, _platforms(entry))

    if _helper_type(entry) == HELPER_MONITORED_ENTITY:
        _async_apply_labels(hass, entry)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: WarningAggregatorConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, _platforms(entry)
    )
    if unload_ok and _helper_type(entry) == HELPER_AGGREGATOR:
        entry.runtime_data.async_stop()
    return unload_ok


async def _async_update_listener(
    hass: HomeAssistant, entry: WarningAggregatorConfigEntry
) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _async_apply_labels(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Keep the monitored-entity sensor's labels in sync with its config."""
    labels = set(entry.data.get(CONF_LABELS) or [])
    if not labels:
        return
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("binary_sensor", DOMAIN, entry.entry_id)
    if entity_id is None:
        return
    current = registry.async_get(entity_id)
    if current and current.labels != labels:
        registry.async_update_entity(entity_id, labels=labels)


async def _async_register_card(hass: HomeAssistant) -> None:
    """Serve the bundled Lovelace card and load it on the frontend (once)."""
    if hass.data.get(DATA_CARD_REGISTERED):
        return
    if "frontend" not in hass.config.components or "http" not in hass.config.components:
        # No frontend/http (e.g. a minimal test rig) — nothing to serve.
        return
    hass.data[DATA_CARD_REGISTERED] = True

    # Imported lazily so the integration still loads where frontend is absent.
    from homeassistant.components.frontend import add_extra_js_url
    from homeassistant.components.http import StaticPathConfig

    try:
        integration = await async_get_integration(hass, DOMAIN)
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    CARD_URL,
                    str(Path(__file__).parent / "frontend" / CARD_FILENAME),
                    False,
                )
            ]
        )
        add_extra_js_url(hass, f"{CARD_URL}?v={integration.version}")
    except Exception:
        hass.data[DATA_CARD_REGISTERED] = False
        _LOGGER.warning("Could not register the Warning Aggregator card", exc_info=True)
