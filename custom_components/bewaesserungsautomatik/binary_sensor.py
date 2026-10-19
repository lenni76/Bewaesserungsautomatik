from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import IrrigationEntity


class RunningSensor(IrrigationEntity, BinarySensorEntity):
    _attr_name = "Bewässerung aktiv"
    _attr_icon = "mdi:water-pump"

    def __init__(self, c):
        super().__init__(c, "running")

    @property
    def is_on(self):
        return self.coordinator.snapshot.running


class ReadySensor(IrrigationEntity, BinarySensorEntity):
    _attr_name = "Automatik bereit"
    _attr_icon = "mdi:check-circle-outline"

    def __init__(self, c):
        super().__init__(c, "ready")

    @property
    def is_on(self):
        c = self.coordinator
        return (
            c.watering_enabled
            and c.settings["automation_enabled"]
            and not c._close_failed
            and c.snapshot.data_quality != "insufficient"
            and not c.is_skipped_today
            and c._minimum_interval_met()
        )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
):
    c = hass.data["bewaesserungsautomatik"][entry.entry_id]
    async_add_entities([RunningSensor(c), ReadySensor(c)])
