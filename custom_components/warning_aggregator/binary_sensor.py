"""Binary sensor platform.

* aggregator entry  -> one aggregated `problem` sensor
* monitored_entity entry -> one `problem` sensor for a single watched entity
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    ENTITY_ID_FORMAT,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import CONF_ENTITY_ID, STATE_ON
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import (
    TrackTemplate,
    TrackTemplateResult,
    async_track_state_change_event,
    async_track_template_result,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.template import Template, result_as_boolean

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
    CONF_REASON_TEMPLATE,
    CONF_UNAVAILABLE_IS,
    CONF_VALUE_TEMPLATE,
    ENTITY_ID_PREFIX,
    HELPER_MONITORED_ENTITY,
    KIND_TEMPLATE,
    UNAVAILABLE_PROBLEM,
)
from .entity import WarningAggregatorEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WarningAggregatorConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensor for this entry."""
    if entry.data.get(CONF_HELPER_TYPE) == HELPER_MONITORED_ENTITY:
        sensor = MonitoredEntityBinarySensor(entry)
        # Seed a prefixed entity_id (e.g. binary_sensor.warn_agg_ups_battery) so
        # every monitor groups together; only applied on first creation.
        sensor.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, f"{ENTITY_ID_PREFIX}{entry.title}", hass=hass
        )
        async_add_entities([sensor])
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
    """`on` (a problem) when the watched entity / template fails its check."""

    _attr_should_poll = False
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, entry: WarningAggregatorConfigEntry) -> None:
        """Initialise from the config entry."""
        self._params: dict[str, Any] = {**entry.data, **entry.options}
        self._kind: str = self._params[CONF_KIND]
        self._watched: str | None = self._params.get(CONF_ENTITY_ID)
        self._attr_unique_id = entry.entry_id
        self._attr_name = entry.title
        self._attr_is_on = False
        self._reason = "unknown"
        self._tmpl_results: dict[Template, Any] = {}
        self._value_tmpl: Template | None = None
        self._reason_tmpl: Template | None = None

    @property
    def _unavailable_is_problem(self) -> bool:
        return (
            self._params.get(CONF_UNAVAILABLE_IS, UNAVAILABLE_PROBLEM)
            == UNAVAILABLE_PROBLEM
        )

    async def async_added_to_hass(self) -> None:
        """Restore prior state, then start tracking."""
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            self._attr_is_on = last.state == STATE_ON

        if self._kind == KIND_TEMPLATE:
            self._attach_template()
        else:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, [self._watched], self._handle_change
                )
            )
            self._recalculate()

    # -- state-based kinds -------------------------------------------

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

    # -- template kind ----------------------------------------------

    def _attach_template(self) -> None:
        self._value_tmpl = Template(self._params[CONF_VALUE_TEMPLATE], self.hass)
        tracks = [TrackTemplate(self._value_tmpl, None)]
        if reason_src := self._params.get(CONF_REASON_TEMPLATE):
            self._reason_tmpl = Template(reason_src, self.hass)
            tracks.append(TrackTemplate(self._reason_tmpl, None))

        info = async_track_template_result(self.hass, tracks, self._handle_template)
        self.async_on_remove(info.async_remove)
        info.async_refresh()

    @callback
    def _handle_template(
        self,
        event: Event | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        for update in updates:
            self._tmpl_results[update.template] = update.result

        value = self._tmpl_results.get(self._value_tmpl)
        if value is None or isinstance(value, TemplateError):
            self._attr_is_on = self._unavailable_is_problem
            self._reason = (
                f"template error: {value}"
                if isinstance(value, TemplateError)
                else "template not evaluated yet"
            )
        else:
            self._attr_is_on = result_as_boolean(value)
            self._reason = self._template_reason(value)

        if event is not None:
            self.async_write_ha_state()

    def _template_reason(self, value: Any) -> str:
        if self._reason_tmpl is not None:
            reason = self._tmpl_results.get(self._reason_tmpl)
            if reason is not None and not isinstance(reason, TemplateError):
                return str(reason)
        return f"template rendered {value!r}"

    # -- attributes ------------------------------------------------

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose what is being watched and why the check tripped."""
        attrs: dict[str, Any] = {ATTR_KIND: self._kind, ATTR_REASON: self._reason}
        if self._kind == KIND_TEMPLATE:
            attrs[CONF_VALUE_TEMPLATE] = self._params[CONF_VALUE_TEMPLATE]
        else:
            watched = self.hass.states.get(self._watched)
            attrs[ATTR_WATCHED_ENTITY] = self._watched
            attrs[ATTR_WATCHED_STATE] = watched.state if watched else None
        return attrs
