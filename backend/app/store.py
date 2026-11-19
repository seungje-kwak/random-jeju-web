"""Data access. Supabase only: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in backend/.env.

The store returns plain dicts:
  place        -> PRD 9.3 `Place` (with nested accessibility / food_options)
  course row   -> {id, user_profile, tier, created_at, meal_gaps}
  item row     -> {course_id, order, place_id, start_time, stay_min, move_method, move_min,
                   reason_en, is_rest_stop, status}
"""
from __future__ import annotations

import copy
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional, Protocol

from . import areas, config

log = logging.getLogger("mypace.store")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class Store(Protocol):
    def list_places(self) -> list[dict]: ...
    def list_areas(self) -> list[dict]: ...
    def list_phrase_cards(self) -> list[dict]: ...
    def get_course(self, course_id: str) -> Optional[dict]: ...
    def get_items(self, course_id: str) -> list[dict]: ...
    def create_course(self, course: dict, items: list[dict]) -> None: ...
    def apply_replan(self, course_id: str, user_profile: dict, statuses: dict[int, str],
                     delete_orders: list[int], new_items: list[dict], report_place_id: Optional[int],
                     meal_gaps: Optional[list[dict]] = None) -> None: ...
    def set_tier(self, course_id: str, tier: str) -> None: ...
    def add_report(self, place_id: int, type_: str) -> dict: ...
    def replace_course(self, course: dict, items: list[dict]) -> None: ...
    def get_user(self, user_id: str) -> Optional[dict]: ...
    def save_nickname(self, user_id: str, nickname: str) -> dict: ...
    def draw_point(self) -> Optional[dict]: ...
    def add_location(self, row: dict) -> dict: ...
    def get_location(self, location_id: int) -> Optional[dict]: ...
    def link_location(self, location_id: int, course_id: str) -> None: ...
    # photo posts (FR-11 - FR-18)
    def upload_file(self, bucket: str, name: str, data: bytes) -> str: ...
    def remove_files(self, paths: list[str]) -> None: ...
    def uploads_since(self, user_id: str, since_utc: str) -> int: ...
    def create_photo_post(self, args: dict) -> dict: ...
    def feed(self, category: Optional[str], before: Optional[str], before_id: Optional[str], limit: int,
             post_id: Optional[str] = None) -> list[dict]: ...
    def liked_post_ids(self, user_id: str, post_ids: list[str]) -> set[str]: ...
    def toggle_like(self, post_id: str, user_id: str) -> dict: ...
    def list_comments(self, post_id: str, limit: int) -> list[dict]: ...
    def add_comment(self, post_id: str, user_id: str, content: str) -> dict: ...
    def nicknames(self, user_ids: list[str]) -> dict[str, Optional[str]]: ...
    def photos_in_bbox(self, box: dict, limit: int) -> list[dict]: ...
    def photo_clusters(self, box: dict) -> list[dict]: ...


