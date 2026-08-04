from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from .entity import IrrigationEntity
class ActionButton(IrrigationEntity,ButtonEntity):
    def __init__(self,c,key,name,icon,action): super().__init__(c,key); self._attr_name=name; self._attr_icon=icon; self.action=action
    async def async_press(self): await self.action()
async def async_setup_entry(hass:HomeAssistant,entry:ConfigEntry,async_add_entities:AddConfigEntryEntitiesCallback):
    c=hass.data["bewaesserungsautomatik"][entry.entry_id]
    async_add_entities([ActionButton(c,"start_auto","Automatisch jetzt bewässern","mdi:play-circle-outline",c.async_start_automatic),ActionButton(c,"start_manual","Wasser manuell öffnen","mdi:faucet",c.async_start_manual),ActionButton(c,"stop","Sofort stoppen","mdi:stop-circle-outline",c.async_stop),ActionButton(c,"refresh","Berechnung aktualisieren","mdi:refresh",c.async_refresh)])
