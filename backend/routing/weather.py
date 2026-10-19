"""Open-Meteo hourly forecasts, normalized to mph and inches per hour."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

NEAREST_HOUR_SECONDS = 45 * 60


@dataclass(frozen=True)
class HourlySeries:
    timezone: str
    times: tuple[datetime, ...]
    wind_mph: tuple[float | None, ...]
    rain_in_hr: tuple[float | None, ...]
    snow_in_hr: tuple[float | None, ...]

    def reading_at(
        self, instant: datetime
    ) -> tuple[float | None, float | None, float | None] | None:
        if not self.times:
            return None
        aware = instant if instant.tzinfo else instant.replace(tzinfo=ZoneInfo("UTC"))
        nearest = min(
            range(len(self.times)),
            key=lambda index: abs((self.times[index] - aware).total_seconds()),
        )
        if abs((self.times[nearest] - aware).total_seconds()) > NEAREST_HOUR_SECONDS:
            return None
        return (
            self.wind_mph[nearest],
            self.rain_in_hr[nearest],
            self.snow_in_hr[nearest],
        )


def parse_open_meteo(payload: dict) -> HourlySeries:
    units = payload.get("hourly_units") or {}
    hourly = payload.get("hourly") or {}
    timezone_name = payload.get("timezone") or "UTC"
    try:
        zone = ZoneInfo(timezone_name)
    except Exception:
        zone = ZoneInfo("UTC")
        timezone_name = "UTC"

    times = []
    for stamp in hourly.get("time") or []:
        parsed = datetime.fromisoformat(stamp)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=zone)
        times.append(parsed)

    wind_unit = str(units.get("wind_speed_10m") or "mp/h")
    rain_unit = str(units.get("rain") or "mm")
    snow_unit = str(units.get("snowfall") or "cm")
    winds = [_convert_speed(value, wind_unit) for value in hourly.get("wind_speed_10m") or []]
    rains = [_convert_length(value, rain_unit) for value in hourly.get("rain") or []]
    snows = [_convert_length(value, snow_unit) for value in hourly.get("snowfall") or []]
    count = len(times)
    return HourlySeries(
        timezone=timezone_name,
        times=tuple(times),
        wind_mph=tuple(_fit(winds, count)),
        rain_in_hr=tuple(_fit(rains, count)),
        snow_in_hr=tuple(_fit(snows, count)),
    )


def _fit(values: list[float | None], count: int) -> list[float | None]:
    padded = list(values[:count])
    if len(padded) < count:
        padded.extend([None] * (count - len(padded)))
    return padded


def _convert_speed(value: float | None, unit: str) -> float | None:
    if value is None:
        return None
    normalized = unit.lower().replace(" ", "")
    if normalized in {"mp/h", "mph"}:
        return float(value)
    if normalized in {"km/h", "kmh"}:
        return float(value) * 0.621371
    if normalized in {"m/s", "ms"}:
        return float(value) * 2.236936
    if normalized in {"kn", "kt"}:
        return float(value) * 1.150779
    raise ValueError(f"Unknown wind unit {unit!r}")


def _convert_length(value: float | None, unit: str) -> float | None:
    """Convert an hourly amount to inches. Open-Meteo snowfall is often centimeters."""
    if value is None:
        return None
    normalized = unit.lower()
    if normalized in {"inch", "in"}:
        return float(value)
    if normalized == "mm":
        return float(value) / 25.4
    if normalized == "cm":
        return float(value) / 2.54
    raise ValueError(f"Unknown precipitation unit {unit!r}")


def hours_after(start: datetime, count: int) -> list[datetime]:
    return [start + timedelta(hours=offset) for offset in range(count)]
