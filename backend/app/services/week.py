"""Builds the 7-day plan from the saved trips."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Profile, Trip
from app.schemas import DayPlan, JourneyRequest, Point, ProfileRead, TripPlan, WeekPlan, WeekSummary
from app.services.journey import plan_journey

DAYS_IN_PLAN = 7


@dataclass(frozen=True)
class _Occurrence:
    """One saved trip on one concrete day, detached from the database session."""

    trip_id: int
    title: str
    day: date
    request: JourneyRequest


def get_profile(db: Session) -> Profile:
    """The single profile row, created with defaults on first use."""
    profile = db.get(Profile, 1)
    if profile is None:
        profile = Profile(id=1)
        db.add(profile)
        db.commit()
    return profile


def _occurrences(trips: list[Trip], start: date) -> list[_Occurrence]:
    occurrences = []
    for offset in range(DAYS_IN_PLAN):
        day = start + timedelta(days=offset)
        for trip in trips:
            if not trip.occurs_on(day):
                continue
            origin, destination = trip.origin, trip.destination
            request = JourneyRequest(
                origin=Point(name=origin.name, lat=origin.lat, lon=origin.lon),
                destination=Point(name=destination.name, lat=destination.lat, lon=destination.lon),
                time=datetime.combine(day, trip.arrive_by),
                time_mode="arrive",
                importance=trip.importance,
                parking_cost_pln=destination.parking_cost_pln,
            )
            occurrences.append(_Occurrence(trip.id, trip.title, day, request))
    return occurrences


def build_week_plan(db: Session, start: date, now: datetime) -> WeekPlan:
    profile = ProfileRead.model_validate(get_profile(db))
    occurrences = _occurrences(list(db.scalars(select(Trip)).all()), start)

    def plan(occurrence: _Occurrence) -> tuple[TripPlan, float]:
        journey, car_cost = plan_journey(occurrence.request, profile, now, include_geometry=False)
        trip_plan = TripPlan(trip_id=occurrence.trip_id, title=occurrence.title, **journey.model_dump())
        return trip_plan, car_cost

    # Each occurrence needs its own timetable lookup, so they are planned in parallel.
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(plan, occurrences))

    days = {start + timedelta(days=offset): [] for offset in range(DAYS_IN_PLAN)}
    recommended_cost = car_only_cost = 0.0
    travel_minutes = commit_early_count = 0

    for occurrence, (trip_plan, car_cost) in zip(occurrences, results):
        days[occurrence.day].append(trip_plan)
        chosen = next(o for o in trip_plan.options if o.id == trip_plan.recommended)
        recommended_cost += chosen.cost_pln
        car_only_cost += car_cost
        travel_minutes += chosen.typical_minutes
        if trip_plan.backup and trip_plan.backup.commit_early:
            commit_early_count += 1

    summary = WeekSummary(
        trips_count=len(occurrences),
        recommended_cost_pln=round(recommended_cost, 2),
        car_only_cost_pln=round(car_only_cost, 2) if profile.has_car else None,
        travel_minutes=travel_minutes,
        commit_early_count=commit_early_count,
    )
    return WeekPlan(
        start=start,
        days=[DayPlan(date=day, trips=sorted(trips, key=lambda t: t.time)) for day, trips in days.items()],
        summary=summary,
    )
