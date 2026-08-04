from __future__ import annotations
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
from .const import *
class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION=1
    async def async_step_user(self,user_input=None):
        if self._async_current_entries(): return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN); self._abort_if_unique_id_configured()
            return self.async_create_entry(title="Bewässerungsautomatik",data=user_input)
        schema=vol.Schema({
            vol.Required(CONF_TEMPERATURE,default="sensor.icolog277_temperature"):selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Required(CONF_PRECIPITATION,default="sensor.icolog277_precipitation_today"):selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Required(CONF_WEATHER,default="weather.koln_bonn"):selector.EntitySelector(selector.EntitySelectorConfig(domain="weather")),
            vol.Required(CONF_VALVE,default="valve.garten_wasseranschluss"):selector.EntitySelector(selector.EntitySelectorConfig(domain="valve")),
            vol.Required(CONF_RUNTIME,default="number.wasseranschluss_laufzeit"):selector.EntitySelector(selector.EntitySelectorConfig(domain="number")),
            vol.Required(CONF_PROFILE,default=DEFAULT_PROFILE):selector.SelectSelector(selector.SelectSelectorConfig(options=[{"value":"flower_bed","label":"Blumenbeet"}],mode=selector.SelectSelectorMode.DROPDOWN)),
            vol.Required(CONF_EXPOSURE,default=DEFAULT_EXPOSURE):selector.SelectSelector(selector.SelectSelectorConfig(options=[{"value":"sunny","label":"Sonnig"}],mode=selector.SelectSelectorMode.DROPDOWN)),
        })
        return self.async_show_form(step_id="user",data_schema=schema)
