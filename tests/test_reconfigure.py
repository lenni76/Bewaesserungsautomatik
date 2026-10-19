"""Exercise reconfiguration with HA's real ConfigEntry update helper."""

import asyncio
from copy import deepcopy
from types import MappingProxyType, SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
import pytest_asyncio
from homeassistant.config_entries import ConfigEntries, ConfigEntry
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from custom_components.bewaesserungsautomatik.config_flow import ConfigFlow
from custom_components.bewaesserungsautomatik.const import CONF_HISTORY_GENERATION, DOMAIN
from custom_components.bewaesserungsautomatik.coordinator import IrrigationCoordinator


@pytest_asyncio.fixture
async def form(rig):
    hass = rig.hass
    hass.config_entries = ConfigEntries(hass, {})
    # Core's own entry-store writer is not under test in this partial HA setup.
    # Our integration's Store persistence has a separate real disk round-trip.
    hass.config_entries._async_schedule_save = Mock()
    entry = ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="Bewässerungsautomatik",
        data={**rig.config, "plant_profile": "flower_bed", "exposure": "sunny"},
        options={},
        source="user",
        unique_id=DOMAIN,
        discovery_keys=MappingProxyType({}),
        subentries_data=[],
    )
    with patch.object(hass.config_entries, "async_setup", new=AsyncMock(return_value=True)):
        await hass.config_entries.async_add(entry)
    flow = ConfigFlow()
    rig.c.entry = entry
    rig.c.config = entry.data
    flow.hass = hass
    flow.context = {"source": "reconfigure", "entry_id": entry.entry_id}
    hass.data[DOMAIN] = {entry.entry_id: rig.c}
    with patch.object(hass.config_entries, "async_schedule_reload", new=Mock()) as reload:
        yield SimpleNamespace(flow=flow, entry=entry, reload=reload, values=dict(entry.data))


@pytest.mark.asyncio
async def test_initial_setup_validates_sources_and_creates_entry(rig):
    rig.hass.config_entries = ConfigEntries(rig.hass, {})
    flow = ConfigFlow()
    flow.hass = rig.hass
    flow.flow_id = "initial_test"
    flow.context = {"source": "user"}
    result = await flow.async_step_user(rig.config | {"plant_profile": "flower_bed", "exposure": "sunny"})
    assert result["type"] == "create_entry"
    assert result["data"]["weather_entity"] == rig.config["weather_entity"]


@pytest.mark.asyncio
async def test_legacy_run_log_is_migrated_into_last_run(rig):
    finished = (dt_util.now()).isoformat()
    rig.c.store.async_load.return_value = {"logbook": [{"finished": finished}]}
    await rig.c.async_initialize()
    assert rig.c.snapshot.last_run == finished
    assert not rig.c._minimum_interval_met()


@pytest.mark.asyncio
async def test_form_is_prefilled_and_has_no_device_side_effects(rig, form):
    result = await form.flow.async_step_reconfigure()
    values = result["data_schema"]({})
    assert result["step_id"] == "reconfigure"
    assert values["temperature_entity"] == rig.config["temperature_entity"]
    assert values["reset_weather_history"] is False
    assert rig.calls == []
    form.reload.assert_not_called()


@pytest.mark.asyncio
async def test_changes_update_same_entry_and_preserve_unrelated_data(rig, form):
    rig.hass.states.async_set("sensor.new_temperature", "22", {"unit_of_measurement": "°C"})
    values = form.values | {"temperature_entity": "sensor.new_temperature"}
    entry_id = form.entry.entry_id
    unique_id = form.entry.unique_id
    result = await form.flow.async_step_reconfigure(values)
    assert result["type"] == "abort"
    assert result["reason"] == "reconfigure_successful"
    assert form.entry.entry_id == entry_id
    assert form.entry.unique_id == unique_id
    assert form.entry.data["temperature_entity"] == "sensor.new_temperature"
    assert len(rig.hass.config_entries.async_entries(DOMAIN)) == 1
    assert form.entry.data["plant_profile"] == "flower_bed"
    assert rig.c.settings["watering_enabled"] is True  # Persisted user choice unchanged.
    assert rig.c._reconfiguring  # Old coordinator cannot start while reload is queued.
    form.reload.assert_called_once_with(entry_id)


@pytest.mark.asyncio
async def test_invalid_source_does_not_update_entry_or_reload(rig, form):
    before = dict(form.entry.data)
    result = await form.flow.async_step_reconfigure(form.values | {"temperature_entity": "sensor.missing"})
    assert result["errors"]["temperature_entity"] == "entity_unavailable"
    assert dict(form.entry.data) == before
    assert not rig.c._reconfiguring
    form.reload.assert_not_called()
    assert rig.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,entity,value,attrs,error",
    [
        ("temperature_entity", "sensor.bad", "NaN", {"unit_of_measurement": "°C"}, "invalid_temperature"),
        ("temperature_entity", "sensor.bad", "25", {"unit_of_measurement": "%"}, "invalid_temperature"),
        ("precipitation_entity", "sensor.bad", "4", {"unit_of_measurement": "mm/h"}, "invalid_rain"),
        ("precipitation_entity", "sensor.bad", "-1", {"unit_of_measurement": "mm"}, "invalid_rain"),
        ("weather_entity", "weather.bad", "sunny", {"supported_features": 1}, "hourly_forecast_required"),
    ],
)
async def test_invalid_units_values_and_forecast_capability(rig, form, field, entity, value, attrs, error):
    rig.hass.states.async_set(entity, value, attrs)
    result = await form.flow.async_step_reconfigure(form.values | {field: entity})
    assert result["errors"][field] == error
    form.reload.assert_not_called()


