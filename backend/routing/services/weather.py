"""Open-Meteo hourly forecast client (keyless).

Fetches wind / rain / snow for many points in as few calls as possible:
  * checkpoints are rounded to a ~1 km grid cell and de-duplicated,
  * unique cells are requested in bulk (comma-separated lat/lon),
  * results cached in-process for a short TTL to serve request bursts.

All values are normalised to the units the risk rules expect: wind in mph, rain
and snow in inches/hour. Snowfall is reported by Open-Meteo in cm, so we read the
response's own unit labels and convert rather than assuming.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone

import requests

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT = 20
CELL_DIGITS = 2           # ~1.1 km at the equator
CACHE_TTL_S = 600         # 10 minutes
_CHUNK = 100              # max unique cells per HTTP request

_cache: dict[tuple[float, float], tuple[float, "WeatherSeries"]] = {}


@dataclass
class WeatherSeries:
    times: list[datetime]          # tz-aware UTC
    wind_mph: list[float]
    rain_in: list[float]
    snow_in: list[float]

    def nearest(self, target: datetime) -> tuple[float, float, float]:
        """(wind_mph, rain_in, snow_in) at the hour closest to `target`."""
        if not self.times:
            return 0.0, 0.0, 0.0
        t = target.astimezone(timezone.utc)
        i = min(range(len(self.times)), key=lambda k: abs((self.times[k] - t).total_seconds()))
        return self.wind_mph[i], self.rain_in[i], self.snow_in[i]


def _cell(lat: float, lon: float) -> tuple[float, float]:
    return round(lat, CELL_DIGITS), round(lon, CELL_DIGITS)


def _to_inches(values: list[float | None], unit: str) -> list[float]:
    factor = {"inch": 1.0, "mm": 1 / 25.4, "cm": 1 / 2.54}.get(unit, 1.0)
    return [(v or 0.0) * factor for v in values]


def _parse(block: dict) -> WeatherSeries:
    hourly = block.get("hourly", {})
    units = block.get("hourly_units", {})
    times = [
        datetime.fromisoformat(t).replace(tzinfo=timezone.utc)
        for t in hourly.get("time", [])
    ]
    return WeatherSeries(
        times=times,
        wind_mph=[v or 0.0 for v in hourly.get("wind_speed_10m", [])],
        rain_in=_to_inches(hourly.get("rain", []), units.get("rain", "inch")),
        snow_in=_to_inches(hourly.get("snowfall", []), units.get("snowfall", "cm")),
    )


def fetch(points: list[tuple[float, float]], forecast_days: int = 3) -> dict[tuple[float, float], WeatherSeries]:
    """Return a cell -> WeatherSeries map covering every input point."""
    now = time.monotonic()
    wanted = {_cell(lat, lon) for lat, lon in points}

    result: dict[tuple[float, float], WeatherSeries] = {}
    missing: list[tuple[float, float]] = []
    for cell in wanted:
        hit = _cache.get(cell)
        if hit and now - hit[0] < CACHE_TTL_S:
            result[cell] = hit[1]
        else:
            missing.append(cell)

    for start in range(0, len(missing), _CHUNK):
        chunk = missing[start : start + _CHUNK]
        params = {
            "latitude": ",".join(f"{c[0]}" for c in chunk),
            "longitude": ",".join(f"{c[1]}" for c in chunk),
            "hourly": "wind_speed_10m,wind_gusts_10m,rain,snowfall",
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": "UTC",
            "forecast_days": forecast_days,
        }
        resp = requests.get(FORECAST_URL, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        payload = resp.json()
        blocks = payload if isinstance(payload, list) else [payload]
        for cell, block in zip(chunk, blocks):
            series = _parse(block)
            _cache[cell] = (now, series)
            result[cell] = series

    return result


def series_for(weather: dict[tuple[float, float], WeatherSeries], lat: float, lon: float) -> WeatherSeries:
    return weather[_cell(lat, lon)]
