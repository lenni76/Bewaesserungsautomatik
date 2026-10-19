"""Calendar, weather and persistence checks beyond the new winter switch."""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from homeassistant.core import SupportsResponse
from homeassistant.util import dt as dt_util

from custom_components.bewaesserungsautomatik.coordinator import IrrigationCoordinator


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "year,month,expected",
    [
        (2026, 11, 0),
        (2026, 12, 0),
        (2027, 1, 0),
        (2027, 2, 0),
        (2027, 3, 0),
        (2027, 4, 12),
        (2027, 5, 16),
        (2027, 6, 20),
        (2027, 7, 20),
        (2027, 8, 20),
        (2027, 9, 15),
        (2027, 10, 10),
    ],
)
async def test_next_twelve_months_retain_existing_seasonal_recommendations(rig, year, month, expected):
    # Fixed 25 °C, dry new installation, default settings: recognizable reference scenario.
    now = datetime(year, month, 15, 5, 0, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    with patch.object(dt_util, "now", return_value=now):
        await rig.c.async_refresh()
    assert rig.c.snapshot.runtime_minutes == expected


@pytest.mark.asyncio
async def test_heavy_rain_forecast_prevents_watering(rig):
    async def rain_forecast(call):
        return {
            rig.config["weather_entity"]: {
                "forecast": [
                    {
                        "datetime": (dt_util.now() + timedelta(hours=1)).isoformat(),
                        "temperature": 30.0,
                        "precipitation": 9.0,
                    }
                ]
            }
        }

    rig.hass.services.async_register("weather", "get_forecasts", rain_forecast, supports_response=SupportsResponse.ONLY)
    await rig.c.async_refresh()
    assert rig.c.snapshot.runtime_minutes == 0
    await rig.c.async_start_automatic()
    assert not any(call[:2] == ("valve", "open_valve") for call in rig.calls)


@pytest.mark.asyncio
async def test_known_issue_last_run_survives_restart(rig):
    completed = dt_util.now().isoformat()
    rig.c.snapshot.last_run = completed
    await rig.c._save()
    saved = rig.c.store.async_save.call_args.args[0]
    restored = IrrigationCoordinator(rig.hass, rig.c.entry)
    restored.store.async_load = rig.c.store.async_load
    restored.store.async_load.return_value = saved
    restored.store.async_save = rig.c.store.async_save
    try:
        await restored.async_initialize()
        assert restored.snapshot.last_run == completed
        assert not restored._minimum_interval_met()
    finally:
        await restored.async_shutdown()


@pytest.mark.asyncio
async def test_known_issue_stale_forecast_is_not_reported_as_valid(rig):
    async def stale(call):
        return {
            rig.config["weather_entity"]: {
                "forecast": [
                    {
                        "datetime": (dt_util.now() - timedelta(days=1)).isoformat(),
                        "temperature": 30.0,
                        "precipitation": 9.0,
                    }
                ]
            }
        }

    rig.hass.services.async_register("weather", "get_forecasts", stale, supports_response=SupportsResponse.ONLY)
    _rain, _temperature, valid = await rig.c._weather_forecast()
    assert valid is False
