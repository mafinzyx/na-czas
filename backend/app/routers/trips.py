"""CRUD for trips."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Place, Trip
from app.schemas import TripCreate, TripRead, TripUpdate

router = APIRouter(prefix="/api/trips", tags=["trips"])


def _get_or_404(db: Session, trip_id: int) -> Trip:
    trip = db.get(Trip, trip_id)
    if trip is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Trip not found")
    return trip


def _check_places_exist(db: Session, payload: TripCreate | TripUpdate) -> None:
    for place_id in (payload.origin_id, payload.destination_id):
        if db.get(Place, place_id) is None:
            raise HTTPException(422, f"Place {place_id} does not exist")


@router.get("", response_model=list[TripRead])
def list_trips(db: Session = Depends(get_db)):
    return db.scalars(select(Trip).order_by(Trip.arrive_by, Trip.title)).all()


@router.post("", response_model=TripRead, status_code=status.HTTP_201_CREATED)
def create_trip(payload: TripCreate, db: Session = Depends(get_db)):
    _check_places_exist(db, payload)
    trip = Trip(**payload.model_dump())
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


@router.get("/{trip_id}", response_model=TripRead)
def get_trip(trip_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, trip_id)


@router.put("/{trip_id}", response_model=TripRead)
def update_trip(trip_id: int, payload: TripUpdate, db: Session = Depends(get_db)):
    trip = _get_or_404(db, trip_id)
    _check_places_exist(db, payload)
    for field, value in payload.model_dump().items():
        setattr(trip, field, value)
    db.commit()
    db.refresh(trip)
    return trip


@router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trip(trip_id: int, db: Session = Depends(get_db)):
    db.delete(_get_or_404(db, trip_id))
    db.commit()
