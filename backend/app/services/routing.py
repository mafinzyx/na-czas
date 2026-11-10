"""Routes for the modes you steer yourself: car, bike and walking.

All providers are free and need no API key:

* car      - OSRM demo server (distance, free-flow time, geometry)
* walking  - OSRM "foot" profile hosted by FOSSGIS
* bike     - BRouter, which also returns alternatives and the elevation of every point

Each function falls back to an estimate from the straight-line distance when its
provider is unreachable, so the planner always gets an answer.
"""

import logging
from dataclasses import dataclass
from typing import Literal

import httpx

from app.config import get_settings
from app.services.geo import LatLon, haversine_km

logger = logging.getLogger(__name__)

OSRM_CAR_URL = "https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
OSRM_FOOT_URL = "https://routing.openstreetmap.de/routed-foot/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
BROUTER_URL = "https://brouter.de/brouter"

# Fallback assumptions: roads are ~35 % longer than the straight line,
# and an empty city road averages 32 km/h door to door.
DETOUR_FACTOR = 1.35
FREE_FLOW_SPEED_KMH = 32.0
MAX_BIKE_ALTERNATIVES = 3
# Two bike routes whose lengths differ by less than this are treated as the same route.
MIN_ALTERNATIVE_DIFFERENCE_KM = 0.15


@dataclass(frozen=True)
class Route:
    distance_km: float
    drive_minutes: float  # car only: driving time without traffic
    geometry: list[LatLon]
    source: Literal["provider", "estimate"]


@dataclass(frozen=True)
class BikeRoute:
    distance_km: float
    ascent_m: float | None  # total climb; None when elevation is unknown
    geometry: list[LatLon]
    elevations_m: list[float]  # one value per geometry point, empty when unknown


Coordinates = tuple[float, float, float, float]
_car_cache: dict[Coordinates, Route] = {}
_walk_cache: dict[Coordinates, Route] = {}
_bike_cache: dict[Coordinates, list[BikeRoute]] = {}


def _key(lat1: float, lon1: float, lat2: float, lon2: float) -> Coordinates:
    return (round(lat1, 5), round(lon1, 5), round(lat2, 5), round(lon2, 5))


def _get(url: str, params: dict) -> dict:
    settings = get_settings()
    response = httpx.get(
        url, params=params, timeout=settings.http_timeout_seconds, headers={"User-Agent": settings.user_agent}
    )
    response.raise_for_status()
    return response.json()


def estimate_route(lat1: float, lon1: float, lat2: float, lon2: float) -> Route:
    distance = haversine_km(lat1, lon1, lat2, lon2) * DETOUR_FACTOR
    return Route(distance, distance / FREE_FLOW_SPEED_KMH * 60, [(lat1, lon1), (lat2, lon2)], "estimate")


def _osrm_route(url_template: str, lat1: float, lon1: float, lat2: float, lon2: float) -> Route:
    url = url_template.format(lon1=lon1, lat1=lat1, lon2=lon2, lat2=lat2)
    best = _get(url, {"overview": "full", "geometries": "geojson"})["routes"][0]
    geometry = [(lat, lon) for lon, lat in best["geometry"]["coordinates"]]
    return Route(best["distance"] / 1000, best["duration"] / 60, geometry, "provider")


def _cached_osrm(cache: dict[Coordinates, Route], url: str, lat1: float, lon1: float, lat2: float, lon2: float) -> Route:
    key = _key(lat1, lon1, lat2, lon2)
    if key in cache:
        return cache[key]
    if get_settings().offline:
        return estimate_route(lat1, lon1, lat2, lon2)
    try:
        route = _osrm_route(url, lat1, lon1, lat2, lon2)
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as error:
        # Not cached on purpose: the next request retries the real service.
        logger.warning("Routing service unavailable, using a straight-line estimate: %s", error)
        return estimate_route(lat1, lon1, lat2, lon2)
    cache[key] = route
    return route


def car_route(lat1: float, lon1: float, lat2: float, lon2: float) -> Route:
    return _cached_osrm(_car_cache, OSRM_CAR_URL, lat1, lon1, lat2, lon2)


def walk_route(lat1: float, lon1: float, lat2: float, lon2: float) -> Route:
    return _cached_osrm(_walk_cache, OSRM_FOOT_URL, lat1, lon1, lat2, lon2)


def _brouter_route(lat1: float, lon1: float, lat2: float, lon2: float, alternative: int) -> BikeRoute:
    data = _get(
        BROUTER_URL,
        {
            "lonlats": f"{lon1},{lat1}|{lon2},{lat2}",
            "profile": "trekking",
            "alternativeidx": alternative,
            "format": "geojson",
        },
    )
    feature = data["features"][0]
    coordinates = feature["geometry"]["coordinates"]  # [lon, lat, elevation]
    has_elevation = all(len(point) >= 3 for point in coordinates)
    return BikeRoute(
        distance_km=float(feature["properties"]["track-length"]) / 1000,
        ascent_m=float(feature["properties"]["filtered ascend"]) if has_elevation else None,
        geometry=[(point[1], point[0]) for point in coordinates],
        elevations_m=[point[2] for point in coordinates] if has_elevation else [],
    )


def bike_routes(lat1: float, lon1: float, lat2: float, lon2: float) -> list[BikeRoute]:
    """Up to three noticeably different bike routes, best first. Empty if none could be found."""
    key = _key(lat1, lon1, lat2, lon2)
    if key in _bike_cache:
        return _bike_cache[key]
    if get_settings().offline:
        return []

    routes: list[BikeRoute] = []
    for alternative in range(MAX_BIKE_ALTERNATIVES):
        try:
            candidate = _brouter_route(lat1, lon1, lat2, lon2, alternative)
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as error:
            logger.warning("BRouter alternative %s unavailable: %s", alternative, error)
            break
        is_new = all(abs(candidate.distance_km - r.distance_km) >= MIN_ALTERNATIVE_DIFFERENCE_KM for r in routes)
        if is_new:
            routes.append(candidate)

    if routes:
        _bike_cache[key] = routes
    return routes
