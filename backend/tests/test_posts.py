"""Photo posts, feed, likes, comments, photo map (tasks/prd-random-jeju-merge.md US-020, US-022, US-024,
US-026, US-027). Offline: Pillow-made images, a fake store and fake Storage, local HS256 tokens."""
from __future__ import annotations

import copy
import io
import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import auth, config, main, photos, store
from app.errors import ApiError

SECRET = "test-secret-at-least-32-bytes-long!!"
ORIENTATION = 0x0112
GPS_IFD = 0x8825
# What Pillow's exif_transpose does for each orientation, and the operation that undoes it.
UNDO = {1: None, 2: Image.Transpose.FLIP_LEFT_RIGHT, 3: Image.Transpose.ROTATE_180, 4: Image.Transpose.FLIP_TOP_BOTTOM,
        5: Image.Transpose.TRANSPOSE, 6: Image.Transpose.ROTATE_90, 7: Image.Transpose.TRANSVERSE,
        8: Image.Transpose.ROTATE_270}


def upright() -> Image.Image:
    """60x40, white, with a red block in the top-left corner: any wrong turn or flip moves the block."""
    img = Image.new("RGB", (60, 40), "white")
    img.paste((220, 20, 20), (0, 0, 20, 12))
    return img


def jpeg_with_orientation(orientation: int, gps: bool = False) -> bytes:
    img = upright()
    if UNDO[orientation] is not None:
        img = img.transpose(UNDO[orientation])        # the camera stored it this way and wrote the tag
    exif = Image.Exif()
    exif[ORIENTATION] = orientation
    if gps:
        exif[0x010F] = "TestCam"                      # Make
        exif.get_ifd(GPS_IFD)[2] = (33.0, 30.0, 0.0)  # GPSLatitude
    out = io.BytesIO()
    img.save(out, "JPEG", quality=95, exif=exif)
    return out.getvalue()


def is_red(px) -> bool:
    return px[0] > 150 and px[1] < 90 and px[2] < 90


# --- FR-12 image processing -------------------------------------------------------------------------------
@pytest.mark.parametrize("orientation", range(1, 9))
def test_every_orientation_comes_out_upright(orientation):
    out = photos.process_image(jpeg_with_orientation(orientation))
    photo = Image.open(io.BytesIO(out.photo))
    assert photo.size == (60, 40)
    assert is_red(photo.getpixel((3, 3))) and not is_red(photo.getpixel((56, 36)))
    thumb = Image.open(io.BytesIO(out.thumb))
    assert thumb.size == (config.THUMB_EDGE, config.THUMB_EDGE)
    # the thumbnail is a centre crop of the upright photo: the left edge stays left, the top stays top
    assert is_red(thumb.getpixel((5, 5)))


def test_no_exif_survives():
    out = photos.process_image(jpeg_with_orientation(6, gps=True))
    for data in (out.photo, out.thumb):
        img = Image.open(io.BytesIO(data))
        assert len(img.getexif()) == 0 and "exif" not in img.info


def test_big_photos_are_shrunk(monkeypatch):
    monkeypatch.setattr(config, "PHOTO_MAX_EDGE", 32)
    out = photos.process_image(jpeg_with_orientation(1))
    assert max(Image.open(io.BytesIO(out.photo)).size) == 32


