"""Config and options flow for Warning Aggregator.

Helper types offered by the menu:

* **monitored_entity** - watch one entity; the flow adapts to whether it is
  boolean, numeric or text and asks only the relevant questions.
* **template** - a monitored_entity whose check is a Jinja template (the
  escape hatch when the built-in kinds don't fit).
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
    CONF_RANGE_HIGH,
    CONF_RANGE_LOW,
    CONF_REASON_TEMPLATE,
    CONF_THRESHOLD,
    CONF_UNAVAILABLE_IS,
    CONF_VALUE_TEMPLATE,
    DEFAULT_MATCH,
    DEFAULT_PROBLEM_STATES,
    DIRECTION_BELOW,
    DIRECTION_OUTSIDE,
    DIRECTION_RANGE,
    DIRECTION_RANGE_ORDER,
    DIRECTION_THRESHOLD_ORDER,
    DOMAIN,
    HELPER_AGGREGATOR,
    HELPER_MONITORED_ENTITY,
    KIND_BOOLEAN,
    KIND_NUMERIC,
    KIND_TEMPLATE,
    MATCH_IS_BAD,
    MATCH_MODE_OPTIONS,
    MATCH_OPTIONS,
    UNAVAILABLE_OPTIONS,
    UNAVAILABLE_PROBLEM,
)

COMPARISON_EQUALS = COMPARISON_OPTIONS[0]


def _number(*, non_negative: bool = False) -> selector.NumberSelector:
    cfg = selector.NumberSelectorConfig(
        mode=selector.NumberSelectorMode.BOX, step="any"
    )
    if non_negative:
        cfg["min"] = 0
    return selector.NumberSelector(cfg)


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


def _unavailable_field() -> dict[Any, Any]:
    return {
        vol.Required(CONF_UNAVAILABLE_IS, default=UNAVAILABLE_PROBLEM): _select(
            UNAVAILABLE_OPTIONS, "unavailable_is"
        )
    }


def _kind_schema(kind: str) -> vol.Schema:
    """The per-kind question set for boolean / string / template, plus 'no value'.

    Numeric is handled separately (a threshold or a range — never both) via
    ``_numeric_threshold_schema`` / ``_numeric_range_schema``.
    """
    fields: dict[Any, Any] = {}

    if kind == KIND_TEMPLATE:
        fields[vol.Required(CONF_VALUE_TEMPLATE)] = selector.TemplateSelector()
        fields[vol.Optional(CONF_REASON_TEMPLATE)] = selector.TemplateSelector()
    elif kind == KIND_BOOLEAN:
        fields[vol.Required(CONF_BAD_STATE, default="on")] = _select(
            BAD_STATE_OPTIONS, "bad_state"
        )
    else:  # KIND_STRING
        fields[vol.Required(CONF_MATCH_TEXT)] = selector.TextSelector()
        fields[vol.Required(CONF_COMPARISON, default=COMPARISON_EQUALS)] = _select(
            COMPARISON_OPTIONS, "comparison"
        )
        fields[vol.Required(CONF_MATCH_MODE, default=MATCH_IS_BAD)] = _select(
            MATCH_MODE_OPTIONS, "match_mode"
        )

    return vol.Schema({**fields, **_unavailable_field()})


def _numeric_threshold_schema(current_value: str | None) -> vol.Schema:
    """A single cut-off: a problem below (or above) one threshold."""
    suggested = _as_float(current_value)
    threshold = (
        vol.Required(CONF_THRESHOLD, default=suggested)
        if suggested is not None
        else vol.Required(CONF_THRESHOLD)
    )
    return vol.Schema(
        {
            vol.Required(CONF_DIRECTION, default=DIRECTION_BELOW): _select(
                list(DIRECTION_THRESHOLD_ORDER), "direction"
            ),
            threshold: _number(),
            vol.Optional(CONF_HYSTERESIS, default=0): _number(non_negative=True),
            **_unavailable_field(),
        }
    )


def _numeric_range_schema() -> vol.Schema:
    """A band: a problem outside (or inside) a low/high range."""
    return vol.Schema(
        {
            vol.Required(CONF_DIRECTION, default=DIRECTION_OUTSIDE): _select(
                list(DIRECTION_RANGE_ORDER), "direction"
            ),
            vol.Required(CONF_RANGE_LOW): _number(),
            vol.Required(CONF_RANGE_HIGH): _number(),
            vol.Optional(CONF_HYSTERESIS, default=0): _number(non_negative=True),
            **_unavailable_field(),
        }
    )


def _as_float(raw: str | float | None) -> float | None:
    try:
        return float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _range_error(data: dict[str, Any]) -> dict[str, str]:
    """The one range check the schema can't do: the bounds must differ."""
    low = _as_float(data.get(CONF_RANGE_LOW))
    high = _as_float(data.get(CONF_RANGE_HIGH))
    if low is not None and high is not None and low == high:
        return {CONF_RANGE_LOW: "range_equal"}
    return {}


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
        """Offer the helper types."""
        return self.async_show_menu(
            step_id="user",
            menu_options=[HELPER_MONITORED_ENTITY, KIND_TEMPLATE, HELPER_AGGREGATOR],
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

    @property
    def _me_placeholders(self) -> dict[str, str]:
        state = self.hass.states.get(self._me[CONF_ENTITY_ID])
        return {
            "entity": self._me[CONF_ENTITY_ID],
            "kind": self._me[CONF_KIND],
            "value": state.state if state else "unavailable",
        }

    def _me_entry(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        return self.async_create_entry(
            title=self._me[CONF_NAME], data={**self._me, **user_input}
        )

    async def async_step_configure_check(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask only the questions that matter for the detected kind."""
        kind = self._me[CONF_KIND]
        if kind == KIND_NUMERIC:
            return await self.async_step_numeric_kind()

        if user_input is not None:
            return self._me_entry(user_input)

        return self.async_show_form(
            step_id="configure_check",
            data_schema=_kind_schema(kind),
            description_placeholders=self._me_placeholders,
        )

    async def async_step_numeric_kind(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """A number monitor is a single threshold OR a range — pick one."""
        return self.async_show_menu(
            step_id="numeric_kind",
            menu_options=["numeric_threshold", "numeric_range"],
            description_placeholders=self._me_placeholders,
        )

    async def async_step_numeric_threshold(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self._me_entry(user_input)
        state = self.hass.states.get(self._me[CONF_ENTITY_ID])
        return self.async_show_form(
            step_id="numeric_threshold",
            data_schema=_numeric_threshold_schema(state.state if state else None),
            description_placeholders=self._me_placeholders,
        )

    async def async_step_numeric_range(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _range_error(user_input)
            if not errors:
                return self._me_entry(user_input)
        return self.async_show_form(
            step_id="numeric_range",
            data_schema=self.add_suggested_values_to_schema(
                _numeric_range_schema(), user_input or {}
            ),
            description_placeholders=self._me_placeholders,
            errors=errors,
        )

    # -- template check ------------------------------------------------

    async def async_step_template(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """A monitored entity whose check is a Jinja template."""
        errors: dict[str, str] = {}

        if user_input is not None:
            name = (user_input.get(CONF_NAME) or "").strip()
            if not name:
                errors[CONF_NAME] = "name_required"
            else:
                data = {
                    CONF_HELPER_TYPE: HELPER_MONITORED_ENTITY,
                    CONF_KIND: KIND_TEMPLATE,
                    CONF_NAME: name,
                    CONF_LABELS: user_input.get(CONF_LABELS, []),
                    CONF_VALUE_TEMPLATE: user_input[CONF_VALUE_TEMPLATE],
                    CONF_UNAVAILABLE_IS: user_input[CONF_UNAVAILABLE_IS],
                }
                if reason := user_input.get(CONF_REASON_TEMPLATE):
                    data[CONF_REASON_TEMPLATE] = reason
                return self.async_create_entry(title=name, data=data)

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): selector.TextSelector(),
                vol.Optional(CONF_LABELS, default=[]): selector.LabelSelector(
                    selector.LabelSelectorConfig(multiple=True)
                ),
            }
        ).extend(_kind_schema(KIND_TEMPLATE).schema)
        return self.async_show_form(
            step_id="template",
            data_schema=self.add_suggested_values_to_schema(schema, user_input or {}),
            errors=errors,
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
        return await self.async_step_retune(user_input)

    @property
    def _current(self) -> dict[str, Any]:
        return {**self.config_entry.data, **self.config_entry.options}

    @property
    def _retune_placeholders(self) -> dict[str, str]:
        current = self._current
        watched = current.get(CONF_ENTITY_ID)
        state = self.hass.states.get(watched) if watched else None
        return {
            "entity": watched or "a template",
            "kind": current[CONF_KIND],
            "value": state.state if state else "n/a",
        }

    def _watched_value(self) -> str | None:
        watched = self._current.get(CONF_ENTITY_ID)
        state = self.hass.states.get(watched) if watched else None
        return state.state if state else None

    async def async_step_retune(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        current = self._current
        kind = current[CONF_KIND]

        if kind == KIND_NUMERIC:
            return await self.async_step_retune_numeric_kind()

        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="retune",
            data_schema=self.add_suggested_values_to_schema(
                _kind_schema(kind), current
            ),
            description_placeholders=self._retune_placeholders,
        )

    async def async_step_retune_numeric_kind(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Re-tune a threshold or a range — the current one is marked."""
        is_range = self._current.get(CONF_DIRECTION) in DIRECTION_RANGE
        here = "   ← current"
        return self.async_show_menu(
            step_id="retune_numeric_kind",
            menu_options={
                "retune_threshold": "A threshold — a problem below or above one value"
                + ("" if is_range else here),
                "retune_range": "A range — a problem outside or inside a band"
                + (here if is_range else ""),
            },
            description_placeholders={
                **self._retune_placeholders,
                "current_mode": "a range" if is_range else "a threshold",
            },
        )

    async def async_step_retune_threshold(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="retune_threshold",
            data_schema=self.add_suggested_values_to_schema(
                _numeric_threshold_schema(self._watched_value()), self._current
            ),
            description_placeholders=self._retune_placeholders,
        )

    async def async_step_retune_range(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _range_error(user_input)
            if not errors:
                return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="retune_range",
            data_schema=self.add_suggested_values_to_schema(
                _numeric_range_schema(), user_input or self._current
            ),
            description_placeholders=self._retune_placeholders,
            errors=errors,
        )
