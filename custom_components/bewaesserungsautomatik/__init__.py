from __future__ import annotations
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN,PLATFORMS
from .coordinator import IrrigationCoordinator
async def async_setup_entry(hass:HomeAssistant,entry:ConfigEntry)->bool:
    coordinator=IrrigationCoordinator(hass,entry)
    await coordinator.async_initialize()
    hass.data.setdefault(DOMAIN,{})[entry.entry_id]=coordinator
    await hass.config_entries.async_forward_entry_setups(entry,PLATFORMS)
    return True
async def async_unload_entry(hass:HomeAssistant,entry:ConfigEntry)->bool:
    unload=await hass.config_entries.async_unload_platforms(entry,PLATFORMS)
    if unload:
        coordinator=hass.data[DOMAIN].pop(entry.entry_id); await coordinator.async_shutdown()
    return unload
