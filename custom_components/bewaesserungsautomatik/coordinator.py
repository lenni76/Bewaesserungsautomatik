from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from datetime import datetime, time, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later, async_track_state_change_event, async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_HISTORY_GENERATION,
    CONF_PRECIPITATION,
    CONF_RUNTIME,
    CONF_TEMPERATURE,
    CONF_VALVE,
    CONF_WEATHER,
    DEFAULTS,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .models import IrrigationSnapshot
from .weather_data import async_forecast, finite_number, rain_mm, sensor_rain, sensor_temperature, temperature_c

_LOGGER = logging.getLogger(__name__)


class IrrigationCoordinator:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.config = entry.data
        self.store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY.format(entry_id=entry.entry_id))
        self.settings = dict(DEFAULTS)
        self.snapshot = IrrigationSnapshot()
        self.daily: list[dict[str, Any]] = []
        self.logbook: list[dict[str, Any]] = []
        self.skip_date: str | None = None
        self._today_max: float | None = None
        self._listeners: list[Any] = []
        self._schedule_listeners: list[Any] = []
        self._subscribers: set[Any] = set()
        self._run_task: asyncio.Task | None = None
        self._refresh_lock = asyncio.Lock()
        self._operation_lock = asyncio.Lock()
        self._valve_lock = asyncio.Lock()
        self._watering_setting_lock = asyncio.Lock()
        self._close_failed = False
        self._reconfiguring = False
        self._refresh_debounce_unsub = None
        self._last_refresh_temperature: float | None = None
        self._last_refresh_rain: float | None = None

    async def async_initialize(self) -> None:
        saved = await self.store.async_load() or {}
        self.settings.update(saved.get("settings", {}))
        # Migration from 1.0.0 storage.
        if "start_time" not in self.settings:
            hour = int(float(self.settings.pop("start_hour", 5)))
            self.settings["start_time"] = f"{hour:02d}:00:00"
        reset_history = saved.get(CONF_HISTORY_GENERATION, 0) != self.config.get(CONF_HISTORY_GENERATION, 0)
        self.daily = [] if reset_history else saved.get("daily", [])[-14:]
        self.logbook = saved.get("logbook", [])[-50:]
        self.skip_date = saved.get("skip_date")
        # Migrate older installations from their successful-run log, validating
        # the newly persisted timestamp as well before it can affect scheduling.
        completed = [saved.get("last_run")] + [x.get("finished") for x in self.logbook]
        valid = []
        for value in completed:
            if not isinstance(value, str):
                continue
            try:
                parsed = dt_util.parse_datetime(value)
            except (TypeError, ValueError):
                continue
            if parsed and parsed.tzinfo is not None:
                valid.append(parsed)
        self.snapshot.last_run = max(valid).isoformat() if valid else None
        current = self._state_number(self.config[CONF_TEMPERATURE])
        saved_max = (
            finite_number(saved.get("today_max"))
            if not reset_history and saved.get("today_date") == dt_util.now().date().isoformat()
            else None
        )
        self._today_max = (
            max(v for v in (current, saved_max) if v is not None)
            if current is not None or saved_max is not None
            else None
        )
        self._listeners.extend(
            [
                async_track_state_change_event(self.hass, [self.config[CONF_TEMPERATURE]], self._temperature_changed),
                async_track_state_change_event(
                    self.hass, [self.config[CONF_PRECIPITATION]], self._precipitation_changed
                ),
                async_track_state_change_event(self.hass, [self.config[CONF_WEATHER]], self._weather_changed),
                async_track_state_change_event(self.hass, [self.config[CONF_VALVE]], self._valve_changed),
                async_track_time_change(self.hass, self._archive_day, hour=23, minute=59, second=45),
            ]
        )
        self._reschedule_daily_jobs()
        if not self.watering_enabled:
            await self._enforce_winter_lock()
        await self.async_refresh()

    async def async_shutdown(self) -> None:
        for unsub in self._listeners + self._schedule_listeners:
            unsub()
        self._listeners.clear()
        self._schedule_listeners.clear()
        if self._run_task or self.snapshot.running:
            await self.async_stop()
        if self._refresh_debounce_unsub:
            self._refresh_debounce_unsub()
            self._refresh_debounce_unsub = None
        await self._save()

    @callback
    def subscribe(self, listener):
        self._subscribers.add(listener)
        return lambda: self._subscribers.discard(listener)

    @callback
    def notify(self) -> None:
        for listener in list(self._subscribers):
            listener()

    async def _save(self) -> None:
        await self.store.async_save(
            {
                "settings": self.settings,
                "daily": self.daily[-14:],
                "logbook": self.logbook[-50:],
                "skip_date": self.skip_date,
                "last_run": self.snapshot.last_run,
                "today_date": dt_util.now().date().isoformat(),
                "today_max": self._today_max,
                CONF_HISTORY_GENERATION: self.config.get(CONF_HISTORY_GENERATION, 0),
            }
        )

    @staticmethod
    def _number(state) -> float | None:
        try:
            return finite_number(state.state)
        except (AttributeError, TypeError, ValueError):
            return None

    def _state_number(self, entity_id: str) -> float | None:
        if entity_id == self.config[CONF_TEMPERATURE]:
            return sensor_temperature(self.hass, entity_id)
        if entity_id == self.config[CONF_PRECIPITATION]:
            return sensor_rain(self.hass, entity_id)
        return self._number(self.hass.states.get(entity_id))

    @property
    def watering_enabled(self) -> bool:
        """Whether any watering is allowed, independently of calculations."""
        return bool(self.settings["watering_enabled"]) and not self._reconfiguring

    def _idle_status(self) -> str:
        if self._close_failed:
            return "stop_failed"
        return "ready" if self.watering_enabled else "watering_disabled"

    async def _valve_changed(self, event) -> None:
        state = event.data.get("new_state")
        if not self.watering_enabled and state and state.state in ("open", "opening"):
            await self._enforce_winter_lock()

    async def _enforce_winter_lock(self) -> None:
        """Close a valve found open after restart or an external command."""
        state = self.hass.states.get(self.config[CONF_VALVE])
        if not self.watering_enabled and state and state.state in ("open", "opening"):
            try:
                await self.async_stop()
            except HomeAssistantError:
                _LOGGER.exception("Wintersperre aktiv, Ventil konnte nicht geschlossen werden")

    async def _temperature_changed(self, event) -> None:
        state = event.data.get("new_state")
        value = temperature_c(state.state, state.attributes.get("unit_of_measurement")) if state else None
        if value is None:
            self._schedule_event_refresh("Temperaturdaten fehlen")
            return
        self._today_max = value if self._today_max is None else max(self._today_max, value)
        reference = self._last_refresh_temperature
        if reference is None or abs(value - reference) >= 2.0:
            self._schedule_event_refresh("Temperaturänderung")

    async def _precipitation_changed(self, event) -> None:
        state = event.data.get("new_state")
        value = rain_mm(state.state, state.attributes.get("unit_of_measurement")) if state else None
        if value is None:
            self._schedule_event_refresh("Niederschlagsdaten fehlen")
            return
        reference = self._last_refresh_rain
        if reference is None or abs(value - reference) >= 0.1:
            self._schedule_event_refresh("Niederschlagsänderung")

    async def _weather_changed(self, event) -> None:
        if event.data.get("new_state") is not None:
            self._schedule_event_refresh("neue Wettervorhersage")

    @callback
    def _schedule_event_refresh(self, reason: str) -> None:
        """Debounce several related state updates into one calculation."""
        if self._refresh_debounce_unsub:
            self._refresh_debounce_unsub()

        async def _run_refresh(_now) -> None:
            self._refresh_debounce_unsub = None
            _LOGGER.debug("Neuberechnung wegen %s", reason)
            await self.async_refresh()

        self._refresh_debounce_unsub = async_call_later(self.hass, 5, _run_refresh)

    def _configured_start_time(self) -> time:
        try:
            return time.fromisoformat(str(self.settings["start_time"]))
        except (TypeError, ValueError):
            return time(5, 0)

    def _reschedule_daily_jobs(self) -> None:
        for unsub in self._schedule_listeners:
            unsub()
        self._schedule_listeners.clear()
        start = self._configured_start_time()
        prep_dt = datetime.combine(dt_util.now().date(), start) - timedelta(minutes=10)
        self._schedule_listeners.extend(
            [
                async_track_time_change(
                    self.hass,
                    self._scheduled_prepare,
                    hour=prep_dt.hour,
                    minute=prep_dt.minute,
                    second=0,
                ),
                async_track_time_change(
                    self.hass,
                    self._scheduled_start,
                    hour=start.hour,
                    minute=start.minute,
                    second=start.second,
                ),
            ]
        )

    async def _archive_day(self, now: datetime) -> None:
        date = now.date().isoformat()
        rain = self._state_number(self.config[CONF_PRECIPITATION])
        record = {"date": date, "rain": round(rain, 2) if rain is not None else None, "max_temp": self._today_max}
        self.daily = [x for x in self.daily if x.get("date") != date] + [record]
        self.daily = self.daily[-14:]
        self._today_max = self._state_number(self.config[CONF_TEMPERATURE])
        if self.skip_date and self.skip_date != dt_util.now().date().isoformat():
            self.skip_date = None
        await self._save()
        await self.async_refresh()

    async def _scheduled_prepare(self, now: datetime) -> None:
        await self.async_refresh()
        self.snapshot.prepared_at = dt_util.now().isoformat()
        self.snapshot.planned_start = self._next_start_datetime(today=True).isoformat()
        self.snapshot.status = (
            "prepared" if self.watering_enabled and self.snapshot.runtime_minutes > 0 else self._idle_status()
        )
        self.snapshot.next_action = self._build_next_action()
        self.notify()
        await self._save()

    async def _scheduled_start(self, now: datetime) -> None:
        # Final re-check immediately before opening the valve.
        await self.async_refresh()
        if not self.watering_enabled:
            return
        if not self.settings["automation_enabled"]:
            await self._notify_user("Bewässerung ausgelassen", "Die Automatik ist deaktiviert.")
            return
        if self.is_skipped_today:
            await self._notify_user("Bewässerung ausgelassen", "Die Bewässerung ist für heute gesperrt.")
            return
        if self.snapshot.runtime_minutes <= 0 or not self._minimum_interval_met():
            await self._notify_user("Bewässerung ausgelassen", self.snapshot.reason)
            return
        await self.async_start_automatic()

    @property
    def is_skipped_today(self) -> bool:
        return self.skip_date == dt_util.now().date().isoformat()

    def _minimum_interval_met(self) -> bool:
        if not self.snapshot.last_run:
            return True
        try:
            last = dt_util.parse_datetime(self.snapshot.last_run)
        except (TypeError, ValueError):
            return True
        return last is None or dt_util.now() >= last + timedelta(hours=float(self.settings["minimum_interval"]))

    def _next_start_datetime(self, today: bool = False) -> datetime:
        now = dt_util.now()
        start = self._configured_start_time()
        candidate = datetime.combine(now.date(), start, tzinfo=now.tzinfo)
        if not today and candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    def _build_next_action(self) -> str:
        if self._close_failed:
            return "Ventil konnte nicht geschlossen werden – Anschluss prüfen"
        if self._reconfiguring:
            return "Konfiguration wird gewechselt – Bewässerung vorübergehend gesperrt"
        if not self.watering_enabled:
            return "Bewässerung gesperrt (Winterpause) – Berechnung läuft weiter"
        if self.snapshot.running:
            mode = "Manueller Betrieb" if self.snapshot.manual else "Bewässerung"
            return f"{mode} läuft – noch {self.snapshot.remaining_minutes} Minuten"
        if not self.settings["automation_enabled"]:
            return "Automatik deaktiviert"
        if self.is_skipped_today:
            return "Heute keine Bewässerung"
        start = self._next_start_datetime()
        if self.snapshot.runtime_minutes > 0:
            return f"{start.strftime('%d.%m. %H:%M')} Uhr – {self.snapshot.runtime_minutes} Minuten"
        return f"Nächste Prüfung {start.strftime('%d.%m. %H:%M')} Uhr"

    async def _weather_forecast(self) -> tuple[float | None, float | None, bool]:
        try:
            return await async_forecast(self.hass, self.config[CONF_WEATHER])
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Wettervorhersage konnte nicht geladen werden: %s", err)
            return None, None, False

    async def async_refresh(self) -> None:
        async with self._refresh_lock:
            forecast_rain, forecast_max, forecast_ok = await self._weather_forecast()
            measured_current = self._state_number(self.config[CONF_TEMPERATURE])
            today_rain = self._state_number(self.config[CONF_PRECIPITATION])
            self._last_refresh_temperature = measured_current
            self._last_refresh_rain = today_rain
            previous = list(reversed(self.daily[-4:]))
            rains = [today_rain] + [finite_number(x.get("rain")) for x in previous]
            weights = [1.0, 0.75, 0.50, 0.30, 0.15]
            effective = (
                sum(value * weight for value, weight in zip(rains, weights) if value is not None)
                * float(self.settings["rain_effect"])
                / 100.0
            )
            if today_rain is None:
                effective = None
            yesterday_max = self.daily[-1].get("max_temp") if self.daily else None
            if yesterday_max is None:
                yesterday_max = measured_current
            if yesterday_max is not None and forecast_max is not None:
                weight = float(self.settings["past_temperature_weight"]) / 100.0
                calc_temp = float(yesterday_max) * weight + float(forecast_max) * (1 - weight)
            else:
                calc_temp = yesterday_max if yesterday_max is not None else forecast_max
            # A fresh installation has no completed daily history yet. Treat a
            # currently dry day as one dry day instead of multiplying the
            # irrigation demand by zero until the first midnight archive exists.
            if not self.daily:
                dry_days = 0 if today_rain is None or today_rain >= 8.0 else 1
            else:
                dry_days = 0
                for record in reversed(self.daily[-7:]):
                    rain = finite_number(record.get("rain"))
                    if rain is None or rain >= 8.0:
                        break
                    dry_days += 1
            temp_factor = self._temperature_factor(calc_temp)
            rain_factor = (
                0
                if effective is None or effective >= 10
                else 0.2
                if effective >= 8
                else 0.4
                if effective >= 6
                else 0.65
                if effective >= 4
                else 0.85
                if effective >= 2
                else 1.0
            )
            dry_factor = (
                0
                if dry_days == 0
                else 0.6
                if dry_days == 1
                else 0.85
                if dry_days == 2
                else 1.0
                if dry_days == 3
                else 1.15
                if dry_days == 4
                else 1.3
            )
            season_factor = {4: 0.6, 5: 0.8, 6: 1, 7: 1, 8: 1, 9: 0.75, 10: 0.5}.get(dt_util.now().month, 0)
            forecast_factor = (
                1.0
                if forecast_rain is None
                else (0 if forecast_rain > 8 else 0.4 if forecast_rain >= 5 else 0.7 if forecast_rain >= 3 else 1.0)
            )
            raw = (
                float(self.settings["base_runtime"])
                * temp_factor
                * rain_factor
                * dry_factor
                * season_factor
                * forecast_factor
            )
            runtime = (
                0
                if raw < float(self.settings["min_runtime"])
                else min(int(round(raw)), int(self.settings["max_runtime"]))
            )
            quality = (
                "complete"
                if measured_current is not None
                and today_rain is not None
                and forecast_ok
                and len(self.daily) >= 4
                and all(value is not None for value in rains)
                else "fallback"
                if today_rain is not None and (measured_current is not None or forecast_ok)
                else "insufficient"
            )
            reason = self._reason(runtime, effective, forecast_rain, quality)
            last_run = self.snapshot.last_run
            next_possible = None
            if last_run:
                parsed = dt_util.parse_datetime(last_run)
                if parsed:
                    next_possible = (parsed + timedelta(hours=float(self.settings["minimum_interval"]))).isoformat()
            running = self.snapshot.running
            manual = self.snapshot.manual
            remaining = self.snapshot.remaining_minutes
            prepared_at = self.snapshot.prepared_at
            planned_start = self.snapshot.planned_start
            self.snapshot = IrrigationSnapshot(
                status="running_manual" if running and manual else "running_auto" if running else self._idle_status(),
                reason=reason,
                data_quality=quality,
                running=running,
                manual=manual,
                remaining_minutes=remaining,
                effective_rain_mm=round(effective, 2) if effective is not None else None,
                forecast_rain_12h_mm=forecast_rain,
                measured_max_yesterday_c=round(float(yesterday_max), 1) if yesterday_max is not None else None,
                forecast_max_today_c=round(float(forecast_max), 1) if forecast_max is not None else None,
                calculation_temperature_c=round(float(calc_temp), 1) if calc_temp is not None else None,
                dry_days=dry_days,
                need_percent=min(100, max(0, round(raw / max(1, float(self.settings["max_runtime"])) * 100))),
                runtime_minutes=runtime,
                last_run=last_run,
                next_possible=next_possible,
                prepared_at=prepared_at,
                planned_start=planned_start,
            )
            self.snapshot.next_action = self._build_next_action()
            self.notify()
            await self._save()

    @staticmethod
    def _temperature_factor(temp: float | None) -> float:
        if temp is None:
            return 0
        return 0.4 if temp < 15 else 0.7 if temp < 20 else 1.0 if temp < 25 else 1.3 if temp < 30 else 1.6

    @staticmethod
    def _reason(runtime: int, effective: float | None, forecast: float | None, quality: str) -> str:
        if quality == "insufficient":
            return "Automatik pausiert: erforderliche Temperatur- oder Niederschlagsdaten fehlen"
        if forecast is not None and forecast > 8:
            return f"Keine Bewässerung: {forecast:.1f} mm Regen in den nächsten 12 Stunden erwartet"
        if effective is not None and effective >= 10:
            return f"Keine Bewässerung: {effective:.1f} mm wirksamer Niederschlag"
        if runtime <= 0:
            return "Keine Bewässerung: geringer Bedarf oder Saison inaktiv"
        return f"Bewässerung empfohlen: {runtime} Minuten"

    async def _notify_user(self, title: str, message: str) -> None:
        if not self.settings.get("notifications_enabled"):
            return
        configured = str(self.settings.get("notification_service", "")).strip()
        if not configured or "." not in configured:
            _LOGGER.warning("Benachrichtigung aktiv, aber kein gültiger Dienst konfiguriert")
            return
        domain, service = configured.split(".", 1)
        if not self.hass.services.has_service(domain, service):
            _LOGGER.warning("Benachrichtigungsdienst %s ist nicht verfügbar", configured)
            return
        try:
            await self.hass.services.async_call(domain, service, {"title": title, "message": message}, blocking=False)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Benachrichtigung fehlgeschlagen: %s", err)

    async def _set_runtime(self, minutes: int) -> None:
        await self.hass.services.async_call(
            "number", "set_value", {"entity_id": self.config[CONF_RUNTIME], "value": minutes}, blocking=True
        )

    async def _open(self) -> bool:
        # Also guards reopening after a soak pause and an in-flight start.
        async with self._valve_lock:
            if not self.watering_enabled:
                return False
            await self.hass.services.async_call(
                "valve", "open_valve", {"entity_id": self.config[CONF_VALVE]}, blocking=True
            )
            return True

    async def _close(self) -> None:
        async with self._valve_lock:
            try:
                await self.hass.services.async_call(
                    "valve", "close_valve", {"entity_id": self.config[CONF_VALVE]}, blocking=True
                )
            except HomeAssistantError:
                self._close_failed = True
                raise
            self._close_failed = False

    async def async_start_automatic(self) -> None:
        if not self.watering_enabled:
            raise HomeAssistantError("Bewässerung gesperrt: zuerst Bewässerung freigeben einschalten")
        if self.snapshot.running or not self.settings["automation_enabled"] or self.is_skipped_today:
            return
        if self.snapshot.data_quality == "insufficient" or not self._minimum_interval_met():
            return
        await self._start(False, self.snapshot.runtime_minutes)

    async def async_start_manual(self) -> None:
        if not self.watering_enabled:
            raise HomeAssistantError("Bewässerung gesperrt: zuerst Bewässerung freigeben einschalten")
        if self.snapshot.running:
            await self.async_stop()
        await self._start(True, int(self.settings["manual_runtime"]))

    async def _start(self, manual: bool, minutes: int) -> None:
        async with self._operation_lock:
            if not self.watering_enabled or self.snapshot.running or minutes <= 0:
                return
            self.snapshot.running = True
            self.snapshot.manual = manual
            self.snapshot.status = "running_manual" if manual else "running_auto"
            self.snapshot.remaining_minutes = minutes
            try:
                await self._set_runtime(minutes)
                if not await self._open():
                    self.snapshot.running = False
                    self.snapshot.manual = False
                    self.snapshot.remaining_minutes = 0
                    self.snapshot.status = self._idle_status()
                    self.snapshot.next_action = self._build_next_action()
                    self.notify()
                    return
            except Exception:
                self.snapshot.running = False
                self.snapshot.manual = False
                self.snapshot.remaining_minutes = 0
                self.snapshot.status = "start_failed"
                self.snapshot.next_action = self._build_next_action()
                self.notify()
                raise
            self.snapshot.next_action = self._build_next_action()
            self._run_task = self.hass.async_create_task(self._run(minutes, manual))
            self.notify()
            await self._notify_user(
                "Wasserbetrieb gestartet" if manual else "Bewässerung gestartet",
                f"Geplante Laufzeit: {minutes} Minuten.",
            )

    async def _run(self, minutes: int, manual: bool) -> None:
        started = dt_util.now()
        try:
            if not manual and minutes >= int(self.settings["cycle_threshold"]):
                first = (minutes + 1) // 2
                second = minutes - first
                await self._countdown(first)
                await self._close()
                self.snapshot.status = "soak_pause"
                self.snapshot.next_action = f"Versickerungspause – {int(self.settings['cycle_pause'])} Minuten"
                self.notify()
                await asyncio.sleep(float(self.settings["cycle_pause"]) * 60)
                if not await self._open():
                    return
                await self._countdown(second)
            else:
                await self._countdown(minutes)
            if not manual or self.settings["safety_enabled"]:
                await self._close()
            finished = dt_util.now()
            self.snapshot.last_run = finished.isoformat()
            self.logbook.append(
                {
                    "started": started.isoformat(),
                    "finished": finished.isoformat(),
                    "mode": "manual" if manual else "automatic",
                    "planned_minutes": minutes,
                    "actual_minutes": round((finished - started).total_seconds() / 60, 1),
                    "temperature": self.snapshot.calculation_temperature_c,
                    "effective_rain": self.snapshot.effective_rain_mm,
                    "forecast_rain": self.snapshot.forecast_rain_12h_mm,
                    "reason": self.snapshot.reason,
                }
            )
            await self._notify_user(
                "Wasserbetrieb beendet" if manual else "Bewässerung beendet",
                f"Der Lauf mit {minutes} Minuten Planzeit wurde beendet.",
            )
        except asyncio.CancelledError:
            raise
        finally:
            self.snapshot.running = False
            self.snapshot.manual = False
            self.snapshot.remaining_minutes = 0
            self.snapshot.status = self._idle_status()
            self._run_task = None
            self.snapshot.next_action = self._build_next_action()
            self.notify()
            await self._save()

    async def _countdown(self, minutes: int) -> None:
        for remaining in range(minutes, 0, -1):
            self.snapshot.remaining_minutes = remaining
            self.snapshot.next_action = self._build_next_action()
            self.notify()
            await asyncio.sleep(60)

    async def async_stop(self) -> None:
        async with self._operation_lock:
            was_running = self.snapshot.running
            task, self._run_task = self._run_task, None
            if task:
                task.cancel()
                try:
                    with suppress(asyncio.CancelledError):
                        await task
                except Exception:
                    # A failed save in the task's cleanup must not skip closing.
                    _LOGGER.exception("Fehler beim Beenden des Bewässerungslaufs")
            try:
                await self._close()
            except HomeAssistantError:
                self.snapshot.status = "stop_failed"
                self.snapshot.next_action = self._build_next_action()
                self.notify()
                await self._save()
                raise
            self.snapshot.running = False
            if was_running:
                self.snapshot.last_run = dt_util.now().isoformat()
            self.snapshot.manual = False
            self.snapshot.remaining_minutes = 0
            self.snapshot.status = "stopped" if self.watering_enabled else self._idle_status()
            self.snapshot.next_action = self._build_next_action()
            self.notify()
            await self._notify_user("Wasserbetrieb gestoppt", "Der Schließbefehl wurde an das Ventil gesendet.")
            await self._save()

    async def async_prepare_reconfigure(self) -> None:
        """Quiesce the old actuator before HA updates and reloads this entry."""
        self._reconfiguring = True
        try:
            state = self.hass.states.get(self.config[CONF_VALVE])
            if self.snapshot.running or self._run_task or (state and state.state in ("open", "opening")):
                await self.async_stop()
            else:
                await self._save()
        except Exception:
            self._reconfiguring = False
            self.snapshot.next_action = self._build_next_action()
            self.notify()
            raise

    async def async_set_watering_enabled(self, enabled: bool) -> None:
        """Persist the winter lock, stop watering, keep all calculations alive."""
        async with self._watering_setting_lock:
            self.settings["watering_enabled"] = enabled
            self.snapshot.next_action = self._build_next_action()
            self.notify()
            if not enabled:
                # Persist before waiting for an in-flight start or valve command.
                # Even a storage failure must not prevent the close attempt.
                try:
                    await self._save()
                finally:
                    await self.async_stop()
            else:
                await self._save()
            await self.async_refresh()

    async def async_set_setting(self, key: str, value: Any) -> None:
        if key == "watering_enabled":
            await self.async_set_watering_enabled(bool(value))
            return
        self.settings[key] = value
        await self.async_refresh()

    async def async_set_start_time(self, value: time) -> None:
        self.settings["start_time"] = value.replace(microsecond=0).isoformat()
        self._reschedule_daily_jobs()
        await self.async_refresh()

    async def async_set_skip_today(self, enabled: bool) -> None:
        self.skip_date = dt_util.now().date().isoformat() if enabled else None
        self.snapshot.next_action = self._build_next_action()
        self.notify()
        await self._save()
