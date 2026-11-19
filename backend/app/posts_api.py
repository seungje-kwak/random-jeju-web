"""Photo posts, feed, likes, comments and the photo map (tasks/prd-random-jeju-merge.md FR-11 - FR-18, FR-13a).
Errors use the 9.2 shape. Writes need a signed-in (guest or not) traveler; reads do not."""
from __future__ import annotations

import base64
import binascii
import json
import logging
import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from pydantic import BaseModel

from . import config
from . import visits as visits_mod
from .auth import User, current_user, optional_user
from .errors import ApiError
from .photos import process_image, public_coord, public_url, taken_at_kst
from .store import get_store

log = logging.getLogger("mypace.posts")
router = APIRouter()


# --- output -------------------------------------------------------------------------------------------
def guest_tag(user_id: Optional[str]) -> Optional[str]:
    """US-003: until a nickname is set, the screen shows "여행자" + these 4 characters."""
    return user_id.replace("-", "")[:4] if user_id else None


def post_out(row: dict, liked: bool, me: Optional[User]) -> dict:
    return {
        "post_id": row["post_id"],
        "author": {"nickname": row.get("nickname"), "tag": guest_tag(row.get("user_id"))},
        "is_mine": bool(me and row.get("user_id") == me.id),
        "created_at": row["created_at"],
        "content": row.get("content"),
        "category": row["category"],
        "image_url": public_url(row.get("file_path")),
        "thumb_url": public_url(row.get("thumb_path")) or public_url(row.get("file_path")),
        "lat": public_coord(row.get("lat")),
        "lng": public_coord(row.get("lng")),
        "like_count": row.get("like_count") or 0,
        "comment_count": row.get("comment_count") or 0,
        "is_liked": liked,
        # US-031 badge: the post's check-in, the random point first (feed_posts picks it)
        "visit": None if not row.get("visit_kind") else {
            "kind": row["visit_kind"], "place_name_ko": row.get("visit_place_name_ko"),
            "place_name_en": row.get("visit_place_name_en")},
    }


def record_visits(user: User, meta: dict, post_id: str) -> list[dict]:
    """FR-19 - FR-21 after a post is saved. A check-in is a bonus: if anything here fails, the post stands
    and the traveler just gets no check-in (logged)."""
    if meta["lat"] is None or meta["source"] not in visits_mod.COUNTED_SOURCES:
        return []
    store = get_store()
    try:
        now = datetime.now(timezone.utc)
        if meta["course_id"]:
            c = store.get_course(meta["course_id"]) if _is_uuid(meta["course_id"]) else None
            rows = [c] if c and c.get("owner_id") == user.id else []
        else:
            since = (now - timedelta(days=config.VISIT_WINDOW_DAYS)).isoformat()
            rows = store.recent_owned_courses(user.id, since)
        if not rows:
            return []
        by_id = {p["id"]: p for p in store.list_places()}
        facts = []
        for c in rows:
            origin = store.get_location(c["origin_location_id"]) if c.get("origin_location_id") else None
            stops = [by_id[i["place_id"]] for i in store.get_items(c["id"]) if i["place_id"] in by_id]
            facts.append(visits_mod.CourseFacts(c["id"], visits_mod.parse_time(c["created_at"]), origin, stops))
        found = visits_mod.judge(meta["lat"], meta["lng"], meta["source"], meta["taken_at"], facts, now)
        out = []
        for cand in found:
            v = store.add_visit(user.id, cand.course_id, cand.kind, cand.place_id, cand.location_id, post_id)
            place = by_id.get(cand.place_id) if cand.place_id else None
            out.append({"kind": cand.kind, "course_id": cand.course_id, "place_id": cand.place_id,
                        "place_name_ko": place["name_ko"] if place else None,
                        "place_name_en": place["name_en"] if place else None,
                        "is_new": bool(v.get("is_new"))})
        return sorted(out, key=lambda v: v["kind"] != "random_point")
    except Exception:
        log.exception("visit check failed for post %s", post_id)
        return []


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


def _one_post(post_id: str) -> dict:
    try:
        uuid.UUID(post_id)
        rows = get_store().feed(None, None, None, 1, post_id=post_id)
    except ValueError:
        rows = []
    if not rows:
        raise ApiError(404, "POST_NOT_FOUND", "That post was not found.")
    return rows[0]


