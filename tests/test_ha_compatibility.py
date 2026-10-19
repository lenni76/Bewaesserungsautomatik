"""API smoke checks against the installed, real Home Assistant version."""

import importlib
from pathlib import Path

import pytest
from homeassistant.config_entries import ConfigEntries

from custom_components.bewaesserungsautomatik.config_flow import ConfigFlow
from custom_components.bewaesserungsautomatik.const import DOMAIN


def test_all_integration_modules_import_against_installed_ha():
    for path in Path("custom_components/bewaesserungsautomatik").glob("*.py"):
        importlib.import_module(f"custom_components.bewaesserungsautomatik.{path.stem}")


@pytest.mark.asyncio
async def test_config_flow_form_uses_actual_ha_selectors(rig):
    rig.hass.config_entries = ConfigEntries(rig.hass, {})
    flow = ConfigFlow()
    flow.hass = rig.hass
    result = await flow.async_step_user()
    assert result["type"] == "form"
    validated = result["data_schema"]({**rig.config, "plant_profile": "flower_bed", "exposure": "sunny"})
    assert validated["valve_entity"] == "valve.test"


@pytest.mark.asyncio
async def test_all_platforms_create_ha_entities(rig):
    rig.hass.data[DOMAIN] = {rig.c.entry.entry_id: rig.c}
    entities = []
    for platform in ("sensor", "binary_sensor", "switch", "number", "button", "time", "text"):
        module = importlib.import_module(f"custom_components.bewaesserungsautomatik.{platform}")
        await module.async_setup_entry(rig.hass, rig.c.entry, entities.extend)
    ids = [entity.unique_id for entity in entities]
    assert len(ids) == len(set(ids))
    assert any(entity.unique_id.endswith("_watering_enabled") for entity in entities)
    for entity in entities:
        entity.hass = rig.hass
        # DeviceInfo, units, state values and public properties are real HA objects.
        assert entity.device_info is not None
        assert entity.name
        _ = entity.state


@pytest.mark.asyncio
async def test_entity_subscription_and_removal(rig):
    from custom_components.bewaesserungsautomatik.entity import IrrigationEntity

    entity = IrrigationEntity(rig.c, "lifecycle_test")
    # notify() invokes a synchronous HA callback, just as Entity does.
    recorded = []
    entity.async_write_ha_state = lambda: recorded.append(True)
    unsubscribers = []
    entity.async_on_remove = unsubscribers.append
    await entity.async_added_to_hass()
    rig.c.notify()
    assert recorded == [True]
    for unsubscribe in unsubscribers:
        unsubscribe()
    rig.c.notify()
    assert recorded == [True]


@pytest.mark.asyncio
async def test_device_info_uses_supported_keyword_fields(rig):
    from homeassistant.helpers.device_registry import DeviceInfo

    from custom_components.bewaesserungsautomatik.entity import IrrigationEntity

    info = IrrigationEntity(rig.c, "metadata").device_info
    fields = {"identifiers", "name", "manufacturer", "model", "sw_version"}
    # TypedDict on stable and dataclass on newer HA: no mapping operations required.
    if isinstance(info, dict):
        assert fields <= info.keys()
    else:
        assert isinstance(info, DeviceInfo)
        assert all(getattr(info, field) is not None for field in fields)
