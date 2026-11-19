"""MyPace Jeju API (9장). Run: uvicorn app.main:app --reload --port 8000"""
from __future__ import annotations

import logging
import unicodedata
from typing import Optional

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import areas, config, planner, random_spots
from .auth import User, current_user, optional_user
from .course_view import build_course
from .errors import ApiError
from .photos import public_url
from .posts_api import router as posts_router
from .schemas import (CreateCourseRequest, NicknameRequest, PurchaseRequest, RandomCourseRequest, ReplanRequest,
                      ReportRequest)
from .store import get_store

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("mypace")

app = FastAPI(title="MyPace Jeju API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
app.include_router(posts_router)   # photo posts, feed, likes, comments, photo map (M4)


@app.on_event("startup")
def _startup() -> None:
    get_store()  # fail at startup, not on the first request, when Supabase is not configured
    log.info("store=supabase llm=%s provider=%s model=%s require_verified=%s auth_hs256=%s",
             "on" if config.USE_LLM else "off (rule planner)", config.LLM_PROVIDER, config.LLM_MODEL,
             config.REQUIRE_VERIFIED, "on" if config.SUPABASE_JWT_SECRET else "off (SUPABASE_JWT_SECRET empty)")


def _course_response(course_id: str) -> dict:
    store = get_store()
    course = store.get_course(course_id)
    if course is None:
        raise ApiError(404, "COURSE_NOT_FOUND", "Course not found.")
    origin = store.get_location(course["origin_location_id"]) if course.get("origin_location_id") else None
    # FR-10 visits: only a course with an owner can have check-ins (FR-19)
    visits = [{"kind": v["kind"], "place_id": v.get("place_id"), "post_id": v["post_id"],
               "thumb_url": public_url(v.get("thumb_path")) or public_url(v.get("file_path"))}
              for v in store.course_visits(course_id)] if course.get("owner_id") else []
    return build_course(course, store.get_items(course_id), store.list_places(), store.list_phrase_cards(),
                        origin=origin, visits=visits)


@app.get("/")
def health() -> dict:
    return {"ok": True, "store": "supabase",
            "llm": f"{config.LLM_PROVIDER}:{config.LLM_MODEL}" if config.USE_LLM else False}


@app.get("/areas")
def list_areas() -> dict:
    store = get_store()
    return {"areas": areas.summaries(store.list_areas(), store.list_places())}


@app.get("/places")
def list_places(area_id: Optional[str] = None) -> dict:
    places = get_store().list_places()
    if area_id is not None:
        places = [p for p in places if p["area_id"] == area_id]
    return {"places": places}


@app.post("/courses", status_code=201)
def create_course(req: CreateCourseRequest, user: Optional[User] = Depends(optional_user)) -> dict:
    store = get_store()
    places = store.list_places()
    areas.check_area(req.area_id, store.list_areas(), places)
    course, items = planner.new_course(places, req.user_profile.model_dump(), req.start_time, req.end_time,
                                       req.area_id)
    if user is not None:              # FR-10: a signed-in traveler owns the course
        course["owner_id"] = user.id
    store.create_course(course, items)
    return _course_response(course["id"])


# --- random points and random courses (tasks/prd-random-jeju-merge.md FR-1 - FR-10) ---
@app.post("/random-points", status_code=201)
def draw_random_point(user: User = Depends(current_user)) -> dict:
    """FR-3: one point on usable land, saved for this traveler, with what is near it. No LLM call."""
    store = get_store()
    row = store.draw_point()
    if row is None:
        raise ApiError(503, "NO_RANDOM_CELLS", "There is nowhere to draw from right now.")
    places = store.list_places()
    selectable = random_spots.selectable_areas(store.list_areas(), places)
    point = {"lat": row["lat"], "lng": row["lng"]}
    near = random_spots.nearby(point, places, random_spots.cached_plain_hubs(places, selectable))
    adm = (row.get("adm_nm") or "").split()[-1] if row.get("adm_nm") else None
    loc = store.add_location({"lat": row["lat"], "lng": row["lng"], "address": adm, "grid_id": row["grid_id"],
                              "user_id": user.id})
    return {"location_id": loc["location_id"], "lat": row["lat"], "lng": row["lng"], "adm_nm": adm, **near}


@app.post("/random-courses", status_code=201)
def create_random_course(req: RandomCourseRequest, user: User = Depends(current_user)) -> dict:
    """FR-9: a day near the traveler's own drawn point. FR-8: no silent second draw on 409."""
    store = get_store()
    loc = store.get_location(req.location_id)
    if loc is None or loc.get("user_id") != user.id:
        raise ApiError(404, "LOCATION_NOT_FOUND", "That random point was not found.")
    places = store.list_places()
    selectable = random_spots.selectable_areas(store.list_areas(), places)
    course, items, _ = planner.random_course(places, req.user_profile.model_dump(), req.start_time, req.end_time,
                                             {"lat": loc["lat"], "lng": loc["lng"]}, selectable)
    course["owner_id"] = user.id
    course["origin_location_id"] = loc["location_id"]
    store.create_course(course, items)
    store.link_location(loc["location_id"], course["id"])
    return _course_response(course["id"])


@app.get("/courses/{course_id}")
def get_course(course_id: str) -> dict:
    return _course_response(course_id)


@app.post("/courses/{course_id}/replan")
def replan_course(course_id: str, req: ReplanRequest) -> dict:
    store = get_store()
    course = store.get_course(course_id)
    if course is None:
        raise ApiError(404, "COURSE_NOT_FOUND", "Course not found.")
    items = store.get_items(course_id)
    # Plan first; the DB changes only after the new items are ready (10.7 step 5).
    result = planner.replan(store.list_places(), course, items, req.reason, req.current_order)
    store.apply_replan(course_id, result.user_profile, result.statuses, result.delete_orders,
                       result.new_items, result.report_place_id, result.meal_gaps)
    return _course_response(course_id)


@app.post("/courses/{course_id}/shuffle", status_code=201)
def shuffle_course(course_id: str) -> dict:
    """P1 US-P15: a new course with the same choices and a different seed. The old course stays."""
    store = get_store()
    course = store.get_course(course_id)
    if course is None:
        raise ApiError(404, "COURSE_NOT_FOUND", "Course not found.")
    new, items = planner.shuffle_course(store.list_places(), course, store.get_items(course_id))
    store.create_course(new, items)
    return _course_response(new["id"])


@app.post("/places/{place_id}/report", status_code=201)
def report_place(place_id: int, req: ReportRequest) -> dict:
    store = get_store()
    if not any(p["id"] == place_id for p in store.list_places()):
        raise ApiError(404, "PLACE_NOT_FOUND", "Place not found.")
    return store.add_report(place_id, req.type)


@app.post("/purchase")
def purchase(req: PurchaseRequest) -> dict:
    """Mock payment: no payment data is accepted or stored (11.2)."""
    store = get_store()
    if store.get_course(req.course_id) is None:
        raise ApiError(404, "COURSE_NOT_FOUND", "Course not found.")
    store.set_tier(req.course_id, "premium")
    return _course_response(req.course_id)


# --- the caller (tasks/prd-random-jeju-merge.md FR-35) ---
def _me(user: User, row: Optional[dict]) -> dict:
    return {"user_id": user.id, "nickname": (row or {}).get("nickname"), "is_anonymous": user.is_anonymous}


def clean_nickname(raw: str) -> str:
    """Trimmed; 2-12 characters; no control or format characters (line breaks, zero-width marks)."""
    name = raw.strip()
    if not (config.NICKNAME_MIN <= len(name) <= config.NICKNAME_MAX) or any(
            unicodedata.category(ch).startswith("C") for ch in name):
        raise ApiError(422, "INVALID_NICKNAME",
                       f"Nickname must be {config.NICKNAME_MIN}-{config.NICKNAME_MAX} characters.")
    return name


@app.get("/me")
def get_me(user: User = Depends(current_user)) -> dict:
    return _me(user, get_store().get_user(user.id))


@app.post("/me")
def save_me(req: NicknameRequest, user: User = Depends(current_user)) -> dict:
    return _me(user, get_store().save_nickname(user.id, clean_nickname(req.nickname)))
