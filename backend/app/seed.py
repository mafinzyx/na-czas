"""Demo data so that a freshly cloned project shows a meaningful plan right away."""

from datetime import date, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Place, Profile, Trip


def seed_demo_data(db: Session) -> None:
    """Fills an empty database with a sample week in Gdańsk. Does nothing otherwise."""
    if db.scalar(select(func.count()).select_from(Place)):
        return

    # Home sits on the Morena hill, about 50 m above the university, so the way
    # back is a real climb: a good case for the elevation-aware bike model.
    home = Place(name="Dom", address="Piecki-Migowo (Morena), Gdańsk", lat=54.3530, lon=18.5870)
    university = Place(
        name="Uczelnia", address="Politechnika Gdańska, Wrzeszcz", lat=54.3716, lon=18.6190, parking_cost_pln=8
    )
    office = Place(
        name="Praca", address="Olivia Business Centre, Oliwa", lat=54.4035, lon=18.5700, parking_cost_pln=15
    )
    gym = Place(name="Siłownia", address="Galeria Bałtycka, Wrzeszcz", lat=54.3826, lon=18.6003)
    db.add_all([home, university, office, gym])
    db.flush()  # assigns ids

    exam_day = date.today() + timedelta(days=2)
    db.add_all(
        [
            Profile(id=1),
            Trip(title="Zajęcia", origin_id=home.id, destination_id=university.id,
                 arrive_by=time(8, 15), importance="normal", weekdays=[0, 2]),
            Trip(title="Powrót z zajęć", origin_id=university.id, destination_id=home.id,
                 arrive_by=time(16, 30), importance="low", weekdays=[0, 2]),
            Trip(title="Praca", origin_id=home.id, destination_id=office.id,
                 arrive_by=time(9, 0), importance="high", weekdays=[1, 3, 4]),
            Trip(title="Siłownia", origin_id=home.id, destination_id=gym.id,
                 arrive_by=time(18, 30), importance="low", weekdays=[5]),
            Trip(title="Egzamin", origin_id=home.id, destination_id=university.id,
                 arrive_by=time(10, 0), importance="high", date=exam_day),
        ]
    )
    db.commit()
