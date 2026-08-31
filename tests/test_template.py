"""The template-check monitored entity."""

from __future__ import annotations

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.warning_aggregator.const import (
    CONF_KIND,
    CONF_LABELS,
    CONF_REASON_TEMPLATE,
    CONF_UNAVAILABLE_IS,
    CONF_VALUE_TEMPLATE,
    DOMAIN,
    KIND_TEMPLATE,
    UNAVAILABLE_OK,
    UNAVAILABLE_PROBLEM,
)


async def _create(hass: HomeAssistant, form: dict) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "template"}
    )
    assert result["step_id"] == "template"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], form)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_KIND] == KIND_TEMPLATE
    await hass.async_block_till_done()


async def test_template_tracks_truthiness(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.foo", "5")
    await _create(
        hass,
        {
            CONF_NAME: "Foo check",
            CONF_VALUE_TEMPLATE: "{{ states('sensor.foo') | int(0) < 10 }}",
            CONF_REASON_TEMPLATE: "foo is {{ states('sensor.foo') }}",
            CONF_UNAVAILABLE_IS: UNAVAILABLE_PROBLEM,
            CONF_LABELS: [],
        },
    )

    state = hass.states.get("binary_sensor.warn_agg_foo_check")
    assert state is not None
    assert state.state == "on"  # 5 < 10 -> truthy -> problem
    assert state.attributes["device_class"] == "problem"
    assert state.attributes["reason"] == "foo is 5"

    hass.states.async_set("sensor.foo", "42")
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.warn_agg_foo_check").state == "off"


async def test_template_error_uses_unavailable_rule(hass: HomeAssistant) -> None:
    await _create(
        hass,
        {
            CONF_NAME: "Broken",
            CONF_VALUE_TEMPLATE: "{{ 1 / 0 }}",
            CONF_UNAVAILABLE_IS: UNAVAILABLE_OK,
            CONF_LABELS: [],
        },
    )
    assert hass.states.get("binary_sensor.warn_agg_broken").state == "off"
