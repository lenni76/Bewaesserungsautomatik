from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.const import UnitOfTemperature, UnitOfTime, UnitOfPrecipitationDepth, PERCENTAGE
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from .entity import IrrigationEntity
@dataclass(frozen=True, slots=True)
class Desc:
    key:str; name:str; icon:str; value:Callable; unit:str|None=None; device_class:SensorDeviceClass|None=None
DESCS=[
 Desc("status","Status","mdi:sprinkler-variant",lambda c:c.snapshot.status),
 Desc("decision","Entscheidung","mdi:comment-text-outline",lambda c:c.snapshot.reason),
 Desc("quality","Datenqualität","mdi:check-decagram-outline",lambda c:c.snapshot.data_quality),
 Desc("need","Bewässerungsbedarf","mdi:water-percent",lambda c:c.snapshot.need_percent,PERCENTAGE),
 Desc("runtime","Empfohlene Laufzeit","mdi:timer-outline",lambda c:c.snapshot.runtime_minutes,UnitOfTime.MINUTES),
 Desc("remaining","Verbleibende Laufzeit","mdi:timer-sand",lambda c:c.snapshot.remaining_minutes,UnitOfTime.MINUTES),
 Desc("effective_rain","Wirksamer Niederschlag","mdi:weather-rainy",lambda c:c.snapshot.effective_rain_mm,UnitOfPrecipitationDepth.MILLIMETERS),
 Desc("forecast_rain","Regen nächste 12 Stunden","mdi:weather-pouring",lambda c:c.snapshot.forecast_rain_12h_mm,UnitOfPrecipitationDepth.MILLIMETERS),
 Desc("temperature","Berechnungstemperatur","mdi:thermometer",lambda c:c.snapshot.calculation_temperature_c,UnitOfTemperature.CELSIUS,SensorDeviceClass.TEMPERATURE),
 Desc("past_max","Höchsttemperatur gestern","mdi:thermometer-high",lambda c:c.snapshot.measured_max_yesterday_c,UnitOfTemperature.CELSIUS,SensorDeviceClass.TEMPERATURE),
 Desc("forecast_max","Erwartete Höchsttemperatur","mdi:thermometer-chevron-up",lambda c:c.snapshot.forecast_max_today_c,UnitOfTemperature.CELSIUS,SensorDeviceClass.TEMPERATURE),
 Desc("dry_days","Trockene Tage","mdi:weather-sunny-alert",lambda c:c.snapshot.dry_days,"d"),
 Desc("last_run","Letzte Bewässerung","mdi:history",lambda c:c.snapshot.last_run),
 Desc("next_possible","Nächste mögliche Bewässerung","mdi:calendar-clock",lambda c:c.snapshot.next_possible),
 Desc("next_action","Nächste Aktion","mdi:calendar-arrow-right",lambda c:c.snapshot.next_action),
 Desc("prepared_at","Letzte Vorberechnung","mdi:calculator-variant-outline",lambda c:c.snapshot.prepared_at),
 Desc("planned_start","Geplanter Start","mdi:clock-start",lambda c:c.snapshot.planned_start),
]
class IrrigationSensor(IrrigationEntity,SensorEntity):
    def __init__(self,c,d): super().__init__(c,d.key); self.d=d; self._attr_name=d.name; self._attr_icon=d.icon; self._attr_native_unit_of_measurement=d.unit; self._attr_device_class=d.device_class
    @property
    def native_value(self): return self.d.value(self.coordinator)
    @property
    def extra_state_attributes(self):
        if self.d.key=="decision": return {"profile":"Blumenbeet","exposure":"Sonnig","logbook":self.coordinator.logbook[-10:]}
        return None
async def async_setup_entry(hass:HomeAssistant,entry:ConfigEntry,async_add_entities:AddConfigEntryEntitiesCallback):
    async_add_entities([IrrigationSensor(hass.data["bewaesserungsautomatik"][entry.entry_id],d) for d in DESCS])
