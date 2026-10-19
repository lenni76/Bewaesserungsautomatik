"""Winter lock tests using real HA services/events; no physical devices."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from custom_components.bewaesserungsautomatik.binary_sensor import ReadySensor
from custom_components.bewaesserungsautomatik.const import CONF_VALVE, DEFAULTS
from custom_components.bewaesserungsautomatik.coordinator import IrrigationCoordinator
from custom_components.bewaesserungsautomatik.switch import SettingSwitch


def opened(rig):
    return [call for call in rig.calls if call[:2] == ("valve", "open_valve")]


@pytest.mark.asyncio
async def test_existing_installation_defaults_to_enabled(rig):
    await rig.c.async_initialize()
    assert rig.c.watering_enabled
    assert not opened(rig)


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["async_start_automatic", "async_start_manual"])
async def test_disabled_blocks_buttons_with_visible_error(rig, method):
    await rig.c.async_set_watering_enabled(False)
    with pytest.raises(HomeAssistantError, match="Bewässerung gesperrt"):
        await getattr(rig.c, method)()
    assert not opened(rig)
    assert not rig.c.snapshot.running
    assert rig.c.snapshot.status == "watering_disabled"


@pytest.mark.asyncio
async def test_scheduled_start_recalculates_without_opening(rig):
    await rig.c.async_set_watering_enabled(False)
    with patch.object(rig.c, "async_refresh", wraps=rig.c.async_refresh) as refresh:
        await rig.c._scheduled_start(dt_util.now())
    refresh.assert_awaited_once()
    assert not opened(rig)


@pytest.mark.asyncio
@pytest.mark.parametrize("manual", [False, True])
async def test_switching_off_stops_running_operation_even_without_safety(rig, manual):
    c = rig.c
    c.settings["safety_enabled"] = False
    await c._start(manual, 10)
    task = c._run_task
    await asyncio.sleep(0)
    await c.async_set_watering_enabled(False)
    assert task.cancelled()
    assert c._run_task is None
    assert not c.snapshot.running
    assert c.snapshot.remaining_minutes == 0
    assert rig.hass.states.get(rig.config[CONF_VALVE]).state == "closed"
    assert c.store.async_save.call_args.args[0]["settings"]["watering_enabled"] is False


@pytest.mark.asyncio
async def test_switching_off_during_soak_pause_prevents_reopening(rig):
    c = rig.c
    pause_reached = asyncio.Event()

    async def countdown(_minutes):
        pause_reached.set()

    c._countdown = countdown
    await c._start(False, 40)
    await pause_reached.wait()
    # Let the task finish its first close and enter the soak sleep.
    for _ in range(20):
        if c.snapshot.status == "soak_pause":
            break
        await asyncio.sleep(0)
    assert c.snapshot.status == "soak_pause"
    await c.async_set_watering_enabled(False)
    assert len(opened(rig)) == 1
    assert c._run_task is None
    assert not await c._open()


@pytest.mark.asyncio
async def test_disable_during_runtime_service_does_not_open(rig):
    entered = asyncio.Event()
    release = asyncio.Event()

    async def slow_runtime(minutes):
        entered.set()
        await release.wait()

    rig.c._set_runtime = slow_runtime
    start = asyncio.create_task(rig.c.async_start_manual())
    await entered.wait()
    disable = asyncio.create_task(rig.c.async_set_watering_enabled(False))
    await asyncio.sleep(0)
    assert not rig.c.watering_enabled
    release.set()
    await asyncio.gather(start, disable)
    assert not opened(rig)
    assert not rig.c.snapshot.running


@pytest.mark.asyncio
async def test_disable_waits_for_inflight_open_then_closes(rig):
    entered = asyncio.Event()
    release = asyncio.Event()

    async def slow_open(call):
        rig.calls.append((call.domain, call.service, dict(call.data)))
        entered.set()
        await release.wait()
        rig.hass.states.async_set(rig.config[CONF_VALVE], "open")

    rig.hass.services.async_register("valve", "open_valve", slow_open)
    start = asyncio.create_task(rig.c.async_start_manual())
    await entered.wait()
    disable = asyncio.create_task(rig.c.async_set_watering_enabled(False))
    await asyncio.sleep(0)
    release.set()
    await asyncio.gather(start, disable)
    assert rig.hass.states.get(rig.config[CONF_VALVE]).state == "closed"
    assert not rig.c.snapshot.running
    assert rig.c._run_task is None


@pytest.mark.asyncio
async def test_calculations_and_archive_continue_while_disabled(rig):
    c = rig.c
    await c.async_set_watering_enabled(False)
    await c.async_refresh()
    assert c.snapshot.calculation_temperature_c == 25.0
    assert c.snapshot.runtime_minutes > 0
    await c._archive_day(dt_util.now())
    assert len(c.daily) == 1
    await c._scheduled_prepare(dt_util.now())
    assert c.snapshot.prepared_at is not None
    assert c.snapshot.status == "watering_disabled"
    assert "Winterpause" in c.snapshot.next_action
    assert not opened(rig)


@pytest.mark.asyncio
async def test_reenable_does_not_start_or_change_automation_setting(rig):
    await rig.c.async_set_watering_enabled(False)
    rig.c.settings["automation_enabled"] = False
    await rig.c.async_set_watering_enabled(True)
    assert rig.c.watering_enabled
    assert rig.c.settings["automation_enabled"] is False
    assert not opened(rig)
    await rig.c.async_start_manual()
    assert len(opened(rig)) == 1


@pytest.mark.asyncio
async def test_restart_restores_lock_and_closes_open_valve(rig):
    rig.c.store.async_load.return_value = {"settings": {"watering_enabled": False}}
    rig.hass.states.async_set(rig.config[CONF_VALVE], "open")
    await rig.c.async_initialize()
    assert not rig.c.watering_enabled
    assert rig.hass.states.get(rig.config[CONF_VALVE]).state == "closed"
    assert not opened(rig)


@pytest.mark.asyncio
async def test_external_open_report_is_closed_while_disabled(rig):
    await rig.c.async_initialize()
    await rig.c.async_set_watering_enabled(False)
    rig.hass.states.async_set(rig.config[CONF_VALVE], "open")
    await rig.hass.async_block_till_done()
    assert rig.hass.states.get(rig.config[CONF_VALVE]).state == "closed"


@pytest.mark.asyncio
async def test_close_failure_keeps_lock_and_reports_error(rig):
    async def fail(call):
        raise HomeAssistantError("simulated connection error")

    rig.hass.services.async_register("valve", "close_valve", fail)
    with pytest.raises(HomeAssistantError, match="simulated connection error"):
        await rig.c.async_set_watering_enabled(False)
    assert not rig.c.watering_enabled
    assert rig.c.snapshot.status == "stop_failed"
    assert "nicht geschlossen" in rig.c.snapshot.next_action
    assert not ReadySensor(rig.c).is_on
    assert rig.c.store.async_save.call_args.args[0]["settings"]["watering_enabled"] is False


@pytest.mark.asyncio
async def test_storage_failure_still_attempts_to_close(rig):
    rig.c.store.async_save.side_effect = OSError("disk unavailable")
    with pytest.raises(OSError, match="disk unavailable"):
        await rig.c.async_set_watering_enabled(False)
    assert any(call[:2] == ("valve", "close_valve") for call in rig.calls)
    rig.c.store.async_save.side_effect = None


@pytest.mark.asyncio
async def test_start_service_error_does_not_leave_running_flag(rig):
    rig.c._set_runtime = AsyncMock(side_effect=HomeAssistantError("device offline"))
    with pytest.raises(HomeAssistantError, match="device offline"):
        await rig.c.async_start_manual()
    assert not rig.c.snapshot.running
    assert rig.c._run_task is None
    assert rig.c.snapshot.status == "start_failed"


@pytest.mark.asyncio
async def test_entity_switch_uses_winter_lock(rig):
    switch = SettingSwitch(rig.c, "watering_enabled", "Bewässerung freigeben", "mdi:water-check")
    await switch.async_turn_off()
    assert not switch.is_on
    assert not ReadySensor(rig.c).is_on
    await switch.async_turn_on()
    assert switch.is_on
    assert not opened(rig)


@pytest.mark.asyncio
async def test_actual_storage_survives_new_coordinator(rig):
    from homeassistant.helpers.storage import Store

    rig.c.store = Store(rig.hass, 1, "winter_round_trip")
    await rig.c.async_set_watering_enabled(False)
    restored = IrrigationCoordinator(rig.hass, rig.c.entry)
    restored.store = Store(rig.hass, 1, "winter_round_trip")
    await restored.async_initialize()
    assert not restored.watering_enabled
    assert restored.snapshot.status == "watering_disabled"
    assert not opened(rig)
    await restored.async_shutdown()


@pytest.mark.asyncio
async def test_shutdown_cancels_and_closes_active_run(rig):
    await rig.c.async_start_manual()
    task = rig.c._run_task
    await asyncio.sleep(0)
    await rig.c.async_shutdown()
    assert task.cancelled()
    assert rig.hass.states.get(rig.config[CONF_VALVE]).state == "closed"


@pytest.mark.parametrize("year,month", [(2026, 11), (2026, 12)] + [(2027, m) for m in range(1, 11)])
@pytest.mark.asyncio
async def test_winter_lock_holds_for_next_twelve_calendar_months(rig, year, month):
    c = rig.c
    c.settings["watering_enabled"] = False
    simulated = datetime(year, month, 15, 5, 0, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    with patch.object(dt_util, "now", return_value=simulated):
        await c._scheduled_start(simulated)
    assert not opened(rig)
    assert c.snapshot.status == "watering_disabled"


@pytest.mark.asyncio
async def test_automated_recommendation_unchanged_by_lock(rig):
    await rig.c.async_refresh()
    enabled = rig.c.snapshot.as_dict()
    await rig.c.async_set_watering_enabled(False)
    disabled = rig.c.snapshot.as_dict()
    for key in (
        "runtime_minutes",
        "effective_rain_mm",
        "forecast_rain_12h_mm",
        "calculation_temperature_c",
        "dry_days",
        "need_percent",
        "data_quality",
    ):
        assert disabled[key] == enabled[key]
    assert DEFAULTS["watering_enabled"] is True


@pytest.mark.asyncio
async def test_storage_failure_during_running_task_still_closes(rig):
    await rig.c.async_start_manual()
    await asyncio.sleep(0)
    rig.c.store.async_save.side_effect = OSError("disk unavailable")
    with pytest.raises(OSError, match="disk unavailable"):
        await rig.c.async_set_watering_enabled(False)
    assert rig.hass.states.get(rig.config[CONF_VALVE]).state == "closed"
    rig.c.store.async_save.side_effect = None
