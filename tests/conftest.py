"""Real HA service/state fixture with simulated weather and valve hardware."""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest_asyncio
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.util import dt as dt_util

from custom_components.bewaesserungsautomatik.const import (
    CONF_PRECIPITATION,
    CONF_RUNTIME,
    CONF_TEMPERATURE,
    CONF_VALVE,
    CONF_WEATHER,
)
from custom_components.bewaesserungsautomatik.coordinator import IrrigationCoordinator


@pytest_asyncio.fixture
async def rig(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    await hass.config.async_set_time_zone("Europe/Berlin")
    config = {
        CONF_TEMPERATURE: "sensor.test_temperature",
        CONF_PRECIPITATION: "sensor.test_rain",
        CONF_WEATHER: "weather.test",
        CONF_RUNTIME: "number.test_runtime",
        CONF_VALVE: "valve.test",
    }
    entry = SimpleNamespace(data=config, entry_id="winter_test")
    c = IrrigationCoordinator(hass, entry)
    # The coordinator's actual storage contract is tested separately.
    c.store.async_load = AsyncMock(return_value=None)
    c.store.async_save = AsyncMock()
    calls = []

    async def service(call):
        calls.append((call.domain, call.service, dict(call.data)))
        if call.service == "open_valve":
            hass.states.async_set(config[CONF_VALVE], "open")
        elif call.service == "close_valve":
            hass.states.async_set(config[CONF_VALVE], "closed")

    async def forecast(call):
        return {
            config[CONF_WEATHER]: {
                "forecast": [
                    {
                        "datetime": (dt_util.now() + timedelta(hours=1)).isoformat(),
                        "precipitation": 0.0,
                        "temperature": 25.0,
                    }
                ]
            }
        }

    hass.services.async_register("valve", "open_valve", service)
    hass.services.async_register("valve", "close_valve", service)
    hass.services.async_register("number", "set_value", service)
    hass.services.async_register("weather", "get_forecasts", forecast, supports_response=SupportsResponse.ONLY)
    hass.states.async_set(config[CONF_TEMPERATURE], "25", {"unit_of_measurement": "°C"})
    hass.states.async_set(config[CONF_PRECIPITATION], "0", {"unit_of_measurement": "mm"})
    hass.states.async_set(
        config[CONF_WEATHER], "sunny", {"supported_features": 2, "temperature_unit": "°C", "precipitation_unit": "mm"}
    )
    hass.states.async_set(config[CONF_RUNTIME], "25", {"unit_of_measurement": "min"})
    hass.states.async_set(config[CONF_VALVE], "closed")
    c.snapshot.data_quality = "complete"
    c.snapshot.runtime_minutes = 10
    yield SimpleNamespace(hass=hass, c=c, config=config, calls=calls)
    await c.async_shutdown()
    await hass.async_stop(force=True)
