from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any

@dataclass(slots=True)
class IrrigationSnapshot:
    status: str = "initializing"
    reason: str = "Noch nicht berechnet"
    data_quality: str = "unknown"
    running: bool = False
    manual: bool = False
    remaining_minutes: int = 0
    effective_rain_mm: float = 0.0
    forecast_rain_12h_mm: float = 0.0
    measured_max_yesterday_c: float | None = None
    forecast_max_today_c: float | None = None
    calculation_temperature_c: float | None = None
    dry_days: int = 0
    need_percent: int = 0
    runtime_minutes: int = 0
    last_run: str | None = None
    next_possible: str | None = None
    next_action: str = "Wird ermittelt"
    prepared_at: str | None = None
    planned_start: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
