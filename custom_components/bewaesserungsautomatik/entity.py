from __future__ import annotations
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from .const import DOMAIN
from .coordinator import IrrigationCoordinator
class IrrigationEntity(Entity):
    _attr_has_entity_name = True
    def __init__(self, coordinator: IrrigationCoordinator, key: str) -> None:
        self.coordinator, self._key = coordinator, key
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, coordinator.entry.entry_id)}, name="Bewässerungsautomatik", manufacturer="lenni76", model="Wetterabhängige Bewässerung", sw_version="1.0.1")
    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.coordinator.subscribe(self.async_write_ha_state))
