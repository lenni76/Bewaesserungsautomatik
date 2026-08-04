from __future__ import annotations
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from .const import DOMAIN
async def async_get_config_entry_diagnostics(hass:HomeAssistant,entry:ConfigEntry):
    c=hass.data[DOMAIN][entry.entry_id]
    return {"config":dict(entry.data),"settings":dict(c.settings),"snapshot":c.snapshot.as_dict(),"daily_history":c.daily,"irrigation_log":c.logbook}
