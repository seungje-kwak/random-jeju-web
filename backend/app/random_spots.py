"""Random points (tasks/prd-random-jeju-merge.md FR-0 - FR-3).

The point itself comes from the DB function random_point() (a uniform point on the land part of one usable
grid cell). This module decides which cells are usable (FR-0) and what to show under a fresh point (FR-3).
The course built from a point is planner.random_course (FR-4 - FR-8).
"""
from __future__ import annotations

import math
import time
from typing import Optional

from . import areas, config, planner

CATEGORIES = ("nature", "market", "cafe", "food", "culture", "photo")


def selectable_areas(area_rows: list[dict], places: list[dict]) -> set[str]:
    """The areas GET /areas lets a traveler pick (not "Coming soon")."""
    return {a["id"] for a in areas.summaries(area_rows, places) if a["selectable"]}


def _plain_ctx() -> planner.TripCtx:
    """A traveler with every interest and no meal to fit: hubs that depend only on where places are."""
    return planner.TripCtx(profile={"interests": list(CATEGORIES)}, start_min=0, end_min=24 * 60,
                           min_items=1, max_items=1, meals=[])


def plain_hubs(places: list[dict], selectable: set[str]) -> list[tuple[planner.Hub, str]]:
    """(hub, area_id) for every selectable area, found the way the planner finds them (find_hubs)."""
    out = []
    for area_id in sorted(selectable):
        pool = planner.in_area(places, area_id)
        out.extend((h, area_id) for h in planner.find_hubs(pool, _plain_ctx()))
    return out


_hub_cache: Optional[tuple[float, list[tuple[planner.Hub, str]]]] = None


def cached_plain_hubs(places: list[dict], selectable: set[str]) -> list[tuple[planner.Hub, str]]:
    """plain_hubs, recomputed at most once a minute (the store caches places for the same time)."""
    global _hub_cache
    if _hub_cache is None or time.time() - _hub_cache[0] > 60:
        _hub_cache = (time.time(), plain_hubs(places, selectable))
    return _hub_cache[1]


def dense_places(places: list[dict], selectable: set[str]) -> list[dict]:
    """FR-0 (c): places in a selectable area with HUB_MIN_PLACES or more places of that area within
    ANCHOR_RADIUS_KM (the same density a hub needs)."""
    out = []
    for area_id in sorted(selectable):
        pool = planner.in_area(places, area_id)
        for c in pool:
            near = sum(1 for p in pool if planner.km_between(c, p) <= config.ANCHOR_RADIUS_KM)
            if near >= config.HUB_MIN_PLACES:
                out.append(c)
    return out


def skip_reason(cell: dict, dense: list[dict], selectable: set[str]) -> Optional[str]:
    """FR-0: why a grid cell is not drawn, or None when it is usable.
    `cell`: {land_share, land_lat, land_lng}. `dense`: dense_places()."""
    if cell.get("land_lat") is None or (cell.get("land_share") or 0) < config.GRID_MIN_LAND_SHARE:
        return "mostly_sea"
    point = {"lat": cell["land_lat"], "lng": cell["land_lng"]}
    if areas.area_of_point(point["lat"], point["lng"]) not in selectable:
        return "area_not_ready"
    if not any(planner.km_between(point, d) <= config.GRID_REACH_KM for d in dense):
        return "far_from_places"
    return None


def nearby(point: dict, places: list[dict], hubs: list[tuple[planner.Hub, str]]) -> dict:
    """FR-3: the closest plain hub (and its area) and up to PREVIEW_COUNT places within PREVIEW_RADIUS_KM,
    places with a photo first, then the closest."""
    nearest = min(hubs, key=lambda h: planner.km_between(point, h[0].place), default=None)
    near = [(planner.km_between(point, p), p) for p in places]
    near = [(km, p) for km, p in near if km <= config.PREVIEW_RADIUS_KM]
    near.sort(key=lambda x: (not x[1].get("image_url"), x[0], x[1]["id"]))
    return {
        "area_id": nearest[1] if nearest else None,
        "nearest_hub": None if nearest is None else {
            "place_id": nearest[0].place["id"], "name_ko": nearest[0].place["name_ko"],
            "name_en": nearest[0].place["name_en"], "km": round_km(planner.km_between(point, nearest[0].place)),
        },
        "preview_places": [
            {"id": p["id"], "name_ko": p["name_ko"], "name_en": p["name_en"], "category": p["category"],
             "image_url": p.get("image_url"), "km": round_km(km)}
            for km, p in near[: config.PREVIEW_COUNT]
        ],
    }


def round_km(km: float) -> float:
    return math.floor(km * 10 + 0.5) / 10
