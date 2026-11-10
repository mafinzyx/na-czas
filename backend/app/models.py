"""Database tables."""

import datetime as dt

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Profile(Base):
    """What the user owns and pays. The app is single-user, so there is exactly one row."""

    __tablename__ = "profile"

    id: Mapped[int] = mapped_column(primary_key=True)

    has_car: Mapped[bool] = mapped_column(default=True)
    fuel_consumption_l_per_100km: Mapped[float] = mapped_column(default=7.0)
    fuel_price_pln_per_l: Mapped[float] = mapped_column(default=6.5)

    has_bike: Mapped[bool] = mapped_column(default=True)
    bike_is_electric: Mapped[bool] = mapped_column(default=False)
    has_scooter: Mapped[bool] = mapped_column(default=False)

    has_transit_pass: Mapped[bool] = mapped_column(default=False)
    transit_ticket_price_pln: Mapped[float] = mapped_column(default=4.8)
    # Time-based ticket needed when the journey includes a change.
    transit_transfer_ticket_price_pln: Mapped[float] = mapped_column(default=6.0)

    taxi_base_fare_pln: Mapped[float] = mapped_column(default=8.0)
    taxi_per_km_pln: Mapped[float] = mapped_column(default=3.0)

    # balanced | cheapest | fastest
    priority: Mapped[str] = mapped_column(String(16), default="balanced")


class Place(Base):
    __tablename__ = "places"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    address: Mapped[str | None] = mapped_column(String(255), default=None)
    lat: Mapped[float]
    lon: Mapped[float]
    # What parking costs when you arrive here by car.
    parking_cost_pln: Mapped[float] = mapped_column(default=0.0)


class Trip(Base):
    """A journey with a fixed arrival time, either weekly-recurring or on a single date."""

    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(80))
    origin_id: Mapped[int] = mapped_column(ForeignKey("places.id"))
    destination_id: Mapped[int] = mapped_column(ForeignKey("places.id"))
    arrive_by: Mapped[dt.time]
    # low | normal | high
    importance: Mapped[str] = mapped_column(String(16), default="normal")
    # Recurring trips: weekdays as 0 (Monday) .. 6 (Sunday). Empty for one-off trips.
    weekdays: Mapped[list[int]] = mapped_column(JSON, default=list)
    # One-off trips: the single date. None for recurring trips.
    date: Mapped[dt.date | None] = mapped_column(default=None)

    origin: Mapped[Place] = relationship(foreign_keys=[origin_id], lazy="joined")
    destination: Mapped[Place] = relationship(foreign_keys=[destination_id], lazy="joined")

    def occurs_on(self, day: dt.date) -> bool:
        if self.date is not None:
            return self.date == day
        return day.weekday() in self.weekdays
