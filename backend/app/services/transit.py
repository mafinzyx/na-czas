"""Real public-transport connections from Transitous.

Transitous (https://transitous.org) is a free, community-run router built on open
GTFS timetables. It needs no API key and answers with complete itineraries: which
line to take, where to board, change and get off, and the shape of every leg.

The service is best-effort, so `find_itineraries` returns None on any failure and
the planner then falls back to a rough estimate.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from app.config import get_settings
from app.services.geo import LatLon, decode_polyline, thin

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 10 * 60
MAX_ITINERARIES = 5  # different line combinations shown for one journey
ITINERARIES_PER_QUERY = 8
SHORT_WALK_SECONDS = 7 * 60  # walking limit to and from stops in the "nearest stop" search
WALK_PENALTY = 0.5  # a minute of walking counts as 1.5 minutes when ranking connections
TRANSFER_PENALTY_MIN = 5
MAX_POINTS_PER_LEG = 120

# Transitous mode -> the leg kind used by this app.
LEG_KINDS = {
    "WALK": "walk",
    "BUS": "bus",
    "COACH": "bus",
    "TRAM": "tram",
    "SUBWAY": "metro",
    "METRO": "metro",
    "FERRY": "ferry",
    "RAIL": "train",
    "REGIONAL_RAIL": "train",
    "REGIONAL_FAST_RAIL": "train",
    "SUBURBAN": "train",
    "LONG_DISTANCE": "train",
    "HIGHSPEED_RAIL": "train",
}
# Names Transitous gives to the two ends of the journey.
ENDPOINT_NAMES = {"START", "END"}


@dataclass(frozen=True)
class TransitLeg:
    kind: str  # walk | bus | tram | metro | train | ferry | transit
    line: str | None
    headsign: str | None
    color: str | None  # "#rrggbb" from the timetable, if the operator defines one
    from_name: str | None  # None for the journey's own start
    to_name: str | None
    depart: datetime
    arrive: datetime
    stops: int | None  # stops passed before getting off
    distance_km: float | None
    geometry: list[LatLon]

    @property
    def minutes(self) -> float:
        return (self.arrive - self.depart).total_seconds() / 60

    @property
    def is_ride(self) -> bool:
        return self.kind != "walk"


@dataclass(frozen=True)
class TransitItinerary:
    depart: datetime  # leaving the origin on foot
    arrive: datetime  # reaching the destination
    transfers: int
    legs: list[TransitLeg]

    @property
    def lines(self) -> tuple[str, ...]:
        """The lines taken, in order: what makes two connections "the same route"."""
        return tuple(leg.line or leg.kind for leg in self.legs if leg.is_ride)

    @property
    def walk_minutes(self) -> float:
        return sum(leg.minutes for leg in self.legs if not leg.is_ride)

    @property
    def inconvenience(self) -> float:
        """Rough ranking score in minutes: travel time, with walking and changes counted extra."""
        duration = (self.arrive - self.depart).total_seconds() / 60
        return duration + WALK_PENALTY * self.walk_minutes + TRANSFER_PENALTY_MIN * self.transfers


_cache: dict[tuple, tuple[float, list[TransitItinerary]]] = {}


def _to_local(iso_utc: str, zone: ZoneInfo) -> datetime:
    """The API answers in UTC; the app works with naive local time."""
    return datetime.fromisoformat(iso_utc.replace("Z", "+00:00")).astimezone(zone).replace(tzinfo=None)


def _stop_name(place: dict) -> str | None:
    name = place.get("name")
    return None if name in ENDPOINT_NAMES else name


def _parse_leg(raw: dict, zone: ZoneInfo) -> TransitLeg:
    kind = LEG_KINDS.get(raw["mode"], "transit")
    shape = raw.get("legGeometry") or {}
    geometry = decode_polyline(shape["points"], shape.get("precision", 5)) if shape.get("points") else []
    color = raw.get("routeColor")
    distance = raw.get("distance")

    return TransitLeg(
        kind=kind,
        line=raw.get("routeShortName") or raw.get("displayName"),
        headsign=raw.get("headsign"),
        color=f"#{color}" if color else None,
        from_name=_stop_name(raw["from"]),
        to_name=_stop_name(raw["to"]),
        depart=_to_local(raw["startTime"], zone),
        arrive=_to_local(raw["endTime"], zone),
        stops=len(raw.get("intermediateStops") or []) + 1 if kind != "walk" else None,
        distance_km=distance / 1000 if distance is not None else None,
        geometry=thin(geometry, MAX_POINTS_PER_LEG),
    )


def _parse(data: dict, zone: ZoneInfo) -> list[TransitItinerary]:
    itineraries = []
    for raw in data.get("itineraries", []):
        legs = [_parse_leg(leg, zone) for leg in raw["legs"]]
        if not any(leg.is_ride for leg in legs):
            continue  # a walk-only answer is covered by the walking option
        itineraries.append(
            TransitItinerary(
                depart=_to_local(raw["startTime"], zone),
                arrive=_to_local(raw["endTime"], zone),
                transfers=raw.get("transfers", 0),
                legs=legs,
            )
        )
    return itineraries


def find_itineraries(
    lat1: float, lon1: float, lat2: float, lon2: float, moment: datetime, arrive_by: bool
) -> list[TransitItinerary] | None:
    """Timetable connections around `moment` (naive local time).

    With arrive_by the connections arrive no later than `moment`; otherwise they
    depart no earlier. Returns None when the service cannot be reached.
    """
    settings = get_settings()
    if settings.offline:
        return None

    key = (round(lat1, 5), round(lon1, 5), round(lat2, 5), round(lon2, 5), moment, arrive_by)
    cached = _cache.get(key)
    if cached and time.monotonic() - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    zone = ZoneInfo(settings.timezone)
    base_params = {
        "fromPlace": f"{lat1},{lon1}",
        "toPlace": f"{lat2},{lon2}",
        "time": moment.replace(tzinfo=zone).isoformat(),
        "arriveBy": str(arrive_by).lower(),
        "numItineraries": ITINERARIES_PER_QUERY,
    }

    def fetch(extra: dict) -> list[TransitItinerary]:
        response = httpx.get(
            settings.transit_api_url,
            params={**base_params, **extra},
            headers={"User-Agent": settings.user_agent},
            timeout=settings.transit_timeout_seconds,
        )
        response.raise_for_status()
        return _parse(response.json(), zone)

    # The router only returns the fastest connections, and those often mean a long walk
    # to a direct line. A second search with a short walking limit brings in what a local
    # would also consider: the nearby stop, even if it costs a change.
    short_walk = {"maxPreTransitTime": SHORT_WALK_SECONDS, "maxPostTransitTime": SHORT_WALK_SECONDS}
    with ThreadPoolExecutor(max_workers=2) as pool:
        fastest = pool.submit(fetch, {})
        nearest = pool.submit(fetch, short_walk)
        try:
            candidates = fastest.result()
        except (httpx.HTTPError, KeyError, ValueError) as error:
            logger.warning("Transitous unavailable, public transport will be estimated: %s", error)
            return None
        try:
            candidates += nearest.result()
        except (httpx.HTTPError, KeyError, ValueError) as error:
            logger.warning("Short-walk transit search failed, showing the fastest connections only: %s", error)

    itineraries = select_varied(candidates, arrive_by)
    _cache[key] = (time.monotonic(), itineraries)
    return itineraries


def select_varied(candidates: list[TransitItinerary], arrive_by: bool) -> list[TransitItinerary]:
    """Picks a small, varied set of connections: different line combinations first.

    Showing five departures of the same bus hides the alternatives, so each combination
    of lines appears once (its departure closest to the requested time). The best
    combination also keeps one more departure, as a safer or later fallback.
    """
    closest_first = sorted(candidates, key=lambda i: i.depart, reverse=arrive_by)
    by_lines: dict[tuple, list[TransitItinerary]] = {}
    for itinerary in closest_first:
        departures = by_lines.setdefault(itinerary.lines, [])
        if all(itinerary.depart != other.depart for other in departures):
            departures.append(itinerary)

    ranked = sorted(by_lines.values(), key=lambda departures: departures[0].inconvenience)
    chosen = [departures[0] for departures in ranked[:MAX_ITINERARIES]]

    # Always include the connection with the least walking, even if it ranks low.
    least_walking = min(ranked, key=lambda departures: departures[0].walk_minutes, default=None)
    if least_walking and least_walking[0] not in chosen:
        chosen[-1] = least_walking[0]

    if ranked and len(ranked[0]) > 1:
        chosen.append(ranked[0][1])
    return chosen
