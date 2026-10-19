from __future__ import annotations

from typing import Final

DOMAIN: Final = "bewaesserungsautomatik"
PLATFORMS: Final = ["sensor", "binary_sensor", "switch", "number", "button", "time", "text"]

CONF_TEMPERATURE = "temperature_entity"
CONF_PRECIPITATION = "precipitation_entity"
CONF_WEATHER = "weather_entity"
CONF_VALVE = "valve_entity"
CONF_RUNTIME = "runtime_entity"
CONF_PROFILE = "plant_profile"
CONF_EXPOSURE = "exposure"
CONF_HISTORY_GENERATION = "weather_history_generation"
DEFAULT_PROFILE = "flower_bed"
DEFAULT_EXPOSURE = "sunny"
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.{{entry_id}}"

DEFAULTS = {
    "watering_enabled": True,
    "automation_enabled": True,
    "safety_enabled": True,
    "expert_mode": False,
    "notifications_enabled": False,
    "notification_service": "",
    "base_runtime": 25.0,
    "min_runtime": 2.0,
    "max_runtime": 50.0,
    "manual_runtime": 240.0,
    "safety_runtime": 240.0,
    "rain_effect": 70.0,
    "past_temperature_weight": 60.0,
    "cycle_threshold": 35.0,
    "cycle_pause": 20.0,
    "start_time": "05:00:00",
    "minimum_interval": 36.0,
}
