"""Visit check-in rules (tasks/prd-random-jeju-merge.md US-030, FR-19 - FR-21). Pure: no store, no network."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app import config
from app.visits import CourseFacts, judge, radius_m

NOW = datetime(2026, 11, 20, 6, 0, tzinfo=timezone.utc)            # 15:00 in Korea
MADE = NOW - timedelta(hours=5)                                     # course made at 10:00 KST
ORIGIN = {"location_id": 7, "lat": 33.5000, "lng": 126.5000}
BEACH = {"id": 1, "lat": 33.5100, "lng": 126.5100, "place_type": "beach"}
CAFE = {"id": 2, "lat": 33.5200, "lng": 126.5200, "place_type": "cafe"}
KM_LAT = 1 / 110.57                                                 # degrees of latitude per km


def course(**kw) -> CourseFacts:
    base = dict(id="c1", created_at=MADE, origin=ORIGIN, stops=[BEACH, CAFE])
    base.update(kw)
    return CourseFacts(**base)


def at(point: dict, north_m: float = 0.0) -> tuple[float, float]:
    return point["lat"] + north_m / 1000 * KM_LAT, point["lng"]


def kinds(found) -> list[tuple[str, object]]:
    return [(c.kind, c.place_id) for c in found]


def test_radius_by_place_type():
    assert radius_m(BEACH) == config.VISIT_RADIUS_WIDE_M == 500
    assert radius_m(CAFE) == config.VISIT_RADIUS_PLACE_M == 200


def test_random_point_inside_and_outside_500m():
    assert kinds(judge(*at(ORIGIN, 450), "exif", None, [course()], NOW)) == [("random_point", None)]
    assert judge(*at(ORIGIN, 560), "exif", None, [course()], NOW) == []


def test_wide_place_gets_500m_and_small_place_200m():
    assert kinds(judge(*at(BEACH, 450), "device", None, [course(origin=None)], NOW)) == [("course_place", 1)]
    assert kinds(judge(*at(CAFE, 180), "device", None, [course(origin=None)], NOW)) == [("course_place", 2)]
    assert judge(*at(CAFE, 260), "device", None, [course(origin=None)], NOW) == []


def test_both_kinds_at_once_and_nearest_stop():
    near_both = {"id": 3, "lat": ORIGIN["lat"], "lng": ORIGIN["lng"], "place_type": "cafe"}
    far_park = {"id": 4, "lat": ORIGIN["lat"] + 0.003, "lng": ORIGIN["lng"], "place_type": "park"}   # ~330 m
    found = judge(*at(ORIGIN, 20), "exif", None, [course(stops=[far_park, near_both])], NOW)
    assert kinds(found) == [("random_point", None), ("course_place", 3)]
    assert found[0].location_id == 7


def test_a_spot_picked_on_the_map_never_counts():
    assert judge(*at(ORIGIN), "manual", None, [course()], NOW) == []
    assert judge(None, None, None, None, [course()], NOW) == []


def test_photo_taken_before_the_course_does_not_count():
    taken_kst = (MADE - timedelta(hours=2)).astimezone(timezone(timedelta(hours=9))).replace(tzinfo=None)
    assert judge(*at(ORIGIN), "exif", taken_kst, [course()], NOW) == []
    # a camera clock a few minutes behind the server still counts
    slightly = (MADE - timedelta(minutes=5)).astimezone(timezone(timedelta(hours=9))).replace(tzinfo=None)
    assert kinds(judge(*at(ORIGIN), "exif", slightly, [course(stops=[])], NOW)) == [("random_point", None)]


def test_capture_time_with_its_zone():
    # photos.taken_at_kst returns Korea time with its zone (M7); the same instants judge the same way
    kst = timezone(timedelta(hours=9))
    assert judge(*at(ORIGIN), "exif", (MADE - timedelta(hours=2)).astimezone(kst), [course()], NOW) == []
    after = (MADE + timedelta(hours=1)).astimezone(kst)
    assert kinds(judge(*at(ORIGIN), "exif", after, [course(stops=[])], NOW)) == [("random_point", None)]


def test_no_capture_time_uses_the_upload_time():
    assert kinds(judge(*at(ORIGIN), "device", None, [course(stops=[])], NOW)) == [("random_point", None)]


@pytest.mark.parametrize("age_days,counts", [(6, True), (8, False)])
def test_only_courses_from_the_last_7_days(age_days, counts):
    old = course(created_at=NOW - timedelta(days=age_days), stops=[])
    assert bool(judge(*at(ORIGIN), "exif", None, [old], NOW)) is counts


def test_several_courses_each_checked():
    other = CourseFacts("c2", MADE, None, [{"id": 9, "lat": ORIGIN["lat"], "lng": ORIGIN["lng"], "place_type": "cafe"}])
    found = judge(*at(ORIGIN), "exif", None, [course(stops=[]), other], NOW)
    assert [(c.course_id, c.kind) for c in found] == [("c1", "random_point"), ("c2", "course_place")]
