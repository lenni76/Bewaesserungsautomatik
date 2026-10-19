"""Validate and normalize weather inputs without controlling any devices."""

import asyncio
import math
from datetime import timedelta

from homeassistant.const import UnitOfLength, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import DistanceConverter, TemperatureConverter


def finite_number(value) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def temperature_c(value, unit: str | None) -> float | None:
    number = finite_number(value)
    if number is None or unit not in TemperatureConverter.VALID_UNITS:
        return None
    return TemperatureConverter.convert(number, unit, UnitOfTemperature.CELSIUS)


def rain_mm(value, unit: str | None) -> float | None:
    number = finite_number(value)
    if number is None or number < 0 or unit not in ("mm", "cm", "m", "in"):
        return None
    return DistanceConverter.convert(number, unit, UnitOfLength.MILLIMETERS)


def sensor_temperature(hass: HomeAssistant, entity_id: str) -> float | None:
    state = hass.states.get(entity_id)
    return temperature_c(state.state, state.attributes.get("unit_of_measurement")) if state else None


def sensor_rain(hass: HomeAssistant, entity_id: str) -> float | None:
    state = hass.states.get(entity_id)
    return rain_mm(state.state, state.attributes.get("unit_of_measurement")) if state else None


async def async_forecast(hass: HomeAssistant, entity_id: str) -> tuple[float | None, float | None, bool]:
    state = hass.states.get(entity_id)
    if state is None or state.state in ("unknown", "unavailable"):
        return None, None, False
    try:
        async with asyncio.timeout(15):
            response = await hass.services.async_call(
                "weather",
                "get_forecasts",
                {"type": "hourly", "entity_id": entity_id},
                blocking=True,
                return_response=True,
            )
    except (HomeAssistantError, TimeoutError):
        return None, None, False
    block = response.get(entity_id) if isinstance(response, dict) else None
    forecasts = block.get("forecast") if isinstance(block, dict) else None
    if not isinstance(forecasts, list):
        return None, None, False
    now = dt_util.now()
    end = now + timedelta(hours=12)
    temperatures = []
    rains = []
    missing_rain = False
    for item in forecasts:
        if not isinstance(item, dict) or not isinstance(item.get("datetime"), str):
            continue
        try:
            when = dt_util.parse_datetime(item["datetime"])
        except (TypeError, ValueError, OverflowError):
            continue
        if when is None or when.tzinfo is None or not now <= when <= end:
            continue
        temp = temperature_c(item.get("temperature"), state.attributes.get("temperature_unit"))
        rain = rain_mm(item.get("precipitation"), state.attributes.get("precipitation_unit"))
        if temp is not None:
            temperatures.append(temp)
        if rain is None:
            missing_rain = True
        else:
            rains.append(rain)
    rain_total = round(sum(rains), 2) if rains and not missing_rain else None
    maximum = max(temperatures) if temperatures else None
    return rain_total, maximum, rain_total is not None and maximum is not None
