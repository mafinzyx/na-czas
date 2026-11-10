"""The calculated plan: read-only resources derived from trips, places and the profile."""

from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import Advice, AdviceRequest, JourneyPlan, JourneyRequest, ProfileRead, TrafficPoint, WeekPlan
from app.services import advisor, traffic
from app.services.journey import plan_journey
from app.services.week import build_week_plan, get_profile

router = APIRouter(prefix="/api/plan", tags=["plan"])


@router.post("/journey", response_model=JourneyPlan)
def journey(payload: JourneyRequest, db: Session = Depends(get_db)):
    """Compares every way of getting from A to B at the given time, with route shapes for the map.

    POST because the request is a structured query, not because anything is stored.
    """
    profile = ProfileRead.model_validate(get_profile(db))
    plan, _ = plan_journey(payload, profile, payload.now or datetime.now())
    return plan


@router.get("/week", response_model=WeekPlan)
def week_plan(
    start: date | None = Query(None, description="First day of the 7-day window. Defaults to today."),
    now: datetime | None = Query(None, description="The client's local time. Defaults to server time."),
    db: Session = Depends(get_db),
):
    now = now or datetime.now()
    return build_week_plan(db, start or now.date(), now)


@router.post("/advice", response_model=Advice)
def advice(payload: AdviceRequest, db: Session = Depends(get_db)):
    """Plain-language briefing for the week: AI when configured, rule-based otherwise."""
    now = payload.now or datetime.now()
    plan = build_week_plan(db, payload.start or now.date(), now)
    return advisor.weekly_advice(plan, payload.language)


@router.get("/traffic", response_model=list[TrafficPoint])
def traffic_curve(day: date = Query(description="The date whose congestion curve is requested.")):
    return [TrafficPoint(hour=hour, factor=factor) for hour, factor in traffic.daily_curve(day.weekday())]
