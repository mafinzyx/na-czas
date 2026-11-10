"""Unit tests of the planning core (pure functions, no I/O)."""

from datetime import datetime, timedelta

from app.schemas import Mode, ProfileRead, WeatherInfo
from app.services.planner import FAMILY, TripContext, plan_trip
from app.services.routing import BikeRoute, Route
from app.services.traffic import congestion_factor, worst_case_factor
from app.services.transit import TransitItinerary, TransitLeg

MONDAY_RUSH = datetime(2026, 11, 9, 8, 15)
SUNDAY_MORNING = datetime(2026, 11, 8, 8, 15)
LONG_BEFORE = datetime(2026, 11, 1, 0, 0)

DRY = WeatherInfo(temperature_c=15, precipitation_mm=0, precipitation_probability=5, wind_kmh=8)
RAIN = WeatherInfo(temperature_c=8, precipitation_mm=3.0, precipitation_probability=90, wind_kmh=15)

LINE = [(54.35, 18.59), (54.37, 18.62)]
FLAT_BIKE = BikeRoute(distance_km=5.0, ascent_m=5, geometry=LINE, elevations_m=[10, 12])
HILLY_BIKE = BikeRoute(distance_km=5.0, ascent_m=90, geometry=LINE, elevations_m=[10, 100])


def make_ctx(**overrides) -> TripContext:
    defaults = dict(
        time=MONDAY_RUSH,
        time_mode="arrive",
        importance="normal",
        profile=ProfileRead(),
        car_route=Route(distance_km=5.0, drive_minutes=11.0, geometry=LINE, source="estimate"),
        bike_routes=[FLAT_BIKE],
        walk_route=None,
        transit=None,
        parking_cost_pln=0.0,
        weather=DRY,
        now=LONG_BEFORE,
    )
    return TripContext(**{**defaults, **overrides})


def ride(kind: str, line: str, depart: datetime, minutes: int, from_name: str, to_name: str) -> TransitLeg:
    return TransitLeg(kind, line, None, None, from_name, to_name, depart, depart + timedelta(minutes=minutes), 4, None, LINE)


def walk(depart: datetime, minutes: int) -> TransitLeg:
    return TransitLeg("walk", None, None, None, None, None, depart, depart + timedelta(minutes=minutes), None, 0.4, LINE)


def direct_bus(depart: datetime, line: str = "168") -> TransitItinerary:
    """5 min walk, 10 min bus, 5 min walk."""
    legs = [
        walk(depart, 5),
        ride("bus", line, depart + timedelta(minutes=5), 10, "Stop A", "Stop B"),
        walk(depart + timedelta(minutes=15), 5),
    ]
    return TransitItinerary(depart, depart + timedelta(minutes=20), 0, legs)


def by_mode(decision, mode: Mode):
    return next(o for o in decision.options if o.mode == mode)


def recommended(decision):
    return next(o for o in decision.options if o.id == decision.recommended)


def test_rush_hour_is_slower_than_weekend():
    assert congestion_factor(MONDAY_RUSH) > 1.5
    assert congestion_factor(SUNDAY_MORNING) == 1.0
    assert worst_case_factor(1.75) > worst_case_factor(1.0)


def test_car_takes_longer_and_is_less_predictable_in_rush_hour():
    rush = by_mode(plan_trip(make_ctx()), Mode.CAR)
    calm = by_mode(plan_trip(make_ctx(time=SUNDAY_MORNING)), Mode.CAR)

    assert rush.typical_minutes > calm.typical_minutes
    assert rush.buffer_minutes > calm.buffer_minutes
    assert "rush_hour" in rush.warnings
    assert "rush_hour" not in calm.warnings


def test_bike_wins_a_short_dry_trip_but_not_in_heavy_rain():
    assert recommended(plan_trip(make_ctx())).mode is Mode.BIKE

    rainy = plan_trip(make_ctx(weather=RAIN))
    assert recommended(rainy).mode is not Mode.BIKE
    assert "heavy_rain" in by_mode(rainy, Mode.BIKE).warnings


