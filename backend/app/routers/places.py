"""CRUD for saved places, plus address search."""

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Place, Trip
from app.schemas import GeocodeResult, PlaceCreate, PlaceRead, PlaceUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/places", tags=["places"])

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


def _get_or_404(db: Session, place_id: int) -> Place:
    place = db.get(Place, place_id)
    if place is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Place not found")
    return place


@router.get("", response_model=list[PlaceRead])
def list_places(db: Session = Depends(get_db)):
    return db.scalars(select(Place).order_by(Place.name)).all()


@router.post("", response_model=PlaceRead, status_code=status.HTTP_201_CREATED)
def create_place(payload: PlaceCreate, db: Session = Depends(get_db)):
    place = Place(**payload.model_dump())
    db.add(place)
    db.commit()
    return place


# Declared before "/{place_id}" so that "search" is not parsed as an id.
@router.get("/search", response_model=list[GeocodeResult])
def search_address(q: str = Query(min_length=3, max_length=120)):
    """Address lookup through OpenStreetMap Nominatim (free, no API key)."""
    if get_settings().offline:
        return []
    try:
        response = httpx.get(
            NOMINATIM_URL,
            params={"q": q, "format": "jsonv2", "limit": 5, "countrycodes": get_settings().geocode_countries},
            headers={"User-Agent": get_settings().user_agent},
            timeout=get_settings().http_timeout_seconds,
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        logger.warning("Nominatim unavailable: %s", error)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Address search is unavailable") from error

    return [
        GeocodeResult(display_name=item["display_name"], lat=float(item["lat"]), lon=float(item["lon"]))
        for item in response.json()
    ]


@router.get("/{place_id}", response_model=PlaceRead)
def get_place(place_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, place_id)


@router.put("/{place_id}", response_model=PlaceRead)
def update_place(place_id: int, payload: PlaceUpdate, db: Session = Depends(get_db)):
    place = _get_or_404(db, place_id)
    for field, value in payload.model_dump().items():
        setattr(place, field, value)
    db.commit()
    return place


@router.delete("/{place_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_place(place_id: int, db: Session = Depends(get_db)):
    place = _get_or_404(db, place_id)
    in_use = db.scalar(
        select(Trip.id).where(or_(Trip.origin_id == place_id, Trip.destination_id == place_id)).limit(1)
    )
    if in_use is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Place is used by a trip")
    db.delete(place)
    db.commit()
