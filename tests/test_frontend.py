"""The bundled Lovelace card is served and loaded on the frontend."""

from __future__ import annotations

from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.warning_aggregator.const import (
    CARD_URL,
    CONF_LABELS,
    CONF_MATCH,
    CONF_PROBLEM_STATES,
    DOMAIN,
    MATCH_ANY,
)


async def test_card_is_registered_on_the_frontend(hass: HomeAssistant) -> None:
    """Setting up an entry serves the card file and adds it as an extra module."""
    if not await async_setup_component(hass, "frontend", {}):
        pytest.skip("frontend not available in this test environment")

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Aggregator",
        data={
            CONF_NAME: "Test Aggregator",
            CONF_LABELS: ["monitored"],
            CONF_MATCH: MATCH_ANY,
            CONF_PROBLEM_STATES: ["warning"],
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL

    urls = hass.data[DATA_EXTRA_MODULE_URL]
    assert any(CARD_URL in url for url in urls.urls)
