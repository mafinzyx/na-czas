"""Road congestion model.

No free, key-less API offers *predicted* traffic, so congestion is modelled as a
multiplier of the free-flow driving time that depends on the weekday and the time
of day. 1.0 means an empty road; 1.75 means the drive takes 75 % longer.

The curve is the only place that knows about rush hours, so swapping it for a real
provider (TomTom, Google Routes) later means replacing `congestion_factor` only.
"""

from datetime import datetime

# (hour of day, multiplier) anchor points; values in between are interpolated linearly.
_WEEKDAY_CURVE = [
    (0.0, 1.0),
    (5.5, 1.0),
    (6.5, 1.15),
    (7.5, 1.55),
    (8.25, 1.75),  # morning peak
    (9.25, 1.45),
    (10.5, 1.15),
    (13.0, 1.2),
    (14.5, 1.35),
    (16.0, 1.75),  # afternoon peak
    (17.25, 1.7),
    (18.5, 1.3),
    (20.0, 1.05),
    (24.0, 1.0),
]
_WEEKEND_CURVE = [
    (0.0, 1.0),
    (9.0, 1.0),
    (12.0, 1.15),
    (15.0, 1.2),
    (18.0, 1.1),
    (21.0, 1.0),
    (24.0, 1.0),
]

RUSH_HOUR_THRESHOLD = 1.4


def _curve_for(weekday: int) -> list[tuple[float, float]]:
    return _WEEKEND_CURVE if weekday >= 5 else _WEEKDAY_CURVE


def _interpolate(curve: list[tuple[float, float]], hour: float) -> float:
    for (h0, f0), (h1, f1) in zip(curve, curve[1:]):
        if h0 <= hour <= h1:
            return f0 + (f1 - f0) * (hour - h0) / (h1 - h0)
    return 1.0


def congestion_factor(moment: datetime) -> float:
    """Typical traffic multiplier at the given local date and time."""
    hour = moment.hour + moment.minute / 60
    return _interpolate(_curve_for(moment.weekday()), hour)


def worst_case_factor(typical: float) -> float:
    """Multiplier on a bad day.

    Jams are not only slower but also less predictable: the gap between a normal
    and a bad day grows with congestion (1.0 -> 1.1, 1.75 -> 2.3).
    """
    return typical + 0.1 + 0.6 * (typical - 1.0)


def daily_curve(weekday: int, step_hours: float = 0.5) -> list[tuple[float, float]]:
    """Sampled curve for one day, used by the UI chart."""
    curve = _curve_for(weekday)
    steps = int(24 / step_hours)
    return [(i * step_hours, round(_interpolate(curve, i * step_hours), 3)) for i in range(steps + 1)]
