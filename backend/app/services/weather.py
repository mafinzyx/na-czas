"""Hourly weather forecast from Open-Meteo (free, no API key)."""

import logging
import time
from datetime import datetime

import httpx

from app.config import get_settings
from app.schemas import WeatherInfo

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
CACHE_TTL_SECONDS = 30 * 60

# One forecast covers a whole city: the cache key is the location rounded to ~10 km.
_cache: dict[tuple[float, float], tuple[float, dict[str, WeatherInfo]]] = {}


def _fetch_forecast(lat: float, lon: float) -> dict[str, WeatherInfo]:
    response = httpx.get(
        OPEN_METEO_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,precipitation,precipitation_probability,wind_speed_10m",
            "forecast_days": 16,
            "past_days": 1,
            "timezone": "auto",  # hours come back in the location's local time
        },
        timeout=get_settings().http_timeout_seconds,
    )
    response.raise_for_status()
    hourly = response.json()["hourly"]

    forecast: dict[str, WeatherInfo] = {}
    for i, hour in enumerate(hourly["time"]):
        if hourly["temperature_2m"][i] is None:
            continue
        forecast[hour] = WeatherInfo(
            temperature_c=hourly["temperature_2m"][i],
            precipitation_mm=hourly["precipitation"][i] or 0.0,
            precipitation_probability=hourly["precipitation_probability"][i],
            wind_kmh=hourly["wind_speed_10m"][i] or 0.0,
        )
    return forecast


def get_weather(lat: float, lon: float, moment: datetime) -> WeatherInfo | None:
    """Forecast for the hour containing `moment`, or None if it is unknown.

    None is a normal outcome (date beyond the forecast range, service down, offline
    mode); the planner then simply ignores weather.
    """
    if get_settings().offline:
        return None

    key = (round(lat, 1), round(lon, 1))
    cached = _cache.get(key)
    if cached is None or time.monotonic() - cached[0] > CACHE_TTL_SECONDS:
        try:
            cached = (time.monotonic(), _fetch_forecast(*key))
        except (httpx.HTTPError, KeyError, ValueError) as error:
            logger.warning("Open-Meteo unavailable, planning without weather: %s", error)
            return None
        _cache[key] = cached

    return cached[1].get(moment.strftime("%Y-%m-%dT%H:00"))
