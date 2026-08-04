from __future__ import annotations
import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from .const import *
from .models import IrrigationSnapshot
_LOGGER = logging.getLogger(__name__)

class IrrigationCoordinator:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass, self.entry = hass, entry
        self.config = entry.data
        self.store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY.format(entry_id=entry.entry_id))
        self.settings = dict(DEFAULTS)
        self.snapshot = IrrigationSnapshot()
        self.daily: list[dict[str, Any]] = []
        self.logbook: list[dict[str, Any]] = []
        self.skip_date: str | None = None
        self._today_max: float | None = None
        self._listeners: list[Any] = []
        self._subscribers: set[Any] = set()
        self._run_task: asyncio.Task | None = None
        self._refresh_lock = asyncio.Lock()

    async def async_initialize(self) -> None:
        saved = await self.store.async_load() or {}
        self.settings.update(saved.get("settings", {}))
        self.daily = saved.get("daily", [])[-14:]
        self.logbook = saved.get("logbook", [])[-50:]
        self.skip_date = saved.get("skip_date")
        self._today_max = self._state_number(self.config[CONF_TEMPERATURE])
        self._listeners.extend([
            async_track_state_change_event(self.hass, [self.config[CONF_TEMPERATURE]], self._temperature_changed),
            async_track_time_change(self.hass, self._archive_day, hour=23, minute=59, second=45),
            async_track_time_change(self.hass, self._scheduled_check, hour=int(self.settings["start_hour"]), minute=0, second=0),
        ])
        await self.async_refresh()

    async def async_shutdown(self) -> None:
        for unsub in self._listeners: unsub()
        self._listeners.clear()
        if self._run_task: self._run_task.cancel()
        await self._save()

    @callback
    def subscribe(self, listener):
        self._subscribers.add(listener)
        return lambda: self._subscribers.discard(listener)

    @callback
    def notify(self) -> None:
        for listener in list(self._subscribers): listener()

    async def _save(self) -> None:
        await self.store.async_save({"settings": self.settings, "daily": self.daily[-14:], "logbook": self.logbook[-50:], "skip_date": self.skip_date})

    @staticmethod
    def _number(state) -> float | None:
        try: return float(state.state)
        except (AttributeError, TypeError, ValueError): return None

    def _state_number(self, entity_id: str) -> float | None:
        return self._number(self.hass.states.get(entity_id))

    async def _temperature_changed(self, event) -> None:
        value = self._number(event.data.get("new_state"))
        if value is not None: self._today_max = value if self._today_max is None else max(self._today_max, value)

    async def _archive_day(self, now: datetime) -> None:
        date = now.date().isoformat()
        rain = self._state_number(self.config[CONF_PRECIPITATION]) or 0.0
        record = {"date": date, "rain": round(rain, 2), "max_temp": self._today_max}
        self.daily = [x for x in self.daily if x.get("date") != date] + [record]
        self.daily = self.daily[-14:]
        self._today_max = self._state_number(self.config[CONF_TEMPERATURE])
        if self.skip_date and self.skip_date != dt_util.now().date().isoformat(): self.skip_date = None
        await self._save()

    async def _scheduled_check(self, now: datetime) -> None:
        await self.async_refresh()
        if self.settings["automation_enabled"] and not self.is_skipped_today and self.snapshot.runtime_minutes > 0:
            if self._minimum_interval_met(): await self.async_start_automatic()

    @property
    def is_skipped_today(self) -> bool:
        return self.skip_date == dt_util.now().date().isoformat()

    def _minimum_interval_met(self) -> bool:
        if not self.snapshot.last_run: return True
        try: last = dt_util.parse_datetime(self.snapshot.last_run)
        except (TypeError, ValueError): return True
        return last is None or dt_util.now() >= last + timedelta(hours=float(self.settings["minimum_interval"]))

    async def _weather_forecast(self) -> tuple[float, float | None, bool]:
        try:
            response = await self.hass.services.async_call(
                "weather", "get_forecasts", {"type": "hourly", "entity_id": self.config[CONF_WEATHER]},
                blocking=True, return_response=True,
            )
            block = response.get(self.config[CONF_WEATHER], {}) if isinstance(response, dict) else {}
            forecasts = block.get("forecast", []) if isinstance(block, dict) else []
        except Exception as err:
            _LOGGER.warning("Wettervorhersage konnte nicht geladen werden: %s", err)
            return 0.0, None, False
        now, end = dt_util.now(), dt_util.now() + timedelta(hours=12)
        rain, temperatures = 0.0, []
        for item in forecasts:
            when = dt_util.parse_datetime(item.get("datetime")) if item.get("datetime") else None
            if when is None or not (now <= when <= end): continue
            try: rain += max(0.0, float(item.get("precipitation") or 0.0))
            except (TypeError, ValueError): pass
            try: temperatures.append(float(item["temperature"]))
            except (KeyError, TypeError, ValueError): pass
        return round(rain, 2), max(temperatures) if temperatures else None, bool(forecasts)

    async def async_refresh(self) -> None:
        async with self._refresh_lock:
            forecast_rain, forecast_max, forecast_ok = await self._weather_forecast()
            measured_current = self._state_number(self.config[CONF_TEMPERATURE])
            today_rain = self._state_number(self.config[CONF_PRECIPITATION]) or 0.0
            previous = list(reversed(self.daily[-4:]))
            rains = [today_rain] + [float(x.get("rain") or 0) for x in previous]
            weights = [1.0, .75, .50, .30, .15]
            effective = sum(v*w for v,w in zip(rains, weights)) * float(self.settings["rain_effect"]) / 100.0
            yesterday_max = self.daily[-1].get("max_temp") if self.daily else None
            if yesterday_max is None: yesterday_max = measured_current
            calc_temp = None
            if yesterday_max is not None and forecast_max is not None:
                weight = float(self.settings["past_temperature_weight"]) / 100.0
                calc_temp = float(yesterday_max)*weight + float(forecast_max)*(1-weight)
            else: calc_temp = yesterday_max if yesterday_max is not None else forecast_max
            dry_days = 0
            for record in reversed(self.daily[-7:]):
                if float(record.get("rain") or 0) >= 8.0: break
                dry_days += 1
            temp_factor = self._temperature_factor(calc_temp)
            rain_factor = 0 if effective >= 10 else .2 if effective >= 8 else .4 if effective >= 6 else .65 if effective >= 4 else .85 if effective >= 2 else 1.0
            dry_factor = 0 if dry_days == 0 else .6 if dry_days == 1 else .85 if dry_days == 2 else 1.0 if dry_days == 3 else 1.15 if dry_days == 4 else 1.3
            season_factor = {4:.6,5:.8,6:1,7:1,8:1,9:.75,10:.5}.get(dt_util.now().month, 0)
            forecast_factor = 0 if forecast_rain > 8 else .4 if forecast_rain >= 5 else .7 if forecast_rain >= 3 else 1.0
            raw = float(self.settings["base_runtime"])*temp_factor*rain_factor*dry_factor*season_factor*forecast_factor
            runtime = 0 if raw < float(self.settings["min_runtime"]) else min(int(round(raw)), int(self.settings["max_runtime"]))
            quality = "complete" if measured_current is not None and forecast_ok and len(self.daily) >= 4 else "fallback" if measured_current is not None or forecast_ok else "insufficient"
            reason = self._reason(runtime, effective, forecast_rain, quality)
            last_run = self.snapshot.last_run
            next_possible = None
            if last_run:
                parsed = dt_util.parse_datetime(last_run)
                if parsed: next_possible = (parsed + timedelta(hours=float(self.settings["minimum_interval"]))).isoformat()
            self.snapshot = IrrigationSnapshot(
                status="running_manual" if self.snapshot.running and self.snapshot.manual else "running_auto" if self.snapshot.running else "ready",
                reason=reason, data_quality=quality, running=self.snapshot.running, manual=self.snapshot.manual,
                remaining_minutes=self.snapshot.remaining_minutes, effective_rain_mm=round(effective,2),
                forecast_rain_12h_mm=forecast_rain, measured_max_yesterday_c=round(float(yesterday_max),1) if yesterday_max is not None else None,
                forecast_max_today_c=round(float(forecast_max),1) if forecast_max is not None else None,
                calculation_temperature_c=round(float(calc_temp),1) if calc_temp is not None else None,
                dry_days=dry_days, need_percent=min(100, max(0, round(raw/max(1,float(self.settings["max_runtime"]))*100))),
                runtime_minutes=runtime, last_run=last_run, next_possible=next_possible)
            self.notify(); await self._save()

    @staticmethod
    def _temperature_factor(temp: float | None) -> float:
        if temp is None: return 0
        return .4 if temp < 15 else .7 if temp < 20 else 1.0 if temp < 25 else 1.3 if temp < 30 else 1.6

    @staticmethod
    def _reason(runtime: int, effective: float, forecast: float, quality: str) -> str:
        if quality == "insufficient": return "Automatik pausiert: Temperatur- und Wetterdaten fehlen"
        if forecast > 8: return f"Keine Bewässerung: {forecast:.1f} mm Regen in den nächsten 12 Stunden erwartet"
        if effective >= 10: return f"Keine Bewässerung: {effective:.1f} mm wirksamer Niederschlag"
        if runtime <= 0: return "Keine Bewässerung: geringer Bedarf oder Saison inaktiv"
        return f"Bewässerung empfohlen: {runtime} Minuten"

    async def _set_runtime(self, minutes: int) -> None:
        await self.hass.services.async_call("number", "set_value", {"entity_id": self.config[CONF_RUNTIME], "value": minutes}, blocking=True)
    async def _open(self) -> None:
        await self.hass.services.async_call("valve", "open_valve", {"entity_id": self.config[CONF_VALVE]}, blocking=True)
    async def _close(self) -> None:
        await self.hass.services.async_call("valve", "close_valve", {"entity_id": self.config[CONF_VALVE]}, blocking=True)

    async def async_start_automatic(self) -> None:
        if self.snapshot.running or not self.settings["automation_enabled"] or self.is_skipped_today: return
        if self.snapshot.data_quality == "insufficient" or not self._minimum_interval_met(): return
        await self._start(False, self.snapshot.runtime_minutes)

    async def async_start_manual(self) -> None:
        if self.snapshot.running: await self.async_stop()
        await self._start(True, int(self.settings["manual_runtime"]))

    async def _start(self, manual: bool, minutes: int) -> None:
        if minutes <= 0: return
        self.snapshot.running, self.snapshot.manual = True, manual
        self.snapshot.status = "running_manual" if manual else "running_auto"
        self.snapshot.remaining_minutes = minutes
        await self._set_runtime(minutes); await self._open(); self.notify()
        self._run_task = self.hass.async_create_task(self._run(minutes, manual))

    async def _run(self, minutes: int, manual: bool) -> None:
        started = dt_util.now()
        try:
            if not manual and minutes >= int(self.settings["cycle_threshold"]):
                first = (minutes + 1)//2; second = minutes-first
                await self._countdown(first); await self._close()
                self.snapshot.status = "soak_pause"; self.notify()
                await asyncio.sleep(float(self.settings["cycle_pause"])*60)
                await self._open(); await self._countdown(second)
            else: await self._countdown(minutes)
            if not manual or self.settings["safety_enabled"]: await self._close()
            finished = dt_util.now(); self.snapshot.last_run = finished.isoformat()
            self.logbook.append({"started": started.isoformat(), "finished": finished.isoformat(), "mode": "manual" if manual else "automatic", "planned_minutes": minutes, "actual_minutes": round((finished-started).total_seconds()/60,1), "temperature": self.snapshot.calculation_temperature_c, "effective_rain": self.snapshot.effective_rain_mm, "forecast_rain": self.snapshot.forecast_rain_12h_mm, "reason": self.snapshot.reason})
        except asyncio.CancelledError: raise
        finally:
            self.snapshot.running=False; self.snapshot.manual=False; self.snapshot.remaining_minutes=0; self.snapshot.status="ready"; self._run_task=None
            self.notify(); await self._save()

    async def _countdown(self, minutes: int) -> None:
        for remaining in range(minutes,0,-1):
            self.snapshot.remaining_minutes=remaining; self.notify(); await asyncio.sleep(60)

    async def async_stop(self) -> None:
        task, self._run_task = self._run_task, None
        if task: task.cancel()
        await self._close()
        self.snapshot.running=False; self.snapshot.manual=False; self.snapshot.remaining_minutes=0; self.snapshot.status="stopped"
        self.notify(); await self._save()

    async def async_set_setting(self, key: str, value: Any) -> None:
        self.settings[key]=value
        if key == "start_hour":
            # New schedule becomes active after reload; options UI documents this.
            pass
        await self.async_refresh()

    async def async_set_skip_today(self, enabled: bool) -> None:
        self.skip_date = dt_util.now().date().isoformat() if enabled else None
        self.notify(); await self._save()