def test_hills_slow_a_regular_bike_much_more_than_an_electric_one():
    flat = by_mode(plan_trip(make_ctx()), Mode.BIKE)
    hilly = by_mode(plan_trip(make_ctx(bike_routes=[HILLY_BIKE])), Mode.BIKE)
    electric = by_mode(
        plan_trip(make_ctx(bike_routes=[HILLY_BIKE], profile=ProfileRead(bike_is_electric=True))), Mode.BIKE
    )

    assert hilly.typical_minutes >= flat.typical_minutes + 5
    assert "hilly" in hilly.warnings
    assert electric.typical_minutes < flat.typical_minutes
    assert "hilly" not in electric.warnings
    assert electric.score < hilly.score


def test_every_bike_alternative_becomes_its_own_option():
    decision = plan_trip(make_ctx(bike_routes=[FLAT_BIKE, HILLY_BIKE]))
    bikes = [o for o in decision.options if o.mode is Mode.BIKE]

    assert {o.id for o in bikes} == {"bike-0", "bike-1"}
    assert {o.ascent_m for o in bikes} == {5, 90}
    assert all(o.elevation_profile for o in bikes)


def test_car_cost_is_fuel_plus_parking():
    car = by_mode(plan_trip(make_ctx(parking_cost_pln=10)), Mode.CAR)
    # 5 km * 7 l/100 km * 6.50 zl/l = 2.275 zl of fuel, plus 10 zl of parking
    assert abs(car.cost_pln - 12.275) < 0.01
    assert "parking_fee" in car.warnings


def test_important_trips_leave_earlier():
    normal = by_mode(plan_trip(make_ctx()), Mode.CAR)
    important = by_mode(plan_trip(make_ctx(importance="high")), Mode.CAR)
    assert important.depart_at < normal.depart_at


def test_modes_the_user_does_not_own_are_not_offered():
    profile = ProfileRead(has_car=False, has_bike=False, has_scooter=False)
    modes = {o.mode for o in plan_trip(make_ctx(profile=profile)).options}
    assert modes == {Mode.TRANSIT, Mode.TAXI}


def test_walking_is_offered_only_for_short_distances():
    near = Route(distance_km=2.0, drive_minutes=5.0, geometry=LINE, source="estimate")
    assert Mode.WALK in {o.mode for o in plan_trip(make_ctx(car_route=near)).options}
    assert Mode.WALK not in {o.mode for o in plan_trip(make_ctx()).options}


def test_without_a_timetable_public_transport_is_estimated():
    transit = by_mode(plan_trip(make_ctx()), Mode.TRANSIT)
    assert transit.estimated
    assert transit.legs == []


def test_timetable_connection_keeps_its_fixed_departure_and_legs():
    bus = direct_bus(MONDAY_RUSH - timedelta(minutes=35))
    transit = by_mode(plan_trip(make_ctx(transit=[bus])), Mode.TRANSIT)

    assert not transit.estimated
    assert transit.label == "168"
    assert transit.depart_at == bus.depart
    assert transit.arrive_at == bus.arrive
    assert transit.buffer_minutes == 15
    assert [leg.kind for leg in transit.legs] == ["walk", "bus", "walk"]
    assert not transit.risky


def test_connection_arriving_at_the_last_minute_is_risky_for_an_important_trip():
    last_minute = direct_bus(MONDAY_RUSH - timedelta(minutes=21))
    earlier = direct_bus(MONDAY_RUSH - timedelta(minutes=35), line="199")
    decision = plan_trip(make_ctx(transit=[last_minute, earlier], importance="high"))

    options = {o.label: o for o in decision.options if o.mode is Mode.TRANSIT}
    assert options["168"].risky
    assert not options["199"].risky
    assert recommended(decision).label != "168"


