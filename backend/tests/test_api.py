"""API tests: CRUD, validation and the shape of the plans (offline, so everything is estimated)."""

HOME = {"name": "Home", "lat": 54.3530, "lon": 18.5870}
OFFICE = {"name": "Office", "lat": 54.4035, "lon": 18.5700, "parking_cost_pln": 15}


def create_places(client) -> tuple[int, int]:
    home = client.post("/api/places", json=HOME).json()
    office = client.post("/api/places", json=OFFICE).json()
    return home["id"], office["id"]


def trip_payload(origin_id: int, destination_id: int, **overrides) -> dict:
    payload = {
        "title": "Work",
        "origin_id": origin_id,
        "destination_id": destination_id,
        "arrive_by": "09:00",
        "importance": "high",
        "weekdays": [0, 1, 2, 3, 4],
    }
    return {**payload, **overrides}


def journey_payload(**overrides) -> dict:
    payload = {
        "origin": HOME,
        "destination": {"name": "Office", "lat": OFFICE["lat"], "lon": OFFICE["lon"]},
        "time": "2026-11-09T09:00:00",
        "time_mode": "arrive",
        "now": "2026-11-09T06:00:00",
    }
    return {**payload, **overrides}


def test_place_crud(client):
    created = client.post("/api/places", json=HOME)
    assert created.status_code == 201
    place_id = created.json()["id"]

    updated = client.put(f"/api/places/{place_id}", json={**HOME, "name": "Flat"})
    assert updated.json()["name"] == "Flat"
    assert [p["name"] for p in client.get("/api/places").json()] == ["Flat"]

    assert client.delete(f"/api/places/{place_id}").status_code == 204
    assert client.get(f"/api/places/{place_id}").status_code == 404


def test_place_validation(client):
    assert client.post("/api/places", json={**HOME, "lat": 123}).status_code == 422
    assert client.post("/api/places", json={**HOME, "name": ""}).status_code == 422


def test_trip_crud(client):
    home_id, office_id = create_places(client)

    created = client.post("/api/trips", json=trip_payload(home_id, office_id))
    assert created.status_code == 201
    trip = created.json()
    assert trip["destination"]["name"] == "Office"

    changed = client.put(f"/api/trips/{trip['id']}", json=trip_payload(home_id, office_id, title="Office day"))
    assert changed.json()["title"] == "Office day"

    assert client.delete(f"/api/trips/{trip['id']}").status_code == 204
    assert client.get("/api/trips").json() == []


def test_trip_validation(client):
    home_id, office_id = create_places(client)

    same_place = trip_payload(home_id, home_id)
    no_schedule = trip_payload(home_id, office_id, weekdays=[])
    both_schedules = trip_payload(home_id, office_id, date="2026-11-12")
    unknown_place = trip_payload(home_id, 999)

    for payload in (same_place, no_schedule, both_schedules, unknown_place):
        assert client.post("/api/trips", json=payload).status_code == 422


def test_place_used_by_a_trip_cannot_be_deleted(client):
    home_id, office_id = create_places(client)
    client.post("/api/trips", json=trip_payload(home_id, office_id))
    assert client.delete(f"/api/places/{home_id}").status_code == 409


def test_profile_update(client):
    profile = client.get("/api/profile").json()
    assert profile["has_transit_pass"] is False

    updated = client.put("/api/profile", json={**profile, "bike_is_electric": True, "priority": "cheapest"})
    assert updated.status_code == 200
    saved = client.get("/api/profile").json()
    assert (saved["bike_is_electric"], saved["priority"]) == (True, "cheapest")


def test_journey_plan_for_an_ad_hoc_search(client):
    response = client.post("/api/plan/journey", json=journey_payload())
    assert response.status_code == 200
    plan = response.json()

    ids = [option["id"] for option in plan["options"]]
    assert plan["recommended"] in ids
    assert {"car", "taxi", "transit-0", "bike-0"} <= set(ids)
    assert plan["transit_source"] == "estimate"  # offline mode
    assert plan["status"] == "ok"
    assert plan["backup"] is not None

    car = next(option for option in plan["options"] if option["id"] == "car")
    assert len(car["legs"][0]["geometry"]) >= 2  # shapes are included for the map


def test_journey_in_depart_mode_leaves_at_the_requested_time(client):
    plan = client.post("/api/plan/journey", json=journey_payload(time_mode="depart")).json()

    car = next(option for option in plan["options"] if option["id"] == "car")
    assert car["depart_at"] == "2026-11-09T09:00:00"
    assert plan["backup"] is None


def test_journey_validation(client):
    same_point = journey_payload(destination=HOME)
    assert client.post("/api/plan/journey", json=same_point).status_code == 422


def test_week_plan(client):
    home_id, office_id = create_places(client)
    client.post("/api/trips", json=trip_payload(home_id, office_id))
    client.post(
        "/api/trips",
        json=trip_payload(home_id, office_id, title="Exam", weekdays=[], date="2026-11-14", arrive_by="10:00"),
    )

    # 2026-11-09 is a Monday.
    plan = client.get("/api/plan/week", params={"start": "2026-11-09", "now": "2026-11-09T06:00:00"}).json()

    assert len(plan["days"]) == 7
    assert [len(day["trips"]) for day in plan["days"]] == [1, 1, 1, 1, 1, 1, 0]
    assert plan["summary"]["trips_count"] == 6

    monday_trip = plan["days"][0]["trips"][0]
    assert monday_trip["title"] == "Work"
    assert monday_trip["status"] == "ok"
    assert monday_trip["recommended"] in {o["id"] for o in monday_trip["options"]}
    # The overview carries no route shapes; they are fetched per journey.
    assert all(leg["geometry"] == [] for o in monday_trip["options"] for leg in o["legs"])


def test_advice_falls_back_to_rules_without_an_api_key(client):
    home_id, office_id = create_places(client)
    client.post("/api/trips", json=trip_payload(home_id, office_id))

    for language in ("en", "pl"):
        advice = client.post(
            "/api/plan/advice", json={"start": "2026-11-09", "now": "2026-11-09T06:00:00", "language": language}
        ).json()
        assert advice["source"] == "rules"
        assert advice["text"].startswith("- ")


def test_traffic_curve(client):
    curve = client.get("/api/plan/traffic", params={"day": "2026-11-09"}).json()
    assert curve[0] == {"hour": 0.0, "factor": 1.0}
    assert max(point["factor"] for point in curve) >= 1.7
