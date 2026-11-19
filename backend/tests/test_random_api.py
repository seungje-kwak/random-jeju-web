"""POST /random-points, POST /random-courses and the new Course fields (tasks/prd-random-jeju-merge.md US-010,
US-012, US-017). Offline: a fake store over app/data/*.json, local HS256 tokens, the rule planner."""
from __future__ import annotations

import copy
import json
import time
import uuid
from typing import Optional

import jwt
import pytest
from fastapi.testclient import TestClient

from app import areas, auth, config, main, store

SECRET = "test-secret-at-least-32-bytes-long!!"
PROFILE = {"interests": ["nature", "cafe", "food"], "fitness_level": 2, "max_walk_min": 20, "avoid_slopes": False,
           "condition_today": "normal", "diet": "none"}
OLD_TOWN = {"grid_id": 1, "lat": 33.511, "lng": 126.522, "adm_nm": "제주특별자치도 제주시 일도1동"}


class FakeStore:
    def __init__(self, places: list[dict]) -> None:
        self.places = places
        self.courses: dict[str, dict] = {}
        self.items: dict[str, list[dict]] = {}
        self.locations: dict[int, dict] = {}
        self.next_point: Optional[dict] = dict(OLD_TOWN)

    def list_places(self): return copy.deepcopy(self.places)
    def list_areas(self): return areas.load_seed_areas()
    def list_phrase_cards(self): return []
    def get_course(self, cid): return copy.deepcopy(self.courses.get(cid))
    def get_items(self, cid): return copy.deepcopy(self.items.get(cid, []))

    def create_course(self, course, items):
        self.courses[course["id"]] = copy.deepcopy(course)
        self.items[course["id"]] = copy.deepcopy(items)

    def draw_point(self): return copy.deepcopy(self.next_point)

    def add_location(self, row):
        lid = len(self.locations) + 1
        self.locations[lid] = {"location_id": lid, "course_id": None, **row}
        return dict(self.locations[lid])

    def get_location(self, lid): return copy.deepcopy(self.locations.get(lid))
    def link_location(self, lid, cid): self.locations[lid]["course_id"] = cid


def token(sub: str) -> dict:
    t = jwt.encode({"sub": sub, "role": "authenticated", "aud": "authenticated", "exp": int(time.time()) + 3600,
                    "is_anonymous": True}, SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture()
def fake(places, monkeypatch):
    fs = FakeStore(places)
    monkeypatch.setattr(store, "_store", fs)
    monkeypatch.setattr(auth, "_verifier", auth.TokenVerifier(secret=SECRET))
    monkeypatch.setattr(config, "USE_LLM", False)
    return fs


@pytest.fixture()
def client(fake):
    with TestClient(main.app) as c:
        yield c


def draw(client, user):
    res = client.post("/random-points", headers=token(user))
    assert res.status_code == 201, res.text
    return res.json()


def test_random_point_needs_a_token(client):
    assert client.post("/random-points").status_code == 401


def test_random_point_is_saved_for_the_user_with_what_is_near(client, fake):
    user = str(uuid.uuid4())
    body = draw(client, user)
    assert body["adm_nm"] == "일도1동" and body["area_id"] == "jeju-city"
    assert body["nearest_hub"]["km"] <= 3 and 1 <= len(body["preview_places"]) <= 3
    saved = fake.locations[body["location_id"]]
    assert saved["user_id"] == user and saved["address"] == "일도1동" and saved["grid_id"] == 1


def test_no_usable_cell_is_503(client, fake):
    fake.next_point = None
    res = client.post("/random-points", headers=token(str(uuid.uuid4())))
    assert res.status_code == 503 and res.json()["detail"]["code"] == "NO_RANDOM_CELLS"


def test_random_course_from_my_point(client, fake):
    user = str(uuid.uuid4())
    point = draw(client, user)
    res = client.post("/random-courses", headers=token(user), json={
        "location_id": point["location_id"], "user_profile": PROFILE, "start_time": "10:00", "end_time": "18:00"})
    assert res.status_code == 201, res.text
    course = res.json()
    assert course["kind"] == "random" and course["visits"] == []
    origin = course["random_origin"]
    assert origin["location_id"] == point["location_id"] and origin["adm_nm"] == "일도1동"
    assert origin["area_id"] == course["user_profile"]["area_id"] and origin["snap_km"] is not None
    assert origin["hub_name_ko"]
    saved = fake.courses[course["id"]]
    assert saved["owner_id"] == user and saved["origin_location_id"] == point["location_id"]
    assert fake.locations[point["location_id"]]["course_id"] == course["id"]
    assert "_hub_id" not in course["user_profile"]          # private keys never leave the server


def test_someone_elses_point_is_404(client):
    point = draw(client, str(uuid.uuid4()))
    res = client.post("/random-courses", headers=token(str(uuid.uuid4())), json={
        "location_id": point["location_id"], "user_profile": PROFILE, "start_time": "10:00", "end_time": "18:00"})
    assert res.status_code == 404 and res.json()["detail"]["code"] == "LOCATION_NOT_FOUND"


def test_unknown_point_is_404(client):
    res = client.post("/random-courses", headers=token(str(uuid.uuid4())), json={
        "location_id": 999, "user_profile": PROFILE, "start_time": "10:00", "end_time": "18:00"})
    assert res.status_code == 404


def test_bad_time_window_is_422(client):
    user = str(uuid.uuid4())
    point = draw(client, user)
    res = client.post("/random-courses", headers=token(user), json={
        "location_id": point["location_id"], "user_profile": PROFILE, "start_time": "18:00", "end_time": "10:00"})
    assert res.status_code == 422 and res.json()["detail"]["code"] == "INVALID_TIME_WINDOW"


def test_random_course_needs_a_token(client):
    res = client.post("/random-courses", json={"location_id": 1, "user_profile": PROFILE,
                                               "start_time": "10:00", "end_time": "18:00"})
    assert res.status_code == 401


def test_picked_course_has_the_new_fields_and_an_owner_when_signed_in(client, fake):
    user = str(uuid.uuid4())
    body = {"user_profile": PROFILE, "area_id": "aewol", "start_time": "10:00", "end_time": "18:00"}
    anon = client.post("/courses", json=body).json()
    mine = client.post("/courses", json=body, headers=token(user)).json()
    assert anon["kind"] == "pick" and anon["random_origin"] is None and anon["visits"] == []
    assert "owner_id" not in fake.courses[anon["id"]]
    assert fake.courses[mine["id"]]["owner_id"] == user


# --- US-017 paywall switch --------------------------------------------------------------------------------
def test_paywall_off_shows_every_stop(client, fake, monkeypatch):
    monkeypatch.setattr(config, "PAYWALL_ENABLED", False)
    c = client.post("/courses", json={"user_profile": PROFILE, "area_id": "aewol",
                                      "start_time": "10:00", "end_time": "18:00"}).json()
    assert c["locked_count"] == 0 and len(c["items"]) == c["total_items"] and c["tier"] == "premium"


def test_paywall_on_keeps_the_three_stop_preview(client, fake, monkeypatch):
    monkeypatch.setattr(config, "PAYWALL_ENABLED", True)
    c = client.post("/courses", json={"user_profile": PROFILE, "area_id": "aewol",
                                      "start_time": "10:00", "end_time": "18:00"}).json()
    assert c["tier"] == "free" and len(c["items"]) == min(3, c["total_items"])
    assert c["locked_count"] == c["total_items"] - len(c["items"])