def test_tight_transfer_is_flagged():
    start = MONDAY_RUSH - timedelta(minutes=45)
    legs = [
        walk(start, 5),
        ride("bus", "127", start + timedelta(minutes=5), 10, "Stop A", "Stop B"),
        ride("tram", "6", start + timedelta(minutes=16), 5, "Stop B", "Stop C"),  # 1 minute to change
        walk(start + timedelta(minutes=21), 4),
    ]
    change = TransitItinerary(start, start + timedelta(minutes=25), 1, legs)
    transit = by_mode(plan_trip(make_ctx(transit=[change])), Mode.TRANSIT)

    assert transit.label == "127 → 6"
    assert transit.transfers == 1
    assert "tight_transfer" in transit.warnings
    assert transit.worst_minutes >= transit.typical_minutes + 10


def test_ticket_price_depends_on_transfers_and_pass():
    start = MONDAY_RUSH - timedelta(minutes=40)
    direct = direct_bus(start)
    with_change = TransitItinerary(direct.depart, direct.arrive, 1, direct.legs)

    assert by_mode(plan_trip(make_ctx(transit=[direct])), Mode.TRANSIT).cost_pln == 4.8
    assert by_mode(plan_trip(make_ctx(transit=[with_change])), Mode.TRANSIT).cost_pln == 6.0
    with_pass = make_ctx(transit=[with_change], profile=ProfileRead(has_transit_pass=True))
    assert by_mode(plan_trip(with_pass), Mode.TRANSIT).cost_pln == 0


def test_backup_comes_from_a_different_family():
    decision = plan_trip(make_ctx())
    primary = recommended(decision)

    assert decision.backup is not None
    assert FAMILY[decision.backup.mode] != FAMILY[primary.mode]
    assert decision.backup.decide_by <= primary.depart_at


def test_transit_backup_names_the_line_and_stop_and_sets_the_decision_deadline():
    # With "fastest" priority a road mode wins; the bus backup leaves much earlier.
    bus = direct_bus(MONDAY_RUSH - timedelta(minutes=50))
    profile = ProfileRead(priority="fastest", has_bike=False)
    decision = plan_trip(make_ctx(transit=[bus], profile=profile, weather=RAIN))
    primary = recommended(decision)
    backup = decision.backup

    assert FAMILY[primary.mode] == "road"
    assert (backup.mode, backup.label, backup.board_stop) == (Mode.TRANSIT, "168", "Stop A")
    assert backup.commit_early
    assert backup.decide_by == bus.depart < primary.depart_at


def test_options_whose_departure_has_passed_are_skipped():
    bus = direct_bus(MONDAY_RUSH - timedelta(minutes=40))
    decision = plan_trip(make_ctx(transit=[bus], now=MONDAY_RUSH - timedelta(minutes=30), weather=RAIN))

    assert decision.status == "ok"
    assert not recommended(decision).too_late
    assert by_mode(decision, Mode.TRANSIT).too_late


def test_when_nothing_is_on_time_the_fastest_startable_mode_is_suggested():
    bus = direct_bus(MONDAY_RUSH - timedelta(minutes=40))
    decision = plan_trip(make_ctx(transit=[bus], now=MONDAY_RUSH - timedelta(minutes=5)))

    assert decision.status == "late"
    assert recommended(decision).mode is not Mode.TRANSIT
    assert decision.late_by_minutes >= 1
    assert decision.backup is None


def test_depart_mode_starts_at_the_given_time_and_has_no_deadline():
    start = MONDAY_RUSH
    bus = direct_bus(start + timedelta(minutes=7))
    decision = plan_trip(make_ctx(time_mode="depart", transit=[bus]))

    car = by_mode(decision, Mode.CAR)
    transit = by_mode(decision, Mode.TRANSIT)
    assert car.depart_at == start
    assert car.arrive_at == start + timedelta(minutes=car.typical_minutes)
    assert transit.depart_at == bus.depart
    assert decision.status == "ok"
    assert decision.backup is None
    assert not any(o.too_late or o.risky for o in decision.options)
