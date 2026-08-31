"""Tracks labelled entities and computes the aggregated problem state."""

from __future__ import annotations

from collections.abc import Callable
import logging

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_ON
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er, label_registry as lr
from homeassistant.helpers.event import async_track_state_change_event

from .const import MATCH_ALL

_LOGGER = logging.getLogger(__name__)

ATTR_FRIENDLY_NAME = "friendly_name"
DEVICE_CLASS_PROBLEM = BinarySensorDeviceClass.PROBLEM


class WarningAggregatorCoordinator:
    """Watch every entity carrying the configured label(s) and derive a problem state.

    This is deliberately *not* a ``DataUpdateCoordinator`` - there is nothing to
    poll. It reacts to:

    * state changes of any watched entity
    * entity-registry changes (an entity gained/lost the label, was added/removed)
    * label-registry changes (a label was renamed/removed)

    and pushes a fresh result to the platform entities via registered callbacks.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        name: str,
        label_ids: list[str],
        match: str,
        problem_states: list[str],
    ) -> None:
        """Initialise the coordinator."""
        self.hass = hass
        self.name = name
        self.label_ids: list[str] = sorted(label_ids)
        self.match = match
        self.problem_states: set[str] = {s.strip() for s in problem_states if s.strip()}

        self.watched_entities: set[str] = set()
        self.problem_entities: list[str] = []

        self._listeners: list[Callable[[], None]] = []
        self._unsub_state: Callable[[], None] | None = None
        self._unsub_registry: list[Callable[[], None]] = []

    # -- lifecycle ---------------------------------------------------------

    @callback
    def async_start(self) -> None:
        """Begin tracking. Safe to call once, from ``async_setup_entry``."""
        self._unsub_registry.append(
            self.hass.bus.async_listen(
                er.EVENT_ENTITY_REGISTRY_UPDATED, self._handle_entity_registry_change
            )
        )
        self._unsub_registry.append(
            self.hass.bus.async_listen(
                lr.EVENT_LABEL_REGISTRY_UPDATED, self._handle_label_registry_change
            )
        )
        self._async_refresh_watched()
        self._async_recompute()

    @callback
    def async_stop(self) -> None:
        """Tear down all subscriptions."""
        if self._unsub_state is not None:
            self._unsub_state()
            self._unsub_state = None
        for unsub in self._unsub_registry:
            unsub()
        self._unsub_registry.clear()

    # -- listener registration ------------------------------------------

    @callback
    def async_add_listener(
        self, update_callback: Callable[[], None]
    ) -> Callable[[], None]:
        """Register a callback fired whenever the aggregated result may have changed."""
        self._listeners.append(update_callback)

        def _remove() -> None:
            self._listeners.remove(update_callback)

        return _remove

    @callback
    def _async_notify_listeners(self) -> None:
        for update_callback in list(self._listeners):
            update_callback()

    # -- derived values -------------------------------------------------

    @property
    def problem(self) -> bool:
        """Whether at least one watched entity is in a problem state."""
        return bool(self.problem_entities)

    @callback
    def problem_names(self) -> list[str]:
        """Friendly names of the tripped entities (falls back to entity_id)."""
        names: list[str] = []
        for entity_id in self.problem_entities:
            state = self.hass.states.get(entity_id)
            if state is None:
                names.append(entity_id)
            else:
                names.append(state.attributes.get(ATTR_FRIENDLY_NAME, entity_id))
        return names

    # -- computation ---------------------------------------------------

    @callback
    def _async_refresh_watched(self) -> None:
        """Recompute the watched entity set and (re)subscribe to state changes."""
        registry = er.async_get(self.hass)

        if not self.label_ids:
            entities: set[str] = set()
        elif self.match == MATCH_ALL:
            per_label = [
                {
                    entry.entity_id
                    for entry in er.async_entries_for_label(registry, label_id)
                }
                for label_id in self.label_ids
            ]
            entities = set.intersection(*per_label) if per_label else set()
        else:  # MATCH_ANY
            entities = set()
            for label_id in self.label_ids:
                entities.update(
                    entry.entity_id
                    for entry in er.async_entries_for_label(registry, label_id)
                )

        if entities == self.watched_entities:
            return

        self.watched_entities = entities
        if self._unsub_state is not None:
            self._unsub_state()
            self._unsub_state = None
        if entities:
            self._unsub_state = async_track_state_change_event(
                self.hass, list(entities), self._handle_state_change
            )

    @callback
    def _async_recompute(self) -> None:
        """Rebuild the list of tripped entities from current states.

        An entity counts as tripped when its state is one of ``problem_states``
        OR it is an ``on`` binary sensor with device class ``problem`` (so the
        integration's own monitored-entity sensors work once labelled).
        """
        problems: list[str] = []
        for entity_id in self.watched_entities:
            state = self.hass.states.get(entity_id)
            if state is None:
                continue
            if state.state in self.problem_states or (
                state.state == STATE_ON
                and state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_PROBLEM
            ):
                problems.append(entity_id)
        self.problem_entities = sorted(problems)

    # -- event handlers ----------------------------------------------

    @callback
    def _handle_state_change(self, event: Event) -> None:
        self._async_recompute()
        self._async_notify_listeners()

    @callback
    def _handle_entity_registry_change(self, event: Event) -> None:
        action = event.data["action"]
        if action == "update":
            entity_id = event.data["entity_id"]
            if "labels" not in event.data.get("changes", {}) and (
                entity_id not in self.watched_entities
            ):
                return
        self._async_refresh_watched()
        self._async_recompute()
        self._async_notify_listeners()

    @callback
    def _handle_label_registry_change(self, event: Event) -> None:
        self._async_refresh_watched()
        self._async_recompute()
        self._async_notify_listeners()