def test_png_with_transparency_becomes_jpeg():
    img = Image.new("RGBA", (30, 30), (0, 0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    out = photos.process_image(buf.getvalue())
    assert Image.open(io.BytesIO(out.photo)).format == "JPEG"


@pytest.mark.parametrize("data", [b"not an image at all", b"GIF89a" + b"\0" * 20])
def test_not_a_photo_is_415(data):
    with pytest.raises(ApiError) as e:
        photos.process_image(data)
    assert e.value.status_code == 415


def test_gif_is_415():
    buf = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buf, "GIF")
    with pytest.raises(ApiError) as e:
        photos.process_image(buf.getvalue())
    assert e.value.status_code == 415


def test_too_many_pixels_is_413(monkeypatch):
    monkeypatch.setattr(config, "PHOTO_MAX_PIXELS", 1000)
    with pytest.raises(ApiError) as e:
        photos.process_image(jpeg_with_orientation(1))
    assert e.value.status_code == 413


@pytest.mark.parametrize("value,want", [
    ("2026-11-20T14:03:00+09:00", "2026-11-20T14:03:00+09:00"),
    ("2026-11-20T05:03:00Z", "2026-11-20T14:03:00+09:00"),
    ("2026-11-20T05:03:00+00:00", "2026-11-20T14:03:00+09:00"),
    ("2026-11-20T14:03:00", "2026-11-20T14:03:00+09:00"),
    ("2026:11:20 14:03:00", None),
    ("", None), (None, None),
])
def test_taken_at_is_korea_time(value, want):
    got = photos.taken_at_kst(value)
    assert (got.isoformat() if got else None) == want


def test_public_url_and_coord():
    assert photos.public_url("https://x/y.jpg") == "https://x/y.jpg"
    assert photos.public_url("photos/a.jpg").endswith("/storage/v1/object/public/photos/a.jpg")
    assert photos.public_url(None) is None
    assert photos.public_coord(33.456789) == 33.457 and photos.public_coord(None) is None


# --- API ---------------------------------------------------------------------------------------------------
class FakeStore:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.removed: list[str] = []
        self.posts: list[dict] = []
        self.likes: set[tuple[str, str]] = set()
        self.comments: list[dict] = []
        self.users = {}
        self.fail_post = False
        self.recent_uploads = 0

    def upload_file(self, bucket, name, data):
        self.files[f"{bucket}/{name}"] = data
        return f"{bucket}/{name}"

    def remove_files(self, paths): self.removed += paths
    def uploads_since(self, user_id, since): return self.recent_uploads

    def create_photo_post(self, a):
        if self.fail_post:
            raise RuntimeError("db down")
        pid = str(uuid.uuid4())
        self.posts.insert(0, {"post_id": pid, "user_id": a["p_user"], "nickname": None,
                              "created_at": datetime.now(timezone.utc).isoformat(), "content": a["p_content"] or None,
                              "category": a["p_category"], "file_path": a["p_file_path"], "thumb_path": a["p_thumb_path"],
                              "lat": a["p_lat"], "lng": a["p_lng"], "like_count": 0, "comment_count": 0,
                              "_args": a})
        return {"post_id": pid, "photo_id": len(self.posts)}

    def feed(self, category, before, before_id, limit, post_id=None):
        rows = [p for p in self.posts if (post_id is None or p["post_id"] == post_id)
                and (category is None or p["category"] == category)]
        rows.sort(key=lambda p: (p["created_at"], p["post_id"]), reverse=True)
        if before:
            rows = [p for p in rows if (p["created_at"], p["post_id"]) < (before, before_id)]
        return copy.deepcopy(rows[:limit])

    def liked_post_ids(self, user_id, ids): return {p for (p, u) in self.likes if u == user_id and p in ids}

    def toggle_like(self, post_id, user_id):
        key = (post_id, user_id)
        liked = key not in self.likes
        (self.likes.add if liked else self.likes.discard)(key)
        return {"liked": liked, "like_count": sum(1 for p, _ in self.likes if p == post_id)}

    def list_comments(self, post_id, limit): return [c for c in self.comments if c["post_id"] == post_id][:limit]

    def add_comment(self, post_id, user_id, content):
        c = {"id": str(uuid.uuid4()), "post_id": post_id, "user_id": user_id, "content": content,
             "created_at": datetime.now(timezone.utc).isoformat()}
        self.comments.append(c)
        return c

    def nicknames(self, ids): return {i: self.users.get(i) for i in ids}
    def photos_in_bbox(self, box, limit):
        return [{"photo_id": 1, "post_id": "p", "lat": 33.456789, "lng": 126.512345, "thumb_path": "thumbnails/a.jpg"}]
    def photo_clusters(self, box):
        return [{"admin_area_id": 2, "name": "애월읍", "count": 3, "lat": 33.46, "lng": 126.33,
                 "thumb_path": "https://old/full.jpg", "south": 33.38812, "west": 126.3111, "north": 33.4611,
                 "east": 126.44849}]


def token(sub: str) -> dict:
    t = jwt.encode({"sub": sub, "role": "authenticated", "aud": "authenticated", "exp": int(time.time()) + 3600,
                    "is_anonymous": True}, SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture()
def fake(monkeypatch):
    fs = FakeStore()
    monkeypatch.setattr(store, "_store", fs)
    monkeypatch.setattr(auth, "_verifier", auth.TokenVerifier(secret=SECRET))
    return fs


@pytest.fixture()
def client(fake):
    with TestClient(main.app) as c:
        yield c


def post(client, user, meta: Optional[dict] = None, data: Optional[bytes] = None):
    meta = {"category": "관광", "content": "노을", **(meta or {})}
    return client.post("/posts", headers=token(user) if user else {},
                       files={"image": ("a.jpg", data or jpeg_with_orientation(6, gps=True), "image/jpeg")},
                       data={"meta": json.dumps(meta, ensure_ascii=False)})


def test_post_a_photo(client, fake):
    me = str(uuid.uuid4())
    r = post(client, me, {"lat": 33.456789, "lng": 126.512345, "location_source": "exif",
                          "taken_at": "2026-11-20T05:03:00Z", "content": "  노을이 예뻤어요  "})
    assert r.status_code == 201, r.text
    body = r.json()
    p = body["post"]
    assert body["visit"] is None and p["is_mine"] is True and p["category"] == "관광"
    assert p["content"] == "노을이 예뻤어요"
    assert (p["lat"], p["lng"]) == (33.457, 126.512)                  # FR-13a: rounded on the way out
    assert p["image_url"].endswith(".jpg") and "/thumbnails/" in p["thumb_url"]
    args = fake.posts[0]["_args"]
    assert args["p_lat"] == 33.456789                                  # stored exactly (for check-ins)
    assert args["p_image_time"] == "2026-11-20T14:03:00+09:00" and args["p_user"] == me
    assert len(fake.files) == 2 and all(len(Image.open(io.BytesIO(b)).getexif()) == 0 for b in fake.files.values())


def test_post_needs_a_token(client):
    assert post(client, None).status_code == 401


@pytest.mark.parametrize("meta,code", [
    ({"category": "여행"}, "INVALID_CATEGORY"),
    ({"content": "x" * 501}, "INVALID_CONTENT"),
    ({"lat": 33.4}, "INVALID_LOCATION"),
    ({"lat": 33.4, "lng": 126.5}, "INVALID_LOCATION"),
    ({"lat": 33.4, "lng": 126.5, "location_source": "gps"}, "INVALID_LOCATION"),
    ({"lat": 133.4, "lng": 126.5, "location_source": "exif"}, "INVALID_LOCATION"),
])
def test_bad_meta_is_422(client, meta, code):
    r = post(client, str(uuid.uuid4()), meta)
    assert r.status_code == 422 and r.json()["detail"]["code"] == code


def test_meta_must_be_json(client):
    r = client.post("/posts", headers=token(str(uuid.uuid4())),
                    files={"image": ("a.jpg", jpeg_with_orientation(1), "image/jpeg")}, data={"meta": "{nope"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "INVALID_META"


def test_not_an_image_is_415(client):
    r = post(client, str(uuid.uuid4()), data=b"hello")
    assert r.status_code == 415 and r.json()["detail"]["code"] == "UNSUPPORTED_IMAGE"


def test_too_big_file_is_413(client, monkeypatch):
    monkeypatch.setattr(config, "PHOTO_MAX_BYTES", 100)
    r = post(client, str(uuid.uuid4()))
    assert r.status_code == 413 and r.json()["detail"]["code"] == "FILE_TOO_LARGE"


def test_daily_limit_is_429(client, fake):
    fake.recent_uploads = config.UPLOADS_PER_DAY
    r = post(client, str(uuid.uuid4()))
    assert r.status_code == 429 and r.json()["detail"]["code"] == "UPLOAD_LIMIT"


def test_db_failure_removes_the_uploaded_files(client, fake):
    fake.fail_post = True
    r = post(client, str(uuid.uuid4()))
    assert r.status_code == 502 and r.json()["detail"]["code"] == "UPLOAD_FAILED"
    assert sorted(fake.removed) == sorted(fake.files)


def test_feed_pages_and_filters(client, fake):
    me = str(uuid.uuid4())
    for i in range(5):
        post(client, me, {"category": "카페" if i % 2 else "관광", "content": f"#{i}"})
    first = client.get("/posts?limit=2").json()
    assert len(first["posts"]) == 2 and first["next_cursor"]
    second = client.get(f"/posts?limit=2&cursor={first['next_cursor']}").json()
    third = client.get(f"/posts?limit=2&cursor={second['next_cursor']}").json()
    ids = [p["post_id"] for p in first["posts"] + second["posts"] + third["posts"]]
    assert len(set(ids)) == 5 and third["next_cursor"] is None
    cafes = client.get("/posts?category=카페").json()["posts"]
    assert len(cafes) == 2 and all(p["category"] == "카페" for p in cafes)
    assert all(p["is_liked"] is False and p["is_mine"] is False for p in first["posts"])   # no token: still readable


def test_feed_rejects_bad_category_and_cursor(client):
    assert client.get("/posts?category=여행").json()["detail"]["code"] == "INVALID_CATEGORY"
    assert client.get("/posts?cursor=garbage").json()["detail"]["code"] == "INVALID_CURSOR"


def test_like_toggles_and_shows_in_the_feed(client, fake):
    me = str(uuid.uuid4())
    pid = post(client, me).json()["post"]["post_id"]
    assert client.post(f"/posts/{pid}/like", headers=token(me)).json() == {"liked": True, "like_count": 1}
    assert client.get("/posts", headers=token(me)).json()["posts"][0]["is_liked"] is True
    assert client.post(f"/posts/{pid}/like", headers=token(me)).json() == {"liked": False, "like_count": 0}
    assert client.post(f"/posts/{pid}/like").status_code == 401
    assert client.post(f"/posts/{uuid.uuid4()}/like", headers=token(me)).status_code == 404
    assert client.post("/posts/not-a-uuid/like", headers=token(me)).status_code == 404


def test_comments(client, fake):
    me, other = str(uuid.uuid4()), str(uuid.uuid4())
    fake.users[me] = "귤좋아"
    pid = post(client, other).json()["post"]["post_id"]
    r = client.post(f"/posts/{pid}/comments", json={"content": "  멋져요  "}, headers=token(me))
    assert r.status_code == 201 and r.json()["content"] == "멋져요" and r.json()["author"]["nickname"] == "귤좋아"
    listed = client.get(f"/posts/{pid}/comments").json()["comments"]
    assert [c["content"] for c in listed] == ["멋져요"] and listed[0]["author"]["tag"] == me.replace("-", "")[:4]
    for bad in ("", "   ", "x" * 501):
        r = client.post(f"/posts/{pid}/comments", json={"content": bad}, headers=token(me))
        assert r.status_code == 422 and r.json()["detail"]["code"] == "INVALID_COMMENT"
    assert client.post(f"/posts/{pid}/comments", json={"content": "hi"}).status_code == 401
    assert client.get(f"/posts/{uuid.uuid4()}/comments").status_code == 404


def test_photo_map_rounds_and_validates(client):
    m = client.get("/photos/map?min_lat=33&min_lng=126&max_lat=34&max_lng=127").json()["photos"][0]
    assert (m["lat"], m["lng"]) == (33.457, 126.512) and m["thumb_url"].endswith("thumbnails/a.jpg")
    c = client.get("/photos/clusters?min_lat=33&min_lng=126&max_lat=34&max_lng=127").json()["clusters"][0]
    assert c["name"] == "애월읍" and c["thumb_url"] == "https://old/full.jpg"
    assert c["extent"] == {"south": 33.388, "west": 126.311, "north": 33.461, "east": 126.448}
    for q in ("", "min_lat=34&min_lng=126&max_lat=33&max_lng=127", "min_lat=33&min_lng=126&max_lat=34"):
        r = client.get(f"/photos/map?{q}")
        assert r.status_code == 422 and r.json()["detail"]["code"] == "INVALID_BBOX"
