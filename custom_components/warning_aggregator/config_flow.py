"""Config and options flow for Warning Aggregator.

The integration ships two helper types:

* **monitored_entity** - watch one entity; the flow adapts to whether it is
  boolean, numeric or text and asks only the relevant questions.
* **aggregator** - roll a set of labelled entities up into one problem sensor.
"""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ENTITY_ID, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector
import voluptuous as vol

from .check import detect_kind
from .const import (
    BAD_STATE_OPTIONS,
    COMPARISON_OPTIONS,
    CONF_BAD_STATE,
    CONF_COMPARISON,
    CONF_DIRECTION,
    CONF_HELPER_TYPE,
    CONF_HYSTERESIS,
    CONF_KIND,
    CONF_LABELS,
    CONF_MATCH,
    CONF_MATCH_MODE,
    CONF_MATCH_TEXT,
    CONF_PROBLEM_STATES,
    CONF_THRESHOLD,
    CONF_UNAVAILABLE_IS,
    DEFAULT_MATCH,
    DEFAULT_PROBLEM_STATES,
    DIRECTION_BELOW,
    DIRECTION_OPTIONS,
    DOMAIN,
    HELPER_AGGREGATOR,
    HELPER_MONITORED_ENTITY,
    KIND_BOOLEAN,
    KIND_NUMERIC,
    MATCH_IS_BAD,
    MATCH_MODE_OPTIONS,
    MATCH_OPTIONS,
    UNAVAILABLE_OPTIONS,
    UNAVAILABLE_PROBLEM,
)

COMPARISON_EQUALS = COMPARISON_OPTIONS[0]


def _select(options: list[str], key: str) -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=options,
            translation_key=key,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


# --- aggregator ----------------------------------------------------------


def _aggregator_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_LABELS): selector.LabelSelector(
                selector.LabelSelectorConfig(multiple=True)
            ),
            vol.Required(CONF_MATCH, default=DEFAULT_MATCH): _select(
                MATCH_OPTIONS, "match"
            ),
            vol.Required(
                CONF_PROBLEM_STATES, default=list(DEFAULT_PROBLEM_STATES)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(DEFAULT_PROBLEM_STATES),
                    multiple=True,
                    custom_value=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )


# --- monitored entity --------------------------------------------------


def _kind_schema(kind: str, current_value: str | None) -> vol.Schema:
    """The per-kind question set, plus the shared 'no value' choice."""
    fields: dict[Any, Any] = {}

    if kind == KIND_BOOLEAN:
        fields[vol.Required(CONF_BAD_STATE, default="on")] = _select(
            BAD_STATE_OPTIONS, "bad_state"
        )
    elif kind == KIND_NUMERIC:
        suggested = _as_float(current_value)
        threshold_field = (
            vol.Required(CONF_THRESHOLD, default=suggested)
            if suggested is not None
            else vol.Required(CONF_THRESHOLD)
        )
        fields[threshold_field] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                mode=selector.NumberSelectorMode.BOX, step="any"
            )
        )
        fields[vol.Required(CONF_DIRECTION, default=DIRECTION_BELOW)] = _select(
            DIRECTION_OPTIONS, "direction"
        )
        fields[vol.Optional(CONF_HYSTERESIS, default=0)] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                mode=selector.NumberSelectorMode.BOX, step="any", min=0
            )
        )
    else:  # KIND_STRING
        fields[vol.Required(CONF_MATCH_TEXT)] = selector.TextSelector()
        fields[vol.Required(CONF_COMPARISON, default=COMPARISON_EQUALS)] = _select(
            COMPARISON_OPTIONS, "comparison"
        )
        fields[vol.Required(CONF_MATCH_MODE, default=MATCH_IS_BAD)] = _select(
            MATCH_MODE_OPTIONS, "match_mode"
        )

    fields[vol.Required(CONF_UNAVAILABLE_IS, default=UNAVAILABLE_PROBLEM)] = _select(
        UNAVAILABLE_OPTIONS, "unavailable_is"
    )
    return vol.Schema(fields)


def _as_float(raw: str | None) -> float | None:
    try:
        return float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _default_name(hass, entity_id: str) -> str:
    state = hass.states.get(entity_id)
    friendly = state.attributes.get("friendly_name") if state else None
    return f"{friendly or entity_id} status"


class WarningAggregatorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Root config flow - pick a helper type, then configure it."""

    VERSION = 1

    def __init__(self) -> None:
        self._me: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer the two helper types."""
        return self.async_show_menu(
            step_id="user",
            menu_options=[HELPER_MONITORED_ENTITY, HELPER_AGGREGATOR],
        )

    # -- monitored entity ------------------------------------------------

    async def async_step_monitored_entity(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the entity to watch; detect its kind."""
        if user_input is not None:
            entity_id = user_input[CONF_ENTITY_ID]
            self._me = {
                CONF_HELPER_TYPE: HELPER_MONITORED_ENTITY,
                CONF_ENTITY_ID: entity_id,
                CONF_NAME: (user_input.get(CONF_NAME) or "").strip()
                or _default_name(self.hass, entity_id),
                CONF_LABELS: user_input.get(CONF_LABELS, []),
                CONF_KIND: detect_kind(self.hass.states.get(entity_id)),
            }
            return await self.async_step_configure_check()

        schema = vol.Schema(
            {
                vol.Required(CONF_ENTITY_ID): selector.EntitySelector(),
                vol.Optional(CONF_NAME): selector.TextSelector(),
                vol.Optional(CONF_LABELS, default=[]): selector.LabelSelector(
                    selector.LabelSelectorConfig(multiple=True)
                ),
            }
        )
        return self.async_show_form(
            step_id="monitored_entity",
            data_schema=self.add_suggested_values_to_schema(schema, user_input or {}),
        )

    async def async_step_configure_check(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask only the questions that matter for the detected kind."""
        kind = self._me[CONF_KIND]
        state = self.hass.states.get(self._me[CONF_ENTITY_ID])

        if user_input is not None:
            return self.async_create_entry(
                title=self._me[CONF_NAME],
                data={**self._me, **user_input},
            )

        return self.async_show_form(
            step_id="configure_check",
            data_schema=_kind_schema(kind, state.state if state else None),
            description_placeholders={
                "entity": self._me[CONF_ENTITY_ID],
                "kind": kind,
                "value": state.state if state else "unavailable",
            },
        )

    # -- aggregator ----------------------------------------------------

    async def async_step_aggregator(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure a label aggregator."""
        errors: dict[str, str] = {}

        if user_input is not None:
            name = (user_input.get(CONF_NAME) or "").strip()
            if not name:
                errors[CONF_NAME] = "name_required"
            elif not user_input[CONF_LABELS]:
                errors[CONF_LABELS] = "labels_required"
            else:
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_HELPER_TYPE: HELPER_AGGREGATOR,
                        CONF_LABELS: user_input[CONF_LABELS],
                        CONF_MATCH: user_input[CONF_MATCH],
                        CONF_PROBLEM_STATES: user_input[CONF_PROBLEM_STATES],
                    },
                )

        schema = vol.Schema({vol.Required(CONF_NAME): selector.TextSelector()}).extend(
            _aggregator_schema().schema
        )
        return self.async_show_form(
            step_id="aggregator",
            data_schema=self.add_suggested_values_to_schema(schema, user_input or {}),
            errors=errors,
        )

    # -- options ----------------------------------------------------

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow matching the entry's helper type."""
        if config_entry.data.get(CONF_HELPER_TYPE) == HELPER_MONITORED_ENTITY:
            return MonitoredEntityOptionsFlow()
        return AggregatorOptionsFlow()


class AggregatorOptionsFlow(OptionsFlow):
    """Edit an aggregator's labels, match mode and problem states."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input[CONF_LABELS]:
                errors[CONF_LABELS] = "labels_required"
            else:
                return self.async_create_entry(data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                _aggregator_schema(), user_input or current
            ),
            errors=errors,
        )


class MonitoredEntityOptionsFlow(OptionsFlow):
    """Re-tune the check thresholds for an already-chosen entity."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        kind = current[CONF_KIND]
        state = self.hass.states.get(current[CONF_ENTITY_ID])
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                _kind_schema(kind, state.state if state else None), current
            ),
            description_placeholders={
                "entity": current[CONF_ENTITY_ID],
                "kind": kind,
                "value": state.state if state else "unavailable",
            },
        )
