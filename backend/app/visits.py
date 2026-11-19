"""Visit check-ins (tasks/prd-random-jeju-merge.md FR-19 - FR-21, Q-08).

A photo checks the traveler in at their own recent course when it was taken there: within
VISIT_RADIUS_RANDOM_M of the course's random point (kind "random_point") and/or within a stop's radius
(kind "course_place": 500 m for wide places such as beaches and oreums, 200 m otherwise; the nearest stop
in range). Only a position from the photo itself (EXIF) or the phone counts; a spot picked on the map
does not. judge() is pure so it can be tested without a database.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from . import config
from .planner import haversine_m

KST = timezone(timedelta(hours=9))
COUNTED_SOURCES = ("exif", "device")


@dataclass(frozen=True)
class Candidate:
    course_id: str
    kind: str                       # "random_point" | "course_place"
    place_id: Optional[int] = None
    location_id: Optional[int] = None
    meters: float = 0.0


@dataclass
class CourseFacts:
    """What judge() needs about one of the traveler's courses."""
    id: str
    created_at: datetime            # aware
    origin: Optional[dict]          # {location_id, lat, lng} of a random course, else None
    stops: list[dict]               # place dicts: id, lat, lng, place_type


def radius_m(place: dict) -> float:
    return config.VISIT_RADIUS_WIDE_M if place.get("place_type") in config.VISIT_WIDE_TYPES else config.VISIT_RADIUS_PLACE_M


def parse_time(value) -> datetime:
    """Supabase timestamptz text ("2026-11-19T07:40:28.147+00:00" or "...Z") -> aware datetime."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    t = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def judge(lat: Optional[float], lng: Optional[float], source: Optional[str], taken_kst: Optional[datetime],
          courses: list[CourseFacts], now: datetime) -> list[Candidate]:
    """FR-20. `taken_kst`: the photo's capture time, with its zone (photos.taken_at_kst) or without one (then it
    is Korea time); None = the upload time `now` (aware)."""
    if lat is None or lng is None or source not in COUNTED_SOURCES:
        return []
    if taken_kst is None:
        taken = now
    else:
        taken = taken_kst if taken_kst.tzinfo else taken_kst.replace(tzinfo=KST)
    leeway = timedelta(minutes=config.VISIT_CLOCK_LEEWAY_MIN)
    out: list[Candidate] = []
    for c in courses:
        if now - c.created_at > timedelta(days=config.VISIT_WINDOW_DAYS):
            continue
        if taken < c.created_at - leeway:          # taken before the course existed
            continue
        if c.origin is not None:
            d = haversine_m(lat, lng, c.origin["lat"], c.origin["lng"])
            if d <= config.VISIT_RADIUS_RANDOM_M:
                out.append(Candidate(c.id, "random_point", None, c.origin.get("location_id"), d))
        in_range = [(haversine_m(lat, lng, p["lat"], p["lng"]), p) for p in c.stops]
        in_range = [(d, p) for d, p in in_range if d <= radius_m(p)]
        if in_range:
            d, p = min(in_range, key=lambda x: (x[0], x[1]["id"]))
            out.append(Candidate(c.id, "course_place", p["id"], None, d))
    return out
