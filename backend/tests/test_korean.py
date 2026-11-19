"""Korean course text (tasks/prd-random-jeju-merge.md US-042). Offline: places.json, the rule planner."""
from __future__ import annotations

import re

import pytest

from app import planner
from app.schemas import LLMCourse

HANGUL = re.compile("[가-힣]")
PROFILES = [
    {"interests": ["nature", "cafe"], "fitness_level": 2, "max_walk_min": 20, "avoid_slopes": False,
     "condition_today": "normal", "diet": "none"},
    {"interests": ["culture"], "fitness_level": 1, "max_walk_min": 10, "avoid_slopes": True,
     "condition_today": "tired", "diet": "vegan"},
]


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("area", ["jeju-city", "seongsan", "andeok"])
def test_every_stop_and_free_meal_time_has_korean_text(places, profile, area):
    course, items = planner.new_course(places, profile, "10:00", "19:00", area, seed=3)
    assert items
    for it in items:
        assert it["reason_ko"] and HANGUL.search(it["reason_ko"]) and len(it["reason_ko"]) <= 300
        assert it["reason_en"]                                     # English stays for other languages
    for g in course["meal_gaps"]:
        assert HANGUL.search(g["message_ko"]) and g["start_time"] in g["message_ko"]


def test_rule_reason_ko_mentions_only_true_food_facts(by_id):
    food = next(p for p in by_id.values() if p["category"] == "food" and p.get("food_options")
                and p["food_options"].get("solo_ok") is True and p["food_options"].get("english_menu") is not True)
    text = planner.rule_reason_ko(food, {"interests": ["food"], "diet": "none"}, rest=False)
    assert text.startswith("식사를 즐기기 좋은 장소예요.") and "혼자 주문하기 편해요." in text
    assert "영어 메뉴" not in text


def test_rule_reason_ko_rest_and_rain(by_id):
    indoor = next(p for p in by_id.values() if p["accessibility"]["indoor"] and p["category"] == "culture")
    text = planner.rule_reason_ko(indoor, {"interests": ["culture"], "diet": "none",
                                           "conditions": {"indoor_only": True}}, rest=True)
    assert "문화와 역사에 관심이 있다고 하셔서 추천했어요." in text
    assert "실내 공간이라 비 오는 날에도 방문하기 좋아요." in text and text.endswith("앉아서 잠시 쉬어가기 좋아요.")


def test_llm_korean_reason_wins_and_empty_falls_back(places, by_id):
    profile = PROFILES[0]
    start, end = planner.check_time_window("10:00", "18:00")
    ctx = planner._course_ctx(profile, start, end, "jeju-city", 1)
    stop = next(p for p in planner.in_area(places, "jeju-city") if p["category"] == "nature" and not p.get("open_time"))
    out = LLMCourse.model_validate({"items": [
        {"place_id": stop["id"], "order": 1, "stay_min": 45, "reason_en": "Nice.", "reason_ko": "  바다가 예뻐요.  "},
    ]})
    rows = planner.schedule(out.items, by_id, ctx)
    assert rows[0]["reason_ko"] == "바다가 예뻐요."
    old_shape = LLMCourse.model_validate({"items": [{"place_id": stop["id"], "order": 1, "stay_min": 45, "reason_en": "Nice."}]})
    assert HANGUL.search(planner.schedule(old_shape.items, by_id, ctx)[0]["reason_ko"])


def test_gap_row_in_korean():
    g = planner.gap_row("lunch", "no_diet_match", "12:00", "12:45", "vegan")
    assert g["message_ko"] == "이 지역에서 비건 식당을 찾지 못해서 12:00~12:45은 점심 시간으로 비워 두었어요."
    assert g["message_en"].startswith("We couldn't find a vegan-friendly restaurant")
