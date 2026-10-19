"""Weather unit conversion, malformed forecasts and unknown rainfall."""

from datetime import timedelta

import pytest
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from custom_components.bewaesserungsautomatik.weather_data import finite_number, rain_mm, temperature_c


@pytest.mark.parametrize("value,unit,celsius", [(25, "°C", 25), (77, "°F", 25), (298.15, "K", 25)])
def test_temperature_units(value, unit, celsius):
    assert temperature_c(value, unit) == pytest.approx(celsius)


@pytest.mark.parametrize("value,unit,mm", [(1, "in", 25.4), (2, "cm", 20), (5, "mm", 5)])
def test_rain_units(value, unit, mm):
    assert rain_mm(value, unit) == pytest.approx(mm)


@pytest.mark.parametrize("value", ["nan", "inf", "-inf", True, None, "unknown", "unavailable"])
def test_nonfinite_values_are_unknown(value):
    assert finite_number(value) is None


@pytest.mark.asyncio
async def test_imperial_station_and_forecast_convert_to_metric(rig):
    c = rig.c
    rig.hass.states.async_set(rig.config["temperature_entity"], "77", {"unit_of_measurement": "°F"})
    rig.hass.states.async_set(rig.config["precipitation_entity"], "0.1", {"unit_of_measurement": "in"})
    rig.hass.states.async_set(
        rig.config["weather_entity"],
        "sunny",
        {"supported_features": 2, "temperature_unit": "°F", "precipitation_unit": "in"},
    )

    async def forecast(call):
        return {
            rig.config["weather_entity"]: {
                "forecast": [
                    {
                        "datetime": (dt_util.now() + timedelta(hours=1)).isoformat(),
                        "temperature": 77,
                        "precipitation": 0.1,
                    }
                ]
            }
        }

    rig.hass.services.async_register("weather", "get_forecasts", forecast, supports_response=SupportsResponse.ONLY)
    await c.async_refresh()
    assert c.snapshot.calculation_temperature_c == 25
    assert c.snapshot.forecast_rain_12h_mm == 2.54
    assert c.snapshot.effective_rain_mm == 1.78  # 2.54 mm × default 70 %.


@pytest.mark.asyncio
async def test_missing_rain_sensor_blocks_automatic_watering_and_is_not_archived_as_dry(rig):
    rig.hass.states.async_set(rig.config["precipitation_entity"], "unavailable", {"unit_of_measurement": "mm"})
    await rig.c.async_refresh()
    assert rig.c.snapshot.data_quality == "insufficient"
    assert rig.c.snapshot.runtime_minutes == 0
    assert rig.c.snapshot.effective_rain_mm is None
    await rig.c.async_start_automatic()
    assert not any(call[:2] == ("valve", "open_valve") for call in rig.calls)
    await rig.c._archive_day(dt_util.now())
    assert rig.c.daily[-1]["rain"] is None


@pytest.mark.asyncio
async def test_forecast_failure_keeps_documented_measurement_fallback(rig):
    async def fail(call):
        raise HomeAssistantError("forecast service offline")

    rig.hass.services.async_register("weather", "get_forecasts", fail, supports_response=SupportsResponse.ONLY)
    await rig.c.async_refresh()
    assert rig.c.snapshot.data_quality == "fallback"
    assert rig.c.snapshot.forecast_rain_12h_mm is None
    assert rig.c.snapshot.calculation_temperature_c == 25


@pytest.mark.asyncio
async def test_malformed_and_naive_forecast_datetimes_do_not_crash(rig):
    async def forecast(call):
        return {
            rig.config["weather_entity"]: {
                "forecast": [
                    None,
                    {},
                    {"datetime": 5},
                    {"datetime": "bad"},
                    {"datetime": dt_util.now().replace(tzinfo=None).isoformat(), "temperature": 25, "precipitation": 0},
                ]
            }
        }

    rig.hass.services.async_register("weather", "get_forecasts", forecast, supports_response=SupportsResponse.ONLY)
    rain, temp, valid = await rig.c._weather_forecast()
    assert (rain, temp, valid) == (None, None, False)


@pytest.mark.asyncio
async def test_missing_forecast_precipitation_is_unknown_not_zero(rig):
    async def forecast(call):
        return {
            rig.config["weather_entity"]: {
                "forecast": [{"datetime": (dt_util.now() + timedelta(hours=1)).isoformat(), "temperature": 25}]
            }
        }

    rig.hass.services.async_register("weather", "get_forecasts", forecast, supports_response=SupportsResponse.ONLY)
    rain, temp, valid = await rig.c._weather_forecast()
    assert rain is None
    assert temp == 25
    assert valid is False
