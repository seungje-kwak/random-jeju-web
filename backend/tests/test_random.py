"""Random points and random courses (tasks/prd-random-jeju-merge.md FR-0 - FR-8, US-010, US-011). Offline:
app/data/places.json and app/data/grids.json (written by scripts/mark_grids.py)."""
from __future__ import annotations

import json
import random

import pytest

from app import areas, config, planner, random_spots
from app.errors import ApiError

PROFILE = {"interests": ["nature", "cafe", "food"], "fitness_level": 2, "max_walk_min": 20, "avoid_slopes": False,
           "condition_today": "normal", "diet": "none"}

# Points the grid marking keeps random_point() away from; the planner must still not crash on them.
ODD_POINTS = {
    "sea north of Jeju City": {"lat": 33.56, "lng": 126.52},
    "Udo": {"lat": 33.505, "lng": 126.955},
    "Chuja": {"lat": 33.962, "lng": 126.30},
    "Hallasan summit area": {"lat": 33.362, "lng": 126.533},
}


@pytest.fixture(scope="module")
def grids() -> list[dict]:
    return json.loads((config.SEED_DATA_DIR / "grids.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def selectable(places) -> set[str]:
    return random_spots.selectable_areas(areas.load_seed_areas(), places)


def test_selectable_areas_leave_out_udo_and_chuja(selectable):
    assert "udo" not in selectable and "chuja" not in selectable
    assert {"jeju-city", "aewol", "seongsan", "seogwipo-city"} <= selectable


def test_usable_cells_are_in_ready_areas(grids, selectable):
    assert len(grids) > 5000
    assert all(g["area_id"] in selectable for g in grids)


def test_skip_reason(places, selectable):
    dense = random_spots.dense_places(places, selectable)
    assert random_spots.skip_reason({"land_share": 0.2, "land_lat": 33.5, "land_lng": 126.52}, dense, selectable) == "mostly_sea"
    assert random_spots.skip_reason({"land_share": 1.0, "land_lat": 33.505, "land_lng": 126.955}, dense, selectable) == "area_not_ready"
    assert random_spots.skip_reason({"land_share": 1.0, "land_lat": 33.362, "land_lng": 126.533}, dense, selectable) == "far_from_places"
    assert random_spots.skip_reason({"land_share": 1.0, "land_lat": 33.511, "land_lng": 126.522}, dense, selectable) is None  # old town


@pytest.mark.parametrize("profile", [PROFILE, {**PROFILE, "diet": "vegan", "interests": ["culture"]}])
def test_random_course_uses_the_nearest_hub_with_a_short_detour_for_meals(places, selectable, grids, profile):
    start, end = planner.check_time_window("10:00", "18:00")
    for point in grids[:: len(grids) // 12]:
        course, items, got = planner.random_course(places, profile, "10:00", "18:00", point, selectable, seed=1)
        assert got.hub.place["id"] == course["user_profile"]["_hub_id"]
        assert course["user_profile"]["area_id"] == got.area_id and course["kind"] == "random"
        hubs = []
        for area_id in selectable:
            ctx = planner._course_ctx(profile, start, end, area_id, 1)
            hubs += [(planner.km_between(point, h.place), h.fed(ctx.meals))
                     for h in planner.find_hubs(planner.hub_pool(planner.in_area(places, area_id), ctx, 2), ctx)]
        nearest = min(km for km, _ in hubs)
        fed_near = [km for km, fed in hubs if fed and km <= nearest + config.RANDOM_FED_DETOUR_KM]
        assert got.km <= nearest + config.RANDOM_FED_DETOUR_KM + 1e-9
        assert abs(got.km - (min(fed_near) if fed_near else nearest)) < 1e-9


def test_same_point_and_seed_give_the_same_course(places, selectable, grids):
    a = planner.random_course(places, PROFILE, "10:00", "18:00", grids[0], selectable, seed=5)
    b = planner.random_course(places, PROFILE, "10:00", "18:00", grids[0], selectable, seed=5)
    assert [i["place_id"] for i in a[1]] == [i["place_id"] for i in b[1]]


@pytest.mark.parametrize("name", list(ODD_POINTS))
def test_odd_points_give_a_course_or_409(places, selectable, name):
    try:
        course, items, picked = planner.random_course(places, PROFILE, "10:00", "18:00", ODD_POINTS[name], selectable, seed=3)
    except ApiError as e:
        assert e.status_code == 409
        return
    assert items and picked.area_id in selectable


def test_random_courses_keep_the_planner_rules(places, by_id, selectable, grids):
    """30 drawn cells: moves within MAX_MOVE_MIN, every stop open for its whole stay, inside the day."""
    rng = random.Random(11)
    start, end = planner.check_time_window("10:00", "18:00")
    for g in rng.sample(grids, 30):
        course, items, _ = planner.random_course(places, PROFILE, "10:00", "18:00", g, selectable, seed=rng.randrange(1 << 30))
        assert items
        for it in items:
            assert (it["move_min"] or 0) <= config.MAX_MOVE_MIN
            begin = planner.to_min(it["start_time"])
            assert start <= begin and begin + it["stay_min"] <= end
            assert planner.fits_hours(by_id[it["place_id"]], begin, it["stay_min"])
        assert all(by_id[i["place_id"]]["area_id"] == course["user_profile"]["area_id"] for i in items)


def test_nothing_fits_is_409(places, selectable, grids):
    with pytest.raises(ApiError) as e:
        planner.random_course(places, PROFILE, "10:00", "18:00", grids[0], set(), seed=1)
    assert e.value.status_code == 409


def test_nearby_preview(places, selectable):
    hubs = random_spots.plain_hubs(places, selectable)
    out = random_spots.nearby({"lat": 33.511, "lng": 126.522}, places, hubs)
    assert out["area_id"] == "jeju-city"
    assert out["nearest_hub"]["km"] <= 3
    assert 1 <= len(out["preview_places"]) <= config.PREVIEW_COUNT
    kms = [p["km"] for p in out["preview_places"]]
    assert all(k <= config.PREVIEW_RADIUS_KM for k in kms)


def test_new_course_is_unchanged_by_near(places):
    """A normal course never sets ctx.near, so the hub is still drawn by density."""
    a, items_a = planner.new_course(places, PROFILE, "10:00", "18:00", "aewol", seed=9)
    b, items_b = planner.new_course(places, PROFILE, "10:00", "18:00", "aewol", seed=9)
    assert [i["place_id"] for i in items_a] == [i["place_id"] for i in items_b]
    assert "kind" not in a