@pytest.mark.asyncio
async def test_history_reset_is_explicit_and_not_stored_as_checkbox(rig, form):
    result = await form.flow.async_step_reconfigure(form.values | {"reset_weather_history": True})
    assert result["type"] == "abort"
    assert form.entry.data[CONF_HISTORY_GENERATION] == 1
    assert "reset_weather_history" not in form.entry.data


@pytest.mark.asyncio
async def test_unchanged_form_does_not_interrupt_or_reload(rig, form):
    result = await form.flow.async_step_reconfigure(form.values)
    assert result["type"] == "abort"
    assert not rig.c._reconfiguring
    form.reload.assert_not_called()
    assert rig.calls == []


@pytest.mark.asyncio
async def test_active_old_valve_is_closed_before_entry_changes(rig, form):
    await rig.c.async_start_manual()
    await asyncio.sleep(0)
    rig.hass.states.async_set("sensor.new_temperature", "23", {"unit_of_measurement": "°C"})
    result = await form.flow.async_step_reconfigure(form.values | {"temperature_entity": "sensor.new_temperature"})
    assert result["type"] == "abort"
    assert rig.hass.states.get(rig.config["valve_entity"]).state == "closed"
    assert rig.c._run_task is None
    assert rig.c.snapshot.last_run is not None


@pytest.mark.asyncio
async def test_failed_stop_leaves_assignments_unchanged(rig, form):
    await rig.c.async_start_manual()

    async def fail(call):
        raise HomeAssistantError("offline")

    rig.hass.services.async_register("valve", "close_valve", fail)
    rig.hass.states.async_set("sensor.new_temperature", "23", {"unit_of_measurement": "°C"})
    before = dict(form.entry.data)
    result = await form.flow.async_step_reconfigure(form.values | {"temperature_entity": "sensor.new_temperature"})
    assert result["errors"]["base"] == "cannot_stop"
    assert dict(form.entry.data) == before
    form.reload.assert_not_called()


@pytest.mark.asyncio
async def test_unchanged_offline_actuators_do_not_block_station_change(rig, form):
    rig.hass.states.async_set(rig.config["valve_entity"], "unavailable")
    rig.hass.states.async_set(rig.config["runtime_entity"], "unavailable")
    rig.hass.states.async_set("sensor.new_temperature", "23", {"unit_of_measurement": "°C"})
    result = await form.flow.async_step_reconfigure(form.values | {"temperature_entity": "sensor.new_temperature"})
    assert result["type"] == "abort"


@pytest.mark.asyncio
@pytest.mark.parametrize("reset", [False, True])
async def test_reload_keeps_settings_lock_log_and_last_run_and_optionally_resets_weather(rig, reset):
    c = rig.c
    c.store = Store(rig.hass, 1, "station_change")
    c.settings.update(watering_enabled=False, base_runtime=30, start_time="06:30:00")
    c.daily = [{"date": "2026-10-18", "rain": 2, "max_temp": 21}]
    c.logbook = [{"finished": "2026-10-18T06:00:00+02:00"}]
    c.snapshot.last_run = dt_util.now().isoformat()
    await c.async_shutdown()
    new_entry = SimpleNamespace(entry_id=c.entry.entry_id, data=dict(c.config))
    if reset:
        new_entry.data[CONF_HISTORY_GENERATION] = 1
    new_c = IrrigationCoordinator(rig.hass, new_entry)
    new_c.store = Store(rig.hass, 1, "station_change")
    try:
        await new_c.async_initialize()
        assert new_c.settings["watering_enabled"] is False
        assert new_c.settings["base_runtime"] == 30
        assert new_c.settings["start_time"] == "06:30:00"
        assert new_c.snapshot.last_run == c.snapshot.last_run
        assert not new_c._minimum_interval_met()
        assert new_c.logbook == c.logbook
        assert new_c.daily == ([] if reset else c.daily)
    finally:
        await new_c.async_shutdown()


@pytest.mark.asyncio
async def test_new_temperature_subscription_replaces_old_one(rig):
    c = rig.c
    await c.async_initialize()
    await c.async_prepare_reconfigure()
    saved = deepcopy(c.store.async_save.call_args.args[0])
    await c.async_shutdown()
    rig.hass.states.async_set("sensor.new_temperature", "18", {"unit_of_measurement": "°C"})
    config = dict(c.config) | {"temperature_entity": "sensor.new_temperature", CONF_HISTORY_GENERATION: 1}
    new_c = IrrigationCoordinator(rig.hass, SimpleNamespace(data=config, entry_id=c.entry.entry_id))
    new_c.store.async_load = AsyncMock(return_value=saved)
    new_c.store.async_save = AsyncMock()
    try:
        await new_c.async_initialize()
        rig.hass.states.async_set(rig.config["temperature_entity"], "100", {"unit_of_measurement": "°C"})
        rig.hass.states.async_set("sensor.new_temperature", "20", {"unit_of_measurement": "°C"})
        await rig.hass.async_block_till_done()
        assert new_c._today_max == 20
        assert not c._listeners
    finally:
        await new_c.async_shutdown()
