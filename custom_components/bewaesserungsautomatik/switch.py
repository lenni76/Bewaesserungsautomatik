from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import IrrigationEntity


class SettingSwitch(IrrigationEntity, SwitchEntity):
    def __init__(self, c, key, name, icon):
        super().__init__(c, key)
        self.setting = key
        self._attr_name = name
        self._attr_icon = icon

    @property
    def is_on(self):
        return bool(self.coordinator.settings[self.setting])

    async def async_turn_on(self, **kwargs):
        await self.coordinator.async_set_setting(self.setting, True)

    async def async_turn_off(self, **kwargs):
        await self.coordinator.async_set_setting(self.setting, False)


class SkipSwitch(IrrigationEntity, SwitchEntity):
    _attr_name = "Heute aussetzen"
    _attr_icon = "mdi:calendar-remove"

    def __init__(self, c):
        super().__init__(c, "skip_today")

    @property
    def is_on(self):
        return self.coordinator.is_skipped_today

    async def async_turn_on(self, **kwargs):
        await self.coordinator.async_set_skip_today(True)

    async def async_turn_off(self, **kwargs):
        await self.coordinator.async_set_skip_today(False)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
):
    c = hass.data["bewaesserungsautomatik"][entry.entry_id]
    async_add_entities(
        [
            SettingSwitch(c, "watering_enabled", "Bewässerung freigeben", "mdi:water-check"),
            SettingSwitch(c, "automation_enabled", "Automatik", "mdi:robot"),
            SettingSwitch(c, "safety_enabled", "Sicherheitsabschaltung", "mdi:shield-check"),
            SettingSwitch(c, "expert_mode", "Expertenmodus", "mdi:tune-variant"),
            SettingSwitch(c, "notifications_enabled", "Benachrichtigungen", "mdi:message-badge-outline"),
            SkipSwitch(c),
        ]
    )
