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

    # --- enough of posts and visits for the check-in tests (M5) ---
    posts: list
    visits: list

    def _ensure(self):
        if not hasattr(self, "visits"):
            self.posts, self.visits = [], []

    def upload_file(self, bucket, name, data): return f"{bucket}/{name}"
    def remove_files(self, paths): pass
    def uploads_since(self, user_id, since): return 0

    def create_photo_post(self, a):
        self._ensure()
        pid = str(uuid.uuid4())
        self.posts.append({"post_id": pid, "user_id": a["p_user"], "nickname": None, "created_at": "2026-11-20T06:00:00+00:00",
                           "content": None, "category": a["p_category"], "file_path": a["p_file_path"],
                           "thumb_path": a["p_thumb_path"], "lat": a["p_lat"], "lng": a["p_lng"],
                           "like_count": 0, "comment_count": 0})
        return {"post_id": pid, "photo_id": len(self.posts)}

    def feed(self, category, before, before_id, limit, post_id=None):
        self._ensure()
        rows = [dict(p) for p in self.posts if post_id is None or p["post_id"] == post_id]
        for r in rows:
            v = sorted((v for v in self.visits if v["post_id"] == r["post_id"]), key=lambda v: v["kind"] != "random_point")
            if v:
                place = next((p for p in self.places if p["id"] == v[0]["place_id"]), None)
                r.update(visit_kind=v[0]["kind"], visit_place_name_ko=place and place["name_ko"],
                         visit_place_name_en=place and place["name_en"])
        return rows[:limit]

    def liked_post_ids(self, user_id, ids): return set()

    def recent_owned_courses(self, user_id, since):
        return [dict(c) for c in self.courses.values() if c.get("owner_id") == user_id]

    def add_visit(self, user_id, course_id, kind, place_id, location_id, post_id):
        self._ensure()
        same = next((v for v in self.visits if v["course_id"] == course_id and v["kind"] == kind
                     and (v["place_id"] or 0) == (place_id or 0)), None)
        if same:
            return {**same, "is_new": False}
        v = {"course_id": course_id, "kind": kind, "place_id": place_id, "post_id": post_id}
        self.visits.append(v)
        return {**v, "is_new": True}

    def course_visits(self, course_id):
        self._ensure()
        return [{**v, "thumb_path": f"thumbnails/{v['post_id']}.jpg", "file_path": None}
                for v in self.visits if v["course_id"] == course_id]


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


# --- FR-3a example course under a fresh point -----------------------------------------------------------
def example(client, user, location_id, body=None):
    return client.post(f"/random-points/{location_id}/example-course", headers=token(user), json=body or {})


def test_example_course_under_my_point_is_shown_but_not_saved(client, fake):
    user = str(uuid.uuid4())
    point = draw(client, user)
    res = example(client, user, point["location_id"])
    assert res.status_code == 200, res.text
    body = res.json()
    stops = body["stops"]
    assert len(stops) >= 2 and [s["order"] for s in stops] == list(range(1, len(stops) + 1))
    assert all(isinstance(s["lat"], float) and isinstance(s["lng"], float) and s["name_ko"] for s in stops)
    assert body["area_id"] == "jeju-city" and body["hub"]["name_ko"] and body["personalized"] is False
    assert (body["start_time"], body["end_time"]) == (config.EXAMPLE_START, config.EXAMPLE_END)
    assert fake.courses == {} and fake.locations[point["location_id"]]["course_id"] is None   # nothing saved


def test_example_course_is_the_course_planned_there_with_the_same_taste(client, fake):
    user = str(uuid.uuid4())
    point = draw(client, user)
    trip = {"user_profile": PROFILE, "start_time": "10:00", "end_time": "18:00"}
    ex = example(client, user, point["location_id"], trip).json()
    course = client.post("/random-courses", headers=token(user), json={"location_id": point["location_id"], **trip}).json()
    assert ex["personalized"] is True
    assert [(s["place_id"], s["start_time"]) for s in ex["stops"]] == \
        [(i["place_id"], i["start_time"]) for i in course["items"]]


def test_example_course_never_calls_the_llm(client, monkeypatch):
    from app import planner
    monkeypatch.setattr(config, "USE_LLM", True)
    monkeypatch.setattr(planner, "call_llm", lambda *a, **k: pytest.fail("the example course called the LLM"))
    user = str(uuid.uuid4())
    point = draw(client, user)
    assert example(client, user, point["location_id"]).status_code == 200


