"""Request and response models of the REST API."""

import datetime as dt
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Importance = Literal["low", "normal", "high"]
Priority = Literal["balanced", "cheapest", "fastest"]
Language = Literal["en", "pl"]
# "arrive": be there by the given time. "depart": leave at the given time.
TimeMode = Literal["arrive", "depart"]
LegKind = Literal["walk", "bus", "tram", "metro", "train", "ferry", "transit", "car", "taxi", "bike", "scooter"]
LatLon = tuple[float, float]


class Mode(str, Enum):
    CAR = "car"
    TAXI = "taxi"
    TRANSIT = "transit"
    BIKE = "bike"
    SCOOTER = "scooter"
    WALK = "walk"


# --- Profile -----------------------------------------------------------------


class ProfileBase(BaseModel):
    has_car: bool = True
    fuel_consumption_l_per_100km: float = Field(7.0, gt=0, le=40)
    fuel_price_pln_per_l: float = Field(6.5, gt=0, le=50)
    has_bike: bool = True
    bike_is_electric: bool = False
    has_scooter: bool = False
    has_transit_pass: bool = False
    transit_ticket_price_pln: float = Field(4.8, ge=0, le=100)
    transit_transfer_ticket_price_pln: float = Field(6.0, ge=0, le=100)
    taxi_base_fare_pln: float = Field(8.0, ge=0, le=100)
    taxi_per_km_pln: float = Field(3.0, ge=0, le=50)
    priority: Priority = "balanced"


class ProfileUpdate(ProfileBase):
    pass


class ProfileRead(ProfileBase):
    model_config = ConfigDict(from_attributes=True)


# --- Places ------------------------------------------------------------------


class PlaceBase(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    address: str | None = Field(None, max_length=255)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    parking_cost_pln: float = Field(0.0, ge=0, le=500)


class PlaceCreate(PlaceBase):
    pass


class PlaceUpdate(PlaceBase):
    pass


class PlaceRead(PlaceBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class GeocodeResult(BaseModel):
    display_name: str
    lat: float
    lon: float


# --- Trips -------------------------------------------------------------------


class TripBase(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    origin_id: int
    destination_id: int
    arrive_by: dt.time
    importance: Importance = "normal"
    weekdays: list[int] = Field(default_factory=list)
    date: dt.date | None = None

    @model_validator(mode="after")
    def check_consistency(self) -> "TripBase":
        if self.origin_id == self.destination_id:
            raise ValueError("origin and destination must be different places")
        if any(day < 0 or day > 6 for day in self.weekdays):
            raise ValueError("weekdays must be numbers from 0 (Monday) to 6 (Sunday)")
        if bool(self.weekdays) == (self.date is not None):
            raise ValueError("a trip needs either weekdays (recurring) or a date (one-off)")
        self.weekdays = sorted(set(self.weekdays))
        return self


class TripCreate(TripBase):
    pass


class TripUpdate(TripBase):
    pass


class TripRead(TripBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    origin: PlaceRead
    destination: PlaceRead


# --- Journey plan ------------------------------------------------------------


class WeatherInfo(BaseModel):
    temperature_c: float
    precipitation_mm: float
    precipitation_probability: int | None = None
    wind_kmh: float

    @property
    def is_wet(self) -> bool:
        return self.precipitation_mm >= 0.3 or (self.precipitation_probability or 0) >= 60

    @property
    def is_heavy_rain(self) -> bool:
        return self.precipitation_mm >= 2.0

    @property
    def is_freezing(self) -> bool:
        return self.temperature_c <= 0

    @property
    def is_cold(self) -> bool:
        return self.temperature_c <= 5

    @property
    def is_windy(self) -> bool:
        return self.wind_kmh >= 35


class Leg(BaseModel):
    """One continuous part of a route: a walk, a ride on one line, a drive."""

    kind: LegKind
    line: str | None = None
    headsign: str | None = None
    color: str | None = None
    from_name: str | None = None  # None means the journey's own origin
    to_name: str | None = None  # None means the journey's own destination
    depart: datetime | None = None  # only for timetable legs
    arrive: datetime | None = None
    minutes: int
    distance_km: float | None = None
    stops: int | None = None
    geometry: list[LatLon] = Field(default_factory=list)


class RouteOption(BaseModel):
    """One concrete way of making the journey, e.g. "bus 168" or "bike, route 2"."""

    id: str
    mode: Mode
    label: str | None  # line numbers for public transport, e.g. "127 → 6"
    estimated: bool  # public transport without a timetable (service unreachable)
    depart_at: datetime  # when to leave
    arrive_at: datetime  # arrival on a normal day
    arrive_worst: datetime  # arrival on a bad day (roughly the 95th percentile)
    typical_minutes: int
    worst_minutes: int
    buffer_minutes: int  # spare time before the deadline on a normal day ("arrive" mode)
    cost_pln: float
    distance_km: float | None
    ascent_m: int | None  # total climb, bike only
    transfers: int | None  # public transport only
    reliability: Literal["stable", "variable", "unpredictable"]
    too_late: bool  # the departure time has already passed
    risky: bool  # fixed departure that leaves too little margin for this trip's importance
    score: float  # generalised cost in PLN, lower is better
    tags: list[str]
    warnings: list[str]
    legs: list[Leg]
    elevation_profile: list[tuple[float, float]] = Field(default_factory=list)  # (km, metres)


class BackupPlan(BaseModel):
    option_id: str
    mode: Mode
    label: str | None
    board_stop: str | None  # where to board, for public transport
    depart_at: datetime
    # The last moment at which the backup is still possible ("point of no return").
    decide_by: datetime
    # True when the backup has to leave noticeably earlier than the recommended option.
    commit_early: bool


class Point(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class JourneyRequest(BaseModel):
    origin: Point
    destination: Point
    time: datetime
    time_mode: TimeMode = "arrive"
    importance: Importance = "normal"
    parking_cost_pln: float = Field(0.0, ge=0, le=500)
    now: datetime | None = None  # the client's local time; defaults to server time

    @model_validator(mode="after")
    def check_points_differ(self) -> "JourneyRequest":
        if (self.origin.lat, self.origin.lon) == (self.destination.lat, self.destination.lon):
            raise ValueError("origin and destination must be different")
        return self


class JourneyPlan(BaseModel):
    origin: Point
    destination: Point
    time: datetime
    time_mode: TimeMode
    importance: Importance
    distance_km: float  # by road
    transit_source: Literal["timetable", "estimate"]
    congestion: float  # road traffic multiplier around the travel time, 1.0 = free flow
    weather: WeatherInfo | None
    status: Literal["ok", "late", "past"]
    late_by_minutes: int | None  # only when status is "late": delay if leaving right now
    recommended: str  # id of the best option
    backup: BackupPlan | None
    options: list[RouteOption]  # best first


class TripPlan(JourneyPlan):
    """A journey plan for one occurrence of a saved trip."""

    trip_id: int
    title: str


class DayPlan(BaseModel):
    date: dt.date
    trips: list[TripPlan]


class WeekSummary(BaseModel):
    trips_count: int
    recommended_cost_pln: float
    car_only_cost_pln: float | None  # None when the user has no car
    travel_minutes: int
    commit_early_count: int


class WeekPlan(BaseModel):
    start: dt.date
    days: list[DayPlan]
    summary: WeekSummary


class TrafficPoint(BaseModel):
    hour: float
    factor: float


class AdviceRequest(BaseModel):
    start: dt.date | None = None
    now: datetime | None = None
    language: Language = "en"


class Advice(BaseModel):
    source: Literal["ai", "rules"]
    text: str