# --- POST /posts (FR-11 - FR-13) ------------------------------------------------------------------------
def _meta(raw: str) -> dict:
    try:
        m = json.loads(raw)
        if not isinstance(m, dict):
            raise ValueError
    except ValueError:
        raise ApiError(422, "INVALID_META", "meta must be a JSON object.")
    if m.get("category") not in config.POST_CATEGORIES:
        raise ApiError(422, "INVALID_CATEGORY", "Pick one of the categories.")
    content = (m.get("content") or "").strip()
    if not isinstance(m.get("content", ""), (str, type(None))) or len(content) > config.POST_CONTENT_MAX:
        raise ApiError(422, "INVALID_CONTENT", f"Text can be up to {config.POST_CONTENT_MAX} characters.")
    lat, lng, source = m.get("lat"), m.get("lng"), m.get("location_source")
    if (lat is None) != (lng is None) or (lat is None) != (source is None):
        raise ApiError(422, "INVALID_LOCATION", "Send lat, lng and location_source together, or none of them.")
    if lat is not None:
        if (not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)) or isinstance(lat, bool)
                or not (-90 <= lat <= 90 and -180 <= lng <= 180) or math.isnan(lat) or math.isnan(lng)):
            raise ApiError(422, "INVALID_LOCATION", "lat / lng are not a position.")
        if source not in ("exif", "device", "manual"):
            raise ApiError(422, "INVALID_LOCATION", "location_source must be exif, device or manual.")
    return {"category": m["category"], "content": content, "lat": lat, "lng": lng, "source": source,
            "taken_at": taken_at_kst(m.get("taken_at") if isinstance(m.get("taken_at"), str) else None),
            "course_id": m.get("course_id") if isinstance(m.get("course_id"), str) else None}


@router.post("/posts", status_code=201)
def create_post(image: UploadFile = File(...), meta: str = Form(...), user: User = Depends(current_user)) -> dict:
    """FR-11: one photo + text + category. Files go to Storage first; if the DB write fails they are removed."""
    store = get_store()
    data = image.file.read(config.PHOTO_MAX_BYTES + 1)
    if len(data) > config.PHOTO_MAX_BYTES:
        raise ApiError(413, "FILE_TOO_LARGE", "The photo is too large.")
    m = _meta(meta)
    since = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    if store.uploads_since(user.id, since) >= config.UPLOADS_PER_DAY:
        raise ApiError(429, "UPLOAD_LIMIT", f"You can post up to {config.UPLOADS_PER_DAY} photos a day.")
    processed = process_image(data)

    name = uuid.uuid4().hex
    uploaded: list[str] = []
    try:
        photo_path = store.upload_file(config.PHOTO_BUCKET, f"{name}.jpg", processed.photo)
        uploaded.append(photo_path)
        thumb_path = store.upload_file(config.THUMB_BUCKET, f"{name}_thumb.jpg", processed.thumb)
        uploaded.append(thumb_path)
        made = store.create_photo_post({
            "p_user": user.id, "p_file_path": photo_path, "p_thumb_path": thumb_path,
            "p_lat": m["lat"], "p_lng": m["lng"],
            "p_image_time": m["taken_at"].isoformat() if m["taken_at"] else None,
            "p_location_source": m["source"], "p_content": m["content"], "p_category": m["category"],
        })
    except Exception:
        log.exception("photo post failed; removing %s", uploaded)
        if uploaded:
            try:
                store.remove_files(uploaded)
            except Exception:
                log.exception("could not remove %s", uploaded)
        raise ApiError(502, "UPLOAD_FAILED", "Could not save the photo. Please try again.")
    found = record_visits(user, m, made["post_id"])
    # `visit`: the first check-in (the random point before a stop); `visits`: all of them
    return {"post": post_out(_one_post(made["post_id"]), False, user), "visit": found[0] if found else None,
            "visits": found}


# --- feed (FR-16) ---------------------------------------------------------------------------------------
def make_cursor(created_at: str, post_id: str) -> str:
    """Opaque and URL-safe: the raw time has a "+" that a query string would turn into a space."""
    return base64.urlsafe_b64encode(f"{created_at}|{post_id}".encode()).decode().rstrip("=")


