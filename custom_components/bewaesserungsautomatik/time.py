from __future__ import annotations
from datetime import time
from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from .entity import IrrigationEntity

class StartTimeEntity(IrrigationEntity, TimeEntity):
    _attr_name = "Startzeit"
    _attr_icon = "mdi:clock-start"

    def __init__(self, coordinator):
        super().__init__(coordinator, "start_time")

    @property
    def native_value(self) -> time:
        return time.fromisoformat(str(self.coordinator.settings["start_time"]))

    async def async_set_value(self, value: time) -> None:
        await self.coordinator.async_set_start_time(value)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([StartTimeEntity(hass.data["bewaesserungsautomatik"][entry.entry_id])])