def test_example_course_needs_my_own_point_and_a_good_window(client):
    user = str(uuid.uuid4())
    point = draw(client, user)
    assert client.post(f"/random-points/{point['location_id']}/example-course", json={}).status_code == 401
    other = example(client, str(uuid.uuid4()), point["location_id"])
    assert other.status_code == 404 and other.json()["detail"]["code"] == "LOCATION_NOT_FOUND"
    bad = example(client, user, point["location_id"], {"start_time": "18:00", "end_time": "10:00"})
    assert bad.status_code == 422 and bad.json()["detail"]["code"] == "INVALID_TIME_WINDOW"


def test_each_point_has_its_own_stable_seed():
    from app import random_spots
    seeds = [random_spots.seed_for_location(i) for i in range(1, 51)]
    assert seeds == [random_spots.seed_for_location(i) for i in range(1, 51)]
    assert len(set(seeds)) == 50 and all(0 <= s < 2 ** 31 for s in seeds)


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


# --- M5 visit check-ins (US-030, US-031) ---------------------------------------------------------------
def _photo() -> bytes:
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), "white").save(buf, "JPEG")
    return buf.getvalue()


def _post(client, user, lat, lng, source="exif", course_id=None):
    meta = {"category": "관광", "lat": lat, "lng": lng, "location_source": source}
    if course_id:
        meta["course_id"] = course_id
    return client.post("/posts", headers=token(user), files={"image": ("a.jpg", _photo(), "image/jpeg")},
                       data={"meta": json.dumps(meta, ensure_ascii=False)})


def _random_course(client, user):
    point = draw(client, user)
    course = client.post("/random-courses", headers=token(user), json={
        "location_id": point["location_id"], "user_profile": PROFILE, "start_time": "10:00", "end_time": "18:00"}).json()
    return point, course


def test_photo_at_the_random_point_checks_in_once(client, fake, monkeypatch):
    monkeypatch.setattr(config, "PAYWALL_ENABLED", False)
    user = str(uuid.uuid4())
    point, course = _random_course(client, user)
    r = _post(client, user, point["lat"] + 0.001, point["lng"])                # about 110 m away
    assert r.status_code == 201, r.text
    visit = r.json()["visit"]
    assert visit["kind"] == "random_point" and visit["course_id"] == course["id"] and visit["is_new"] is True
    again = _post(client, user, point["lat"], point["lng"]).json()
    assert again["visit"]["is_new"] is False                                     # FR-21: once per course
    shown = client.get(f"/courses/{course['id']}").json()["visits"]
    # the old-town point is also within stops' radius, so each photo may check in its nearest stop too:
    # at most one stop per photo, and every stop at most once (FR-21)
    kinds = [v["kind"] for v in shown]
    stop_ids = [v["place_id"] for v in shown if v["kind"] == "course_place"]
    assert kinds.count("random_point") == 1 and len(stop_ids) <= 2 and len(set(stop_ids)) == len(stop_ids)
    assert all(v["thumb_url"].endswith(".jpg") for v in shown)
    feed = client.get("/posts").json()["posts"]
    assert feed[0]["visit"]["kind"] == "random_point"


def test_photo_at_a_stop_checks_in_that_stop(client, fake):
    user = str(uuid.uuid4())
    _, course = _random_course(client, user)
    stop = course["items"][-1]["place"]
    r = _post(client, user, stop["lat"], stop["lng"], source="device", course_id=course["id"]).json()
    places = [v for v in r["visits"] if v["kind"] == "course_place"]
    assert places and places[0]["place_id"] == stop["id"] and places[0]["place_name_ko"] == stop["name_ko"]


def test_no_check_in_for_a_picked_spot_or_someone_elses_course(client, fake):
    user, other = str(uuid.uuid4()), str(uuid.uuid4())
    point, course = _random_course(client, user)
    assert _post(client, user, point["lat"], point["lng"], source="manual").json()["visit"] is None
    assert _post(client, other, point["lat"], point["lng"], course_id=course["id"]).json()["visit"] is None
    assert _post(client, other, point["lat"], point["lng"]).json()["visit"] is None   # not their course


def test_a_failing_check_in_does_not_fail_the_post(client, fake, monkeypatch):
    user = str(uuid.uuid4())
    point, _ = _random_course(client, user)
    monkeypatch.setattr(fake, "add_visit", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db down")))
    r = _post(client, user, point["lat"], point["lng"])
    assert r.status_code == 201 and r.json()["visit"] is None
