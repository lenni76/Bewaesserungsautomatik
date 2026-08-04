from __future__ import annotations
from homeassistant.components.text import TextEntity, TextMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from .entity import IrrigationEntity

class NotificationServiceText(IrrigationEntity, TextEntity):
    _attr_name = "Benachrichtigungsdienst"
    _attr_icon = "mdi:message-cog-outline"
    _attr_mode = TextMode.TEXT
    _attr_native_min = 0
    _attr_native_max = 120

    def __init__(self, coordinator):
        super().__init__(coordinator, "notification_service")

    @property
    def native_value(self) -> str:
        return str(self.coordinator.settings.get("notification_service", ""))

    async def async_set_value(self, value: str) -> None:
        await self.coordinator.async_set_setting("notification_service", value.strip())

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([NotificationServiceText(hass.data["bewaesserungsautomatik"][entry.entry_id])])