def _cursor(cursor: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    if not cursor:
        return None, None
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        at, sep, pid = raw.rpartition("|")
        datetime.fromisoformat(at.replace("Z", "+00:00"))
        uuid.UUID(pid)
        if not sep:
            raise ValueError
    except (ValueError, binascii.Error, UnicodeDecodeError):
        raise ApiError(422, "INVALID_CURSOR", "That cursor is not valid.")
    return at, pid


@router.get("/posts")
def list_posts(category: Optional[str] = None, cursor: Optional[str] = None,
               limit: int = Query(default=config.FEED_PAGE, ge=1, le=50),
               user: Optional[User] = Depends(optional_user)) -> dict:
    if category is not None and category not in config.POST_CATEGORIES:
        raise ApiError(422, "INVALID_CATEGORY", "Pick one of the categories.")
    before, before_id = _cursor(cursor)
    store = get_store()
    rows = store.feed(category, before, before_id, limit)
    liked = store.liked_post_ids(user.id, [r["post_id"] for r in rows]) if user else set()
    last = rows[-1] if len(rows) == limit else None
    return {"posts": [post_out(r, r["post_id"] in liked, user) for r in rows],
            "next_cursor": make_cursor(last["created_at"], last["post_id"]) if last else None}


@router.get("/posts/{post_id}")
def get_post(post_id: str, user: Optional[User] = Depends(optional_user)) -> dict:
    row = _one_post(post_id)
    liked = bool(user) and post_id in get_store().liked_post_ids(user.id, [post_id])
    return post_out(row, liked, user)


# --- likes and comments (FR-17, FR-18) ------------------------------------------------------------------
@router.post("/posts/{post_id}/like")
def like_post(post_id: str, user: User = Depends(current_user)) -> dict:
    _one_post(post_id)
    r = get_store().toggle_like(post_id, user.id)
    return {"liked": r["liked"], "like_count": r["like_count"]}


def _comment_out(row: dict, nick: Optional[str], me: Optional[User]) -> dict:
    return {"id": row["id"], "author": {"nickname": nick, "tag": guest_tag(row.get("user_id"))},
            "is_mine": bool(me and row.get("user_id") == me.id), "content": row["content"],
            "created_at": row["created_at"]}


@router.get("/posts/{post_id}/comments")
def list_comments(post_id: str, user: Optional[User] = Depends(optional_user)) -> dict:
    _one_post(post_id)
    store = get_store()
    rows = store.list_comments(post_id, 200)
    names = store.nicknames([r["user_id"] for r in rows])
    return {"comments": [_comment_out(r, names.get(r["user_id"]), user) for r in rows]}


class CommentIn(BaseModel):
    content: str = ""


@router.post("/posts/{post_id}/comments", status_code=201)
def add_comment(post_id: str, req: CommentIn, user: User = Depends(current_user)) -> dict:
    text = req.content.strip()
    if not text or len(text) > config.COMMENT_MAX:
        raise ApiError(422, "INVALID_COMMENT", f"Write 1 to {config.COMMENT_MAX} characters.")
    _one_post(post_id)
    store = get_store()
    made = store.add_comment(post_id, user.id, text)
    nick = store.nicknames([user.id]).get(user.id)
    return _comment_out({"id": made["id"], "user_id": user.id, "content": text, "created_at": made["created_at"]},
                        nick, user)


# --- photo map (FR-14, FR-15) ---------------------------------------------------------------------------
def _box(min_lat, min_lng, max_lat, max_lng) -> dict:
    vals = [min_lat, min_lng, max_lat, max_lng]
    if any(v is None or math.isnan(v) for v in vals) or not (min_lat < max_lat and min_lng < max_lng):
        raise ApiError(422, "INVALID_BBOX", "Send min_lat < max_lat and min_lng < max_lng.")
    return {"min_lat": min_lat, "min_lng": min_lng, "max_lat": max_lat, "max_lng": max_lng}


@router.get("/photos/map")
def photo_markers(min_lat: Optional[float] = None, min_lng: Optional[float] = None,
                  max_lat: Optional[float] = None, max_lng: Optional[float] = None) -> dict:
    rows = get_store().photos_in_bbox(_box(min_lat, min_lng, max_lat, max_lng), 300)
    return {"photos": [{"photo_id": r["photo_id"], "post_id": r["post_id"], "lat": public_coord(r["lat"]),
                        "lng": public_coord(r["lng"]), "thumb_url": public_url(r["thumb_path"])} for r in rows]}


@router.get("/photos/clusters")
def photo_clusters(min_lat: Optional[float] = None, min_lng: Optional[float] = None,
                   max_lat: Optional[float] = None, max_lng: Optional[float] = None) -> dict:
    rows = get_store().photo_clusters(_box(min_lat, min_lng, max_lat, max_lng))
    return {"clusters": [{"admin_area_id": r["admin_area_id"], "name": r["name"], "count": r["count"],
                          "lat": public_coord(r["lat"]), "lng": public_coord(r["lng"]),
                          "thumb_url": public_url(r["thumb_path"]),
                          # where its photos are, so a tap can zoom to them (all rounded like the photos)
                          "extent": {k: public_coord(r.get(k)) for k in ("south", "west", "north", "east")}}
                         for r in rows]}
