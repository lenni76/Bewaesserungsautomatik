from __future__ import annotations
from typing import Final
DOMAIN: Final = "bewaesserungsautomatik"
PLATFORMS: Final = ["sensor", "binary_sensor", "switch", "number", "button"]
CONF_TEMPERATURE = "temperature_entity"
CONF_PRECIPITATION = "precipitation_entity"
CONF_WEATHER = "weather_entity"
CONF_VALVE = "valve_entity"
CONF_RUNTIME = "runtime_entity"
CONF_PROFILE = "plant_profile"
CONF_EXPOSURE = "exposure"
DEFAULT_PROFILE = "flower_bed"
DEFAULT_EXPOSURE = "sunny"
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.{{entry_id}}"
DEFAULTS = {
    "automation_enabled": True, "safety_enabled": True, "expert_mode": False,
    "base_runtime": 25.0, "min_runtime": 2.0, "max_runtime": 50.0,
    "manual_runtime": 240.0, "safety_runtime": 240.0,
    "rain_effect": 70.0, "past_temperature_weight": 60.0,
    "cycle_threshold": 35.0, "cycle_pause": 20.0,
    "start_hour": 5.0, "minimum_interval": 36.0,
}
