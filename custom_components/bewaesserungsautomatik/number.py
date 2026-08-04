from dataclasses import dataclass
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from .entity import IrrigationEntity
@dataclass(frozen=True,slots=True)
class D: key:str; name:str; min:float; max:float; step:float; unit:str; icon:str
DESCS=[D("base_runtime","Basislaufzeit",1,60,1,"min","mdi:timer-cog-outline"),D("min_runtime","Mindestlaufzeit",1,20,1,"min","mdi:timer-minus-outline"),D("max_runtime","Maximale automatische Laufzeit",5,50,1,"min","mdi:timer-alert-outline"),D("manual_runtime","Manuelle Laufzeit",15,720,15,"min","mdi:faucet"),D("safety_runtime","Sicherheitszeit",15,720,15,"min","mdi:shield-clock-outline"),D("rain_effect","Regenwirkung",0,100,5,"%","mdi:weather-rainy"),D("past_temperature_weight","Gewichtung Vergangenheit",0,100,5,"%","mdi:thermometer-lines"),D("cycle_threshold","Zyklus ab Laufzeit",10,50,1,"min","mdi:call-split"),D("cycle_pause","Versickerungspause",0,60,5,"min","mdi:timer-pause-outline"),D("minimum_interval","Mindestabstand",12,96,6,"h","mdi:clock-outline")]
class SettingNumber(IrrigationEntity,NumberEntity):
    _attr_mode=NumberMode.BOX
    def __init__(self,c,d): super().__init__(c,d.key); self.d=d; self._attr_name=d.name; self._attr_native_min_value=d.min; self._attr_native_max_value=d.max; self._attr_native_step=d.step; self._attr_native_unit_of_measurement=d.unit; self._attr_icon=d.icon
    @property
    def native_value(self): return float(self.coordinator.settings[self.d.key])
    async def async_set_native_value(self,value): await self.coordinator.async_set_setting(self.d.key,float(value))
async def async_setup_entry(hass:HomeAssistant,entry:ConfigEntry,async_add_entities:AddConfigEntryEntitiesCallback):
    c=hass.data["bewaesserungsautomatik"][entry.entry_id]; async_add_entities([SettingNumber(c,d) for d in DESCS])
