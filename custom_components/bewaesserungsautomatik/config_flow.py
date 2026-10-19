from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.weather import WeatherEntityFeature
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector

from .const import (
    CONF_EXPOSURE,
    CONF_HISTORY_GENERATION,
    CONF_PRECIPITATION,
    CONF_PROFILE,
    CONF_RUNTIME,
    CONF_TEMPERATURE,
    CONF_VALVE,
    CONF_WEATHER,
    DEFAULT_EXPOSURE,
    DEFAULT_PROFILE,
    DOMAIN,
)
from .weather_data import async_forecast, finite_number, sensor_rain, sensor_temperature

RESET_HISTORY = "reset_weather_history"
ENTITY_FIELDS = {
    CONF_TEMPERATURE: ("sensor", "sensor.icolog277_temperature"),
    CONF_PRECIPITATION: ("sensor", "sensor.icolog277_precipitation_today"),
    CONF_WEATHER: ("weather", "weather.koln_bonn"),
    CONF_VALVE: ("valve", "valve.garten_wasseranschluss"),
    CONF_RUNTIME: ("number", "number.wasseranschluss_laufzeit"),
}


def _schema(values: dict[str, Any], *, reconfigure: bool = False) -> vol.Schema:
    fields = {
        vol.Required(key, default=values.get(key, default)): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=domain)
        )
        for key, (domain, default) in ENTITY_FIELDS.items()
    }
    fields[vol.Required(CONF_PROFILE, default=values.get(CONF_PROFILE, DEFAULT_PROFILE))] = selector.SelectSelector(
        selector.SelectSelectorConfig(options=[{"value": "flower_bed", "label": "Blumenbeet"}])
    )
    fields[vol.Required(CONF_EXPOSURE, default=values.get(CONF_EXPOSURE, DEFAULT_EXPOSURE))] = selector.SelectSelector(
        selector.SelectSelectorConfig(options=[{"value": "sunny", "label": "Sonnig"}])
    )
    if reconfigure:
        fields[vol.Optional(RESET_HISTORY, default=values.get(RESET_HISTORY, False))] = selector.BooleanSelector()
    return vol.Schema(fields)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _validate(self, values: dict[str, Any], previous=None) -> dict[str, str]:
        errors = {}
        for key, (domain, _default) in ENTITY_FIELDS.items():
            entity_id = values.get(key, "")
            if not isinstance(entity_id, str) or not entity_id.startswith(f"{domain}."):
                errors[key] = "invalid_entity"
                continue
            state = self.hass.states.get(entity_id)
            # Existing actuators may intentionally be offline during winter.
            if key in (CONF_VALVE, CONF_RUNTIME) and previous and previous.get(key) == entity_id:
                continue
            if state is None or state.state in ("unknown", "unavailable"):
                errors[key] = "entity_unavailable"
        if CONF_TEMPERATURE not in errors and sensor_temperature(self.hass, values[CONF_TEMPERATURE]) is None:
            errors[CONF_TEMPERATURE] = "invalid_temperature"
        if CONF_PRECIPITATION not in errors and sensor_rain(self.hass, values[CONF_PRECIPITATION]) is None:
            errors[CONF_PRECIPITATION] = "invalid_rain"
        if CONF_RUNTIME not in errors and (not previous or previous.get(CONF_RUNTIME) != values[CONF_RUNTIME]):
            state = self.hass.states.get(values[CONF_RUNTIME])
            if state and finite_number(state.state) is None:
                errors[CONF_RUNTIME] = "invalid_number"
        if CONF_WEATHER not in errors:
            state = self.hass.states.get(values[CONF_WEATHER])
            features = state.attributes.get("supported_features", 0)
            if not isinstance(features, int) or not features & WeatherEntityFeature.FORECAST_HOURLY:
                errors[CONF_WEATHER] = "hourly_forecast_required"
            else:
                try:
                    _rain, _temp, valid = await async_forecast(self.hass, values[CONF_WEATHER])
                except Exception:
                    valid = False
                if not valid:
                    errors[CONF_WEATHER] = "invalid_forecast"
        return errors

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        errors = {}
        if user_input is not None:
            errors = await self._validate(user_input)
            if not errors:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Bewässerungsautomatik", data=user_input)
        return self.async_show_form(step_id="user", data_schema=_schema(user_input or {}), errors=errors)

    async def async_step_reconfigure(self, user_input=None):
        entry = self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            errors = await self._validate(user_input, entry.data)
            if not errors:
                updates = {key: value for key, value in user_input.items() if key != RESET_HISTORY}
                if user_input.get(RESET_HISTORY):
                    updates[CONF_HISTORY_GENERATION] = int(entry.data.get(CONF_HISTORY_GENERATION, 0)) + 1
                changed = any(entry.data.get(key) != value for key, value in updates.items())
                c = self.hass.data.get(DOMAIN, {}).get(entry.entry_id)
                if changed and c is not None:
                    try:
                        await c.async_prepare_reconfigure()
                    except (HomeAssistantError, OSError):
                        errors["base"] = "cannot_stop"
                if not errors:
                    return self.async_update_reload_and_abort(
                        entry, data_updates=updates, reload_even_if_entry_is_unchanged=False
                    )
        values = dict(entry.data) | (user_input or {})
        return self.async_show_form(step_id="reconfigure", data_schema=_schema(values, reconfigure=True), errors=errors)
