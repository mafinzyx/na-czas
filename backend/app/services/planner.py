"""The planning core: compares concrete ways of making one journey.

An *option* is one concrete route: "drive", "bus 168 at 07:34", "bike, route 2".
For each option the planner estimates a *typical* door-to-door time and a *bad day*
time (roughly the 95th percentile), then derives:

* when to leave so that you are on time with the confidence the trip's importance
  asks for (75 % / 90 % / 97 %). Timetable connections have fixed departures, so they
  are instead marked *risky* when they leave too little margin;
* a *score*: money plus time (converted to money) plus effort and weather discomfort,
  so an unreliable or strenuous option pays for it;
* a *backup* from a different "failure family" and the moment until which that backup
  is still possible. This is what prevents the "five minutes before leaving I found
  out the car is not an option, and the bus is already gone" situation.

Everything here is a pure function of its arguments (no I/O), which keeps it testable.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.schemas import (
    BackupPlan,
    Importance,
    Leg,
    Mode,
    ProfileRead,
    RouteOption,
    TimeMode,
    WeatherInfo,
)
from app.services.geo import haversine_km, thin
from app.services.routing import BikeRoute, Route
from app.services.traffic import RUSH_HOUR_THRESHOLD, congestion_factor, worst_case_factor
from app.services.transit import TransitItinerary

# --- Model assumptions -------------------------------------------------------

BIKE_SPEED_KMH = 16.0
EBIKE_SPEED_KMH = 21.0
SCOOTER_SPEED_KMH = 18.0
WALK_SPEED_KMH = 4.8

MAX_WALK_KM = 4.0
MAX_SCOOTER_KM = 10.0
MAX_BIKE_KM = 15.0

# Climbing: extra minutes per metre of ascent (100 m of climb costs a regular bike 6 min).
CLIMB_MIN_PER_M = 0.06
EBIKE_CLIMB_MIN_PER_M = 0.015
# Climbing as discomfort: "felt" extra minutes per metre of ascent.
CLIMB_DISCOMFORT_PER_M = 0.25
EBIKE_CLIMB_DISCOMFORT_PER_M = 0.03
HILLY_ASCENT_M = 35  # from here a regular bike gets a "hilly" warning

CAR_OVERHEAD_MIN = 6  # walking to the car + finding a parking spot
CAR_OVERHEAD_WORST_MIN = 10
TAXI_PICKUP_MIN = 5
TAXI_PICKUP_WORST_MIN = 12
RAIN_TRAFFIC_FACTOR = 1.1  # more people drive when it rains
BAD_WEATHER_SLOWDOWN = 1.15  # cycling in rain or strong wind

# Timetable connections: how late each ride can run on a bad day.
BUS_TRAFFIC_SENSITIVITY = 0.6  # bus lanes shield buses from part of the congestion
BUS_MIN_DELAY_MIN = 2.0
RAIL_DELAY_MIN = 1.5  # trams, metro and trains do not sit in traffic
TIGHT_TRANSFER_MIN = 3  # less than this between two rides and the change may fail
MISSED_TRANSFER_DELAY_MIN = 10  # typical wait for the next departure
LONG_WALK_MIN = 20  # total walking within one connection

# Public transport without a timetable (fallback when the service is unreachable).
EST_ACCESS_MIN = 10  # walking to and from the stops
EST_WAIT_MIN = 5
EST_WAIT_WORST_MIN = 14
EST_RIDE_FACTOR = 1.6  # stops make the ride longer than a direct drive

# On-time confidence per importance, expressed as a z-score of the normal distribution.
Z_SCORE: dict[str, float] = {"low": 0.674, "normal": 1.282, "high": 1.881}  # 75 %, 90 %, 97 %
Z_WORST_CASE = 1.645  # the "bad day" duration is treated as the 95th percentile
# With no deadline ("depart" mode) uncertainty still counts, as half of the possible delay.
DEPART_RISK_WEIGHT = 0.5

# How much one minute is worth in PLN for each user priority.
VALUE_OF_TIME_PLN_PER_MIN: dict[str, float] = {"balanced": 0.6, "cheapest": 0.2, "fastest": 2.0}

# Modes in one family fail for the same reason, so a backup must come from another one.
FAMILY: dict[Mode, str] = {
    Mode.CAR: "road",
    Mode.TAXI: "road",
    Mode.TRANSIT: "transit",
    Mode.BIKE: "active",
    Mode.SCOOTER: "active",
    Mode.WALK: "active",
}
# Extra weight of one minute of physical effort compared with one minute of sitting.
EFFORT_WEIGHT: dict[Mode, float] = {Mode.WALK: 0.5, Mode.BIKE: 0.3, Mode.SCOOTER: 0.15}
EBIKE_EFFORT_WEIGHT = 0.1
TWO_WHEELERS = {Mode.BIKE, Mode.SCOOTER}

# A backup counts as "leaving earlier" only if the difference is worth acting on.
COMMIT_EARLY_MIN_GAP = timedelta(minutes=5)
MAX_PROFILE_POINTS = 60


@dataclass(frozen=True)
class TripContext:
    """Everything the planner needs to know about one journey."""

    time: datetime  # the deadline ("arrive") or the departure ("depart")
    time_mode: TimeMode
    importance: Importance
    profile: ProfileRead
    car_route: Route
    bike_routes: list[BikeRoute]
    walk_route: Route | None
    transit: list[TransitItinerary] | None  # None: no timetable, estimate instead
    parking_cost_pln: float
    weather: WeatherInfo | None
    now: datetime


@dataclass(frozen=True)
class TripDecision:
    options: list[RouteOption]  # best first
    recommended: str
    backup: BackupPlan | None
    congestion: float
    status: str  # ok | late | past
    late_by_minutes: int | None = None


@dataclass(frozen=True)
class _Timing:
    depart: datetime
    time_cost: float  # minutes that count towards the score
    buffer: int


# --- Shared pieces -----------------------------------------------------------


def road_congestion(ctx: TripContext) -> float:
    """Traffic multiplier around the middle of the drive.

    The drive time depends on traffic, and the traffic depends on when you drive,
    so the estimate is refined a few times until both agree.
    """
    direction = -1 if ctx.time_mode == "arrive" else 1
    drive = ctx.car_route.drive_minutes
    factor = 1.0
    for _ in range(3):
        midpoint = ctx.time + direction * timedelta(minutes=drive / 2)
        factor = congestion_factor(midpoint)
        if ctx.weather and ctx.weather.is_wet:
            factor *= RAIN_TRAFFIC_FACTOR
        drive = ctx.car_route.drive_minutes * factor
    return factor


def _flexible_timing(ctx: TripContext, typical: float, worst: float) -> _Timing:
    """Departure for a mode you can start whenever you like."""
    if ctx.time_mode == "depart":
        return _Timing(ctx.time, typical + DEPART_RISK_WEIGHT * (worst - typical), 0)

    # Treat the duration as roughly normal: typical = mean, worst = 95th percentile.
    sigma = (worst - typical) / Z_WORST_CASE
    budget = math.ceil(typical + Z_SCORE[ctx.importance] * sigma)
    return _Timing(ctx.time - timedelta(minutes=budget), budget, budget - round(typical))


def _weather_weight(mode: Mode, weather: WeatherInfo | None) -> float:
    """Extra discomfort of one minute spent outside in the current weather."""
    if weather is None:
        return 0.0
    weight = 0.0
    if weather.is_heavy_rain:
        weight += 2.0
    elif weather.is_wet:
        weight += 1.0
    if weather.is_freezing:
        weight += 0.8
    elif weather.is_cold:
        weight += 0.5
    if mode in TWO_WHEELERS and weather.is_windy:
        weight += 0.4
    return weight


def _weather_warnings(mode: Mode, weather: WeatherInfo | None) -> list[str]:
    if weather is None:
        return []
    warnings = []
    if weather.is_heavy_rain:
        warnings.append("heavy_rain")
    elif weather.is_wet:
        warnings.append("rain")
    if weather.is_freezing:
        warnings.append("freezing")
    elif weather.is_cold:
        warnings.append("cold")
    if mode in TWO_WHEELERS and weather.is_windy:
        warnings.append("strong_wind")
    return warnings


def _reliability(spread_minutes: float) -> str:
    if spread_minutes <= 5:
        return "stable"
    if spread_minutes <= 12:
        return "variable"
    return "unpredictable"


def _option(
    ctx: TripContext,
    *,
    option_id: str,
    mode: Mode,
    typical: float,
    worst: float,
    timing: _Timing,
    cost: float,
    discomfort: float,
    legs: list[Leg],
    warnings: list[str],
    label: str | None = None,
    distance_km: float | None = None,
    ascent_m: float | None = None,
    transfers: int | None = None,
    risky: bool = False,
    estimated: bool = False,
    elevation_profile: list[tuple[float, float]] | None = None,
) -> RouteOption:
    score = cost + VALUE_OF_TIME_PLN_PER_MIN[ctx.profile.priority] * (timing.time_cost + discomfort)
    return RouteOption(
        id=option_id,
        mode=mode,
        label=label,
        estimated=estimated,
        depart_at=timing.depart,
        arrive_at=timing.depart + timedelta(minutes=round(typical)),
        arrive_worst=timing.depart + timedelta(minutes=round(worst)),
        typical_minutes=round(typical),
        worst_minutes=round(worst),
        buffer_minutes=timing.buffer,
        cost_pln=round(cost, 2),
        distance_km=round(distance_km, 1) if distance_km is not None else None,
        ascent_m=round(ascent_m) if ascent_m is not None else None,
        transfers=transfers,
        reliability=_reliability(worst - typical),
        too_late=ctx.time_mode == "arrive" and timing.depart < ctx.now,
        risky=risky,
        score=round(score, 2),
        tags=[],
        warnings=warnings,
        legs=legs,
        elevation_profile=elevation_profile or [],
    )


# --- Road: car and taxi ------------------------------------------------------


def car_cost_pln(ctx: TripContext) -> float:
    profile = ctx.profile
    fuel = ctx.car_route.distance_km * profile.fuel_consumption_l_per_100km / 100 * profile.fuel_price_pln_per_l
    return fuel + ctx.parking_cost_pln


def _road_option(ctx: TripContext, mode: Mode, congestion: float) -> RouteOption:
    route = ctx.car_route
    worst_congestion = worst_case_factor(congestion)
    if mode is Mode.CAR:
        typical = route.drive_minutes * congestion + CAR_OVERHEAD_MIN
        worst = route.drive_minutes * worst_congestion + CAR_OVERHEAD_WORST_MIN
        cost = car_cost_pln(ctx)
    else:
        typical = route.drive_minutes * congestion + TAXI_PICKUP_MIN
        worst = route.drive_minutes * worst_congestion + TAXI_PICKUP_WORST_MIN
        cost = ctx.profile.taxi_base_fare_pln + route.distance_km * ctx.profile.taxi_per_km_pln

    warnings = []
    if congestion >= RUSH_HOUR_THRESHOLD:
        warnings.append("rush_hour")
    if mode is Mode.CAR and ctx.parking_cost_pln > 0:
        warnings.append("parking_fee")

    leg = Leg(kind=mode.value, minutes=round(typical), distance_km=round(route.distance_km, 1), geometry=route.geometry)
    return _option(
        ctx,
        option_id=mode.value,
        mode=mode,
        typical=typical,
        worst=worst,
        timing=_flexible_timing(ctx, typical, worst),
        cost=cost,
        discomfort=0.0,
        legs=[leg],
        warnings=warnings,
        distance_km=route.distance_km,
    )


# --- Active: bike, scooter, walking -----------------------------------------


def _elevation_profile(route: BikeRoute) -> list[tuple[float, float]]:
    """(distance from start in km, elevation in m) samples for the UI chart."""
    if not route.elevations_m:
        return []
    profile, travelled = [], 0.0
    previous = route.geometry[0]
    for point, elevation in zip(route.geometry, route.elevations_m):
        travelled += haversine_km(*previous, *point)
        profile.append((round(travelled, 2), round(elevation, 1)))
        previous = point
    return thin(profile, MAX_PROFILE_POINTS)


def _bike_option(ctx: TripContext, route: BikeRoute, index: int) -> RouteOption:
    electric = ctx.profile.bike_is_electric
    ascent = route.ascent_m or 0.0
    speed = EBIKE_SPEED_KMH if electric else BIKE_SPEED_KMH
    climb_minutes = ascent * (EBIKE_CLIMB_MIN_PER_M if electric else CLIMB_MIN_PER_M)

    typical = route.distance_km / speed * 60 + climb_minutes + 3
    if ctx.weather and (ctx.weather.is_wet or ctx.weather.is_windy):
        typical *= BAD_WEATHER_SLOWDOWN
    worst = typical * 1.1 + 2

    effort = EBIKE_EFFORT_WEIGHT if electric else EFFORT_WEIGHT[Mode.BIKE]
    climb_discomfort = ascent * (EBIKE_CLIMB_DISCOMFORT_PER_M if electric else CLIMB_DISCOMFORT_PER_M)
    discomfort = typical * (effort + _weather_weight(Mode.BIKE, ctx.weather)) + climb_discomfort

    warnings = _weather_warnings(Mode.BIKE, ctx.weather)
    if not electric and ascent >= HILLY_ASCENT_M:
        warnings.append("hilly")

    leg = Leg(kind="bike", minutes=round(typical), distance_km=round(route.distance_km, 1), geometry=route.geometry)
    return _option(
        ctx,
        option_id=f"bike-{index}",
        mode=Mode.BIKE,
        typical=typical,
        worst=worst,
        timing=_flexible_timing(ctx, typical, worst),
        cost=0.0,
        discomfort=discomfort,
        legs=[leg],
        warnings=warnings,
        distance_km=route.distance_km,
        ascent_m=route.ascent_m,
        elevation_profile=_elevation_profile(route),
    )


def _simple_active_option(ctx: TripContext, mode: Mode, distance_km: float, geometry: list) -> RouteOption:
    """Scooter or walking: speed-based, no elevation model."""
    if mode is Mode.WALK:
        typical = distance_km / WALK_SPEED_KMH * 60
        worst = typical * 1.07 + 1
    else:
        typical = distance_km / SCOOTER_SPEED_KMH * 60 + 3
        if ctx.weather and (ctx.weather.is_wet or ctx.weather.is_windy):
            typical *= BAD_WEATHER_SLOWDOWN
        worst = typical * 1.1 + 2

    leg = Leg(kind=mode.value, minutes=round(typical), distance_km=round(distance_km, 1), geometry=geometry)
    return _option(
        ctx,
        option_id=mode.value,
        mode=mode,
        typical=typical,
        worst=worst,
        timing=_flexible_timing(ctx, typical, worst),
        cost=0.0,
        discomfort=typical * (EFFORT_WEIGHT[mode] + _weather_weight(mode, ctx.weather)),
        legs=[leg],
        warnings=_weather_warnings(mode, ctx.weather),
        distance_km=distance_km,
    )


def _active_options(ctx: TripContext) -> list[RouteOption]:
    options: list[RouteOption] = []
    car = ctx.car_route
    # Without a dedicated bike route (provider down) the road route is the best guess.
    bike_routes = ctx.bike_routes or [BikeRoute(car.distance_km, None, car.geometry, [])]

    if ctx.profile.has_bike:
        options += [
            _bike_option(ctx, route, index)
            for index, route in enumerate(bike_routes)
            if route.distance_km <= MAX_BIKE_KM
        ]
    if ctx.profile.has_scooter and bike_routes[0].distance_km <= MAX_SCOOTER_KM:
        options.append(_simple_active_option(ctx, Mode.SCOOTER, bike_routes[0].distance_km, bike_routes[0].geometry))

    walk = ctx.walk_route or car
    if walk.distance_km <= MAX_WALK_KM:
        options.append(_simple_active_option(ctx, Mode.WALK, walk.distance_km, walk.geometry))
    return options


# --- Public transport --------------------------------------------------------


def _transit_cost(ctx: TripContext, transfers: int) -> float:
    profile = ctx.profile
    if profile.has_transit_pass:
        return 0.0
    return profile.transit_transfer_ticket_price_pln if transfers > 0 else profile.transit_ticket_price_pln


def _transit_delay_risk(itinerary: TransitItinerary, congestion: float) -> tuple[float, bool]:
    """(minutes a bad day can add, whether any change is tight)."""
    extra_congestion = worst_case_factor(congestion) - congestion
    risk = 0.0
    tight = False
    previous_ride_end: datetime | None = None
    walk_since_ride = 0.0

    for leg in itinerary.legs:
        if not leg.is_ride:
            walk_since_ride += leg.minutes
            continue
        if leg.kind == "bus":
            risk += max(BUS_MIN_DELAY_MIN, leg.minutes * BUS_TRAFFIC_SENSITIVITY * extra_congestion)
        else:
            risk += RAIL_DELAY_MIN
        if previous_ride_end is not None:
            spare = (leg.depart - previous_ride_end).total_seconds() / 60 - walk_since_ride
            if spare < TIGHT_TRANSFER_MIN:
                tight = True
                risk += MISSED_TRANSFER_DELAY_MIN
        previous_ride_end = leg.arrive
        walk_since_ride = 0.0
    return risk, tight


def _timetable_option(ctx: TripContext, itinerary: TransitItinerary, index: int, congestion: float) -> RouteOption:
    typical = (itinerary.arrive - itinerary.depart).total_seconds() / 60
    risk, tight_transfer = _transit_delay_risk(itinerary, congestion)
    worst = typical + risk

    if ctx.time_mode == "arrive":
        # The departure is fixed by the timetable, so the buffer is whatever is left.
        spare = (ctx.time - itinerary.arrive).total_seconds() / 60
        needed = Z_SCORE[ctx.importance] * risk / Z_WORST_CASE
        risky = spare < needed
        timing = _Timing(itinerary.depart, (ctx.time - itinerary.depart).total_seconds() / 60, round(spare))
    else:
        # Waiting for the departure is part of the journey as well.
        waiting = (itinerary.depart - ctx.time).total_seconds() / 60
        risky = False
        timing = _Timing(itinerary.depart, waiting + typical + DEPART_RISK_WEIGHT * risk, 0)

    walk_minutes = sum(leg.minutes for leg in itinerary.legs if not leg.is_ride)
    discomfort = walk_minutes * (EFFORT_WEIGHT[Mode.WALK] + _weather_weight(Mode.WALK, ctx.weather))

    warnings = []
    if tight_transfer:
        warnings.append("tight_transfer")
    if walk_minutes >= LONG_WALK_MIN:
        warnings.append("long_walk")
    if ctx.weather and ctx.weather.is_wet:
        warnings.append("heavy_rain" if ctx.weather.is_heavy_rain else "rain")

    legs = [
        Leg(
            kind=leg.kind,
            line=leg.line,
            headsign=leg.headsign,
            color=leg.color,
            from_name=leg.from_name,
            to_name=leg.to_name,
            depart=leg.depart,
            arrive=leg.arrive,
            minutes=round(leg.minutes),
            distance_km=round(leg.distance_km, 2) if leg.distance_km is not None else None,
            stops=leg.stops,
            geometry=leg.geometry,
        )
        for leg in itinerary.legs
    ]
    lines = [leg.line or leg.kind for leg in itinerary.legs if leg.is_ride]
    return _option(
        ctx,
        option_id=f"transit-{index}",
        mode=Mode.TRANSIT,
        label=" → ".join(lines),
        typical=typical,
        worst=worst,
        timing=timing,
        cost=_transit_cost(ctx, itinerary.transfers),
        discomfort=discomfort,
        legs=legs,
        warnings=warnings,
        transfers=itinerary.transfers,
        risky=risky,
    )


def _estimated_transit_option(ctx: TripContext, congestion: float) -> RouteOption:
    """Public transport when no timetable is available: a single rough estimate."""
    ride = ctx.car_route.drive_minutes * EST_RIDE_FACTOR
    typical_factor = 1 + BUS_TRAFFIC_SENSITIVITY * (congestion - 1)
    worst_factor = 1 + BUS_TRAFFIC_SENSITIVITY * (worst_case_factor(congestion) - 1)
    typical = ride * typical_factor + EST_ACCESS_MIN + EST_WAIT_MIN
    worst = ride * worst_factor + EST_ACCESS_MIN + EST_WAIT_WORST_MIN

    exposed = EST_ACCESS_MIN + EST_WAIT_MIN
    return _option(
        ctx,
        option_id="transit-0",
        mode=Mode.TRANSIT,
        typical=typical,
        worst=worst,
        timing=_flexible_timing(ctx, typical, worst),
        cost=_transit_cost(ctx, transfers=0),
        discomfort=exposed * _weather_weight(Mode.WALK, ctx.weather),
        legs=[],
        warnings=[],
        estimated=True,
    )


def _transit_options(ctx: TripContext, congestion: float) -> list[RouteOption]:
    if ctx.transit is None:
        return [_estimated_transit_option(ctx, congestion)]
    return [_timetable_option(ctx, itinerary, i, congestion) for i, itinerary in enumerate(ctx.transit)]


# --- Decision ----------------------------------------------------------------


def build_options(ctx: TripContext, congestion: float) -> list[RouteOption]:
    options = [_road_option(ctx, Mode.TAXI, congestion)]
    if ctx.profile.has_car:
        options.append(_road_option(ctx, Mode.CAR, congestion))
    options += _active_options(ctx)
    options += _transit_options(ctx, congestion)
    # Usable options first, then by score.
    return sorted(options, key=lambda o: (o.too_late, o.risky, o.score))


def _add_tags(options: list[RouteOption]) -> None:
    """One holder per tag, so the list does not fill up with identical badges."""
    usable = [o for o in options if not o.too_late] or options
    min(usable, key=lambda o: o.typical_minutes).tags.append("fastest")
    min(usable, key=lambda o: (o.cost_pln, o.score)).tags.append("cheapest")
    min(usable, key=lambda o: (o.worst_minutes - o.typical_minutes, o.score)).tags.append("most_reliable")


def _board_stop(option: RouteOption) -> str | None:
    return next((leg.from_name for leg in option.legs if leg.kind != "walk" and leg.from_name), None)


def choose_backup(primary: RouteOption, options: list[RouteOption]) -> BackupPlan | None:
    """Best alternative that does not share the primary's point of failure."""
    candidates = [
        o for o in options if FAMILY[o.mode] != FAMILY[primary.mode] and not o.too_late and not o.risky
    ]
    if not candidates:
        return None

    backup = min(candidates, key=lambda o: o.score)
    return BackupPlan(
        option_id=backup.id,
        mode=backup.mode,
        label=backup.label,
        board_stop=_board_stop(backup),
        depart_at=backup.depart_at,
        decide_by=min(primary.depart_at, backup.depart_at),
        commit_early=primary.depart_at - backup.depart_at >= COMMIT_EARLY_MIN_GAP,
    )


def plan_trip(ctx: TripContext) -> TripDecision:
    congestion = road_congestion(ctx)
    options = build_options(ctx, congestion)
    _add_tags(options)

    best = options[0]  # the sort order already prefers usable options
    rounded_congestion = round(congestion, 2)

    if ctx.time_mode == "depart":
        return TripDecision(options, best.id, None, rounded_congestion, "ok")
    if ctx.time < ctx.now:
        return TripDecision(options, best.id, None, rounded_congestion, "past")
    if not best.too_late:
        return TripDecision(options, best.id, choose_backup(best, options), rounded_congestion, "ok")

    # Every safe departure has passed: minimise the delay with a mode that can start right now.
    startable = [o for o in options if o.mode is not Mode.TRANSIT or o.estimated]
    fastest = min(startable, key=lambda o: o.typical_minutes)
    arrival_if_leaving_now = ctx.now + timedelta(minutes=fastest.typical_minutes)
    late_by = max(1, round((arrival_if_leaving_now - ctx.time).total_seconds() / 60))
    return TripDecision(options, fastest.id, None, rounded_congestion, "late", late_by)
