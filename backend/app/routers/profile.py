"""The user's transport profile (single resource)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ProfileRead, ProfileUpdate
from app.services.week import get_profile

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=ProfileRead)
def read_profile(db: Session = Depends(get_db)):
    return get_profile(db)


@router.put("", response_model=ProfileRead)
def update_profile(payload: ProfileUpdate, db: Session = Depends(get_db)):
    profile = get_profile(db)
    for field, value in payload.model_dump().items():
        setattr(profile, field, value)
    db.commit()
    return profile
