"""Plans one journey: gathers routes, timetable and weather, then runs the planner.

This is the only place that talks to the outside world for a journey. The data
sources are independent, so they are queried in parallel.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from app.schemas import JourneyPlan, JourneyRequest, ProfileRead
from app.services import routing, transit, weather
from app.services.geo import haversine_km
from app.services.planner import MAX_WALK_KM, TripContext, car_cost_pln, plan_trip

# Shared by all requests; the work is I/O-bound (waiting for HTTP responses).
_executor = ThreadPoolExecutor(max_workers=16, thread_name_prefix="journey")


def plan_journey(
    request: JourneyRequest, profile: ProfileRead, now: datetime, include_geometry: bool = True
) -> tuple[JourneyPlan, float]:
    """The plan for one journey, plus what the same journey would cost by car."""
    origin, destination = request.origin, request.destination
    ends = (origin.lat, origin.lon, destination.lat, destination.lon)
    wants_bike_route = profile.has_bike or profile.has_scooter
    walkable = haversine_km(*ends) <= MAX_WALK_KM

    car = _executor.submit(routing.car_route, *ends)
    bikes = _executor.submit(routing.bike_routes, *ends) if wants_bike_route else None
    walk = _executor.submit(routing.walk_route, *ends) if walkable else None
    timetable = _executor.submit(
        transit.find_itineraries, *ends, request.time, request.time_mode == "arrive"
    )
    forecast = _executor.submit(weather.get_weather, origin.lat, origin.lon, request.time)

    ctx = TripContext(
        time=request.time,
        time_mode=request.time_mode,
        importance=request.importance,
        profile=profile,
        car_route=car.result(),
        bike_routes=bikes.result() if bikes else [],
        walk_route=walk.result() if walk else None,
        transit=timetable.result(),
        parking_cost_pln=request.parking_cost_pln,
        weather=forecast.result(),
        now=now,
    )
    decision = plan_trip(ctx)

    options = decision.options
    if not include_geometry:
        # Overviews (the week) only need the numbers; shapes are fetched on demand.
        options = [
            option.model_copy(
                update={
                    "legs": [leg.model_copy(update={"geometry": []}) for leg in option.legs],
                    "elevation_profile": [],
                }
            )
            for option in options
        ]

    plan = JourneyPlan(
        origin=origin,
        destination=destination,
        time=request.time,
        time_mode=request.time_mode,
        importance=request.importance,
        distance_km=round(ctx.car_route.distance_km, 1),
        transit_source="estimate" if ctx.transit is None else "timetable",
        congestion=decision.congestion,
        weather=ctx.weather,
        status=decision.status,
        late_by_minutes=decision.late_by_minutes,
        recommended=decision.recommended,
        backup=decision.backup,
        options=options,
    )
    return plan, car_cost_pln(ctx)