# ---------------------------------------------------------------------------
class SupabaseStore:
    """Tables from sql/schema.sql. Writes happen only after the planner succeeded (10.7 step 5)."""

    PLACE_TTL_SEC = 60
    PAGE_SIZE = 1000

    def __init__(self) -> None:
        import httpx
        from supabase import ClientOptions, create_client  # imported lazily so local mode needs no network

        # One HTTP/1.1 pool for PostgREST and Storage. supabase-py's default is one shared HTTP/2 connection;
        # FastAPI runs these sync calls on several threads, and two requests at once on that connection made
        # Supabase drop it ("Server disconnected", seen 2026-11-19 on GET /posts/{id}/comments). httpx's
        # HTTP/1.1 pool is safe across threads; `retries` re-opens a connection that failed to connect.
        http = httpx.Client(http2=False, timeout=httpx.Timeout(30.0, connect=10.0),
                            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10, keepalive_expiry=30),
                            transport=httpx.HTTPTransport(retries=2))
        self._sb = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY,
                                 options=ClientOptions(httpx_client=http))
        self._places_cache: tuple[float, list[dict]] | None = None
        self._cards_cache: tuple[float, list[dict]] | None = None
        self._areas_cache: tuple[float, list[dict]] | None = None

    @staticmethod
    def _one(v: Any) -> Optional[dict]:
        if isinstance(v, list):
            return v[0] if v else None
        return v

    def list_places(self) -> list[dict]:
        if self._places_cache and time.time() - self._places_cache[0] < self.PLACE_TTL_SEC:
            return copy.deepcopy(self._places_cache[1])
        # Supabase returns at most 1000 rows per request, so read the table page by page.
        rows: list[dict] = []
        while True:
            page = (self._sb.table("places")
                    .select("*, place_accessibility(*), food_options(*)")
                    .order("id").range(len(rows), len(rows) + self.PAGE_SIZE - 1).execute().data)
            rows += page
            if len(page) < self.PAGE_SIZE:
                break
        places = []
        for r in rows:
            acc = self._one(r.pop("place_accessibility", None))
            food = self._one(r.pop("food_options", None))
            if acc is None:  # 8.10: every place must have an accessibility row
                continue
            acc.pop("place_id", None)
            if food:
                food.pop("place_id", None)
            r["closed_days"] = r.get("closed_days") or []
            # A database without the places.area_id column yet: work the area out from the address.
            r["area_id"] = r.get("area_id") or areas.area_of_address(r["address_ko"]) or config.DEFAULT_AREA_ID
            r["accessibility"] = acc
            r["food_options"] = food
            places.append(r)
        self._places_cache = (time.time(), places)
        return copy.deepcopy(places)

    def list_areas(self) -> list[dict]:
        if self._areas_cache and time.time() - self._areas_cache[0] < self.PLACE_TTL_SEC:
            return copy.deepcopy(self._areas_cache[1])
        try:
            rows = self._sb.table("areas").select("*").order("sort_order").execute().data
        except Exception as e:  # the table is made by sql/schema.sql; an older database does not have it
            log.warning("areas table not readable (%s); using app/data/areas.json", e)
            rows = []
        rows = rows or areas.load_seed_areas()
        self._areas_cache = (time.time(), rows)
        return copy.deepcopy(rows)

    def list_phrase_cards(self) -> list[dict]:
        if self._cards_cache and time.time() - self._cards_cache[0] < self.PLACE_TTL_SEC:
            return copy.deepcopy(self._cards_cache[1])
        rows = self._sb.table("phrase_cards").select("*").execute().data
        self._cards_cache = (time.time(), rows)
        return copy.deepcopy(rows)

    def get_course(self, course_id: str) -> Optional[dict]:
        try:
            rows = self._sb.table("courses").select("*").eq("id", course_id).limit(1).execute().data
        except Exception:  # invalid uuid -> treat as not found
            return None
        return rows[0] if rows else None

    def get_items(self, course_id: str) -> list[dict]:
        rows = self._sb.table("course_items").select("*").eq("course_id", course_id).execute().data
        return sorted(rows, key=lambda i: i["order"])

    def create_course(self, course: dict, items: list[dict]) -> None:
        self._sb.table("courses").insert(course).execute()
        try:
            if items:
                self._sb.table("course_items").insert(items).execute()
        except Exception:
            # no half-written course (US-02)
            self._sb.table("courses").delete().eq("id", course["id"]).execute()
            raise

    def replace_course(self, course: dict, items: list[dict]) -> None:
        self._sb.table("course_items").delete().eq("course_id", course["id"]).execute()
        self._sb.table("courses").upsert(course).execute()
        if items:
            self._sb.table("course_items").insert(items).execute()

    def apply_replan(self, course_id, user_profile, statuses, delete_orders, new_items, report_place_id,
                     meal_gaps=None) -> None:
        """PostgREST reads `order=` in a URL as the sort option, so rows can't be filtered by the
        "order" column (Q-05). Instead: build the full new item list, delete the course's items by
        course_id, insert the new list, and put the old rows back if the insert fails."""
        sb = self._sb
        old = self.get_items(course_id)
        kept = []
        for it in old:
            if it["order"] in delete_orders:
                continue
            row = dict(it)
            row["status"] = statuses.get(it["order"], it["status"])
            kept.append(row)
        final = sorted(kept + [dict(n) for n in new_items], key=lambda i: i["order"])

        sb.table("course_items").delete().eq("course_id", course_id).execute()
        try:
            if final:
                sb.table("course_items").insert(final).execute()
        except Exception:
            if old:
                sb.table("course_items").insert(old).execute()  # keep the previous plan (US-09)
            raise
        update = {"user_profile": user_profile}
        if meal_gaps is not None:
            update["meal_gaps"] = meal_gaps
        sb.table("courses").update(update).eq("id", course_id).execute()
        if report_place_id is not None:
            sb.table("place_reports").insert({"place_id": report_place_id, "type": "closed"}).execute()

    def set_tier(self, course_id: str, tier: str) -> None:
        self._sb.table("courses").update({"tier": tier}).eq("id", course_id).execute()

    def add_report(self, place_id: int, type_: str) -> dict:
        rows = self._sb.table("place_reports").insert({"place_id": place_id, "type": type_}).execute().data
        r = rows[0]
        return {"place_id": r["place_id"], "type": r["type"], "created_at": r["created_at"]}

    # --- users (RandomJeju table: id references auth.users, nickname, ...; FR-33) ---
    def get_user(self, user_id: str) -> Optional[dict]:
        rows = self._sb.table("users").select("id, nickname").eq("id", user_id).limit(1).execute().data
        return rows[0] if rows else None

    def save_nickname(self, user_id: str, nickname: str) -> dict:
        """Creates the row on the first nickname; later calls change only `nickname` (other columns stay)."""
        rows = (self._sb.table("users").upsert({"id": user_id, "nickname": nickname}, on_conflict="id")
                .execute().data)
        return rows[0]

    # --- random points (RandomJeju tables grids / locations; FR-1 - FR-3, FR-9) ---
    def draw_point(self) -> Optional[dict]:
        """{grid_id, lat, lng, adm_nm} from the DB function random_point(), or None when no cell is usable."""
        rows = self._sb.rpc("random_point", {}).execute().data
        return rows[0] if rows else None

    def add_location(self, row: dict) -> dict:
        return self._sb.table("locations").insert(row).execute().data[0]

    def get_location(self, location_id: int) -> Optional[dict]:
        rows = (self._sb.table("locations").select("location_id, lat, lng, address, grid_id, user_id, course_id")
                .eq("location_id", location_id).limit(1).execute().data)
        return rows[0] if rows else None

    def link_location(self, location_id: int, course_id: str) -> None:
        self._sb.table("locations").update({"course_id": course_id}).eq("location_id", location_id).execute()

    # --- photo posts, feed, likes, comments, photo map (FR-11 - FR-18; functions in 0004_posts.sql) ---
    def upload_file(self, bucket: str, name: str, data: bytes) -> str:
        """Returns the bucket-qualified path ("photos/<name>") that photos.file_path stores."""
        self._sb.storage.from_(bucket).upload(path=name, file=data,
                                              file_options={"content-type": "image/jpeg", "upsert": "false"})
        return f"{bucket}/{name}"

    def remove_files(self, paths: list[str]) -> None:
        by_bucket: dict[str, list[str]] = {}
        for p in paths:
            bucket, _, name = p.partition("/")
            by_bucket.setdefault(bucket, []).append(name)
        for bucket, names in by_bucket.items():
            self._sb.storage.from_(bucket).remove(names)

    def uploads_since(self, user_id: str, since_utc: str) -> int:
        res = (self._sb.table("photos").select("photo_id", count="exact").eq("user_id", user_id)
               .gte("timestamp", since_utc).limit(1).execute())
        return res.count or 0

    def create_photo_post(self, args: dict) -> dict:
        return self._sb.rpc("create_photo_post", args).execute().data[0]

    def feed(self, category, before, before_id, limit, post_id=None) -> list[dict]:
        return self._sb.rpc("feed_posts", {"p_category": category, "p_before": before, "p_before_id": before_id,
                                           "p_limit": limit, "p_post_id": post_id}).execute().data

    def liked_post_ids(self, user_id: str, post_ids: list[str]) -> set[str]:
        if not post_ids:
            return set()
        rows = (self._sb.table("post_likes").select("post_id").eq("user_id", user_id).in_("post_id", post_ids)
                .execute().data)
        return {r["post_id"] for r in rows}

    def toggle_like(self, post_id: str, user_id: str) -> dict:
        return self._sb.rpc("toggle_like", {"p_post": post_id, "p_user": user_id}).execute().data[0]

    def list_comments(self, post_id: str, limit: int) -> list[dict]:
        return (self._sb.table("comments").select("id, user_id, content, created_at").eq("post_id", post_id)
                .order("created_at").limit(limit).execute().data)

    def add_comment(self, post_id: str, user_id: str, content: str) -> dict:
        return self._sb.rpc("add_comment", {"p_post": post_id, "p_user": user_id, "p_content": content}).execute().data[0]

    def nicknames(self, user_ids: list[str]) -> dict[str, Optional[str]]:
        ids = sorted({u for u in user_ids if u})
        if not ids:
            return {}
        rows = self._sb.table("users").select("id, nickname").in_("id", ids).execute().data
        return {r["id"]: r.get("nickname") for r in rows}

    def photos_in_bbox(self, box: dict, limit: int) -> list[dict]:
        return self._sb.rpc("photos_in_bbox", {**box, "max_rows": limit}).execute().data

    def photo_clusters(self, box: dict) -> list[dict]:
        return self._sb.rpc("photo_clusters", box).execute().data


_store: Optional[Store] = None


def get_store() -> Store:
    global _store
    if _store is None:
        if not config.USE_SUPABASE:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set (backend/.env or Railway variables).")
        _store = SupabaseStore()
    return _store
