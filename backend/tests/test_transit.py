"""Unit tests for choosing which timetable connections to show."""

from datetime import datetime, timedelta

from app.services.transit import MAX_ITINERARIES, TransitItinerary, TransitLeg, select_varied

DEADLINE = datetime(2026, 11, 9, 8, 15)


def connection(lines: list[str], minutes_before: int, ride_minutes: int = 10, walk_minutes: int = 10) -> TransitItinerary:
    """A connection leaving `minutes_before` the deadline: one walk, then one ride per line."""
    depart = DEADLINE - timedelta(minutes=minutes_before)
    cursor = depart + timedelta(minutes=walk_minutes)
    legs = [TransitLeg("walk", None, None, None, None, None, depart, cursor, None, None, [])]
    for line in lines:
        end = cursor + timedelta(minutes=ride_minutes)
        legs.append(TransitLeg("bus", line, None, None, "A", "B", cursor, end, 3, None, []))
        cursor = end
    return TransitItinerary(depart, cursor, len(lines) - 1, legs)


def shown_lines(itineraries: list[TransitItinerary]) -> list[tuple[str, ...]]:
    return [itinerary.lines for itinerary in itineraries]


def test_each_line_combination_is_shown_once_plus_one_extra_departure_of_the_best():
    candidates = [
        connection(["168"], 40),
        connection(["168"], 60),
        connection(["168"], 80),
        connection(["127", "6"], 45),
    ]
    chosen = select_varied(candidates, arrive_by=True)

    assert shown_lines(chosen) == [("168",), ("127", "6"), ("168",)]
    # Closest to the deadline first, then the previous departure as a fallback.
    assert [i.depart for i in chosen if i.lines == ("168",)] == [candidates[0].depart, candidates[1].depart]


def test_connection_with_a_change_is_not_crowded_out_by_repeats_of_a_direct_line():
    repeats = [connection(["168"], 30 + 10 * n) for n in range(8)]
    with_change = connection(["162", "9"], 50)

    assert ("162", "9") in shown_lines(select_varied([*repeats, with_change], arrive_by=True))


def test_the_connection_with_the_least_walking_is_always_included():
    fast_but_far = [connection([line], 40, walk_minutes=20) for line in ("1", "2", "3", "4", "5")]
    slow_but_near = connection(["10", "130", "115"], 70, ride_minutes=15, walk_minutes=3)
    chosen = select_varied([*fast_but_far, slow_but_near], arrive_by=True)

    assert ("10", "130", "115") in shown_lines(chosen)
    assert len({itinerary.lines for itinerary in chosen}) == MAX_ITINERARIES


def test_duplicates_from_the_two_searches_are_merged():
    same = connection(["168"], 40)
    assert len(select_varied([same, connection(["168"], 40)], arrive_by=True)) == 1


def test_depart_mode_prefers_the_earliest_departure_of_each_line():
    later, earlier = connection(["168"], 20), connection(["168"], 40)
    chosen = select_varied([later, earlier], arrive_by=False)
    assert [i.depart for i in chosen] == [earlier.depart, later.depart]


def test_no_candidates_gives_an_empty_list():
    assert select_varied([], arrive_by=True) == []
