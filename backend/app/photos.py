"""Photo files for posts (tasks/prd-random-jeju-merge.md FR-11, FR-12, FR-13a).

process_image() turns an upload into the two files that are stored: the photo (upright, at most
PHOTO_MAX_EDGE px on its long edge, JPEG) and a square thumbnail. Neither keeps any EXIF data, so the
GPS position and the camera never leave through the public URLs. The old server always rotated
thumbnails 90 degrees; here the EXIF orientation is applied once and then dropped.
"""
from __future__ import annotations

import io
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from PIL import Image, ImageOps, UnidentifiedImageError

from . import config
from .errors import ApiError

ACCEPTED_FORMATS = {"JPEG", "PNG", "WEBP"}
KST = timezone(timedelta(hours=9))
Image.MAX_IMAGE_PIXELS = config.PHOTO_MAX_PIXELS   # larger images raise DecompressionBombError


@dataclass
class Processed:
    photo: bytes
    thumb: bytes
    width: int
    height: int


def _jpeg(img: Image.Image) -> bytes:
    if img.mode not in ("RGB", "L"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode in ("RGBA", "LA") or "transparency" in img.info:
            rgba = img.convert("RGBA")
            background.paste(rgba, mask=rgba.split()[-1])
        else:
            background.paste(img.convert("RGB"))
        img = background
    out = io.BytesIO()
    img.save(out, "JPEG", quality=config.PHOTO_JPEG_QUALITY, optimize=True)   # no exif= argument: nothing kept
    return out.getvalue()


def process_image(data: bytes) -> Processed:
    """FR-12. 415 UNSUPPORTED_IMAGE for anything that is not a JPEG / PNG / WebP picture, 413 FILE_TOO_LARGE
    for more than PHOTO_MAX_PIXELS pixels."""
    if len(data) > config.PHOTO_MAX_BYTES:
        raise ApiError(413, "FILE_TOO_LARGE", "The photo is too large.")
    try:
        img = Image.open(io.BytesIO(data))
        fmt = img.format
        # Pillow itself only refuses above 2 x MAX_IMAGE_PIXELS; check the header size before decoding
        if img.width * img.height > config.PHOTO_MAX_PIXELS:
            raise ApiError(413, "FILE_TOO_LARGE", "The photo has too many pixels.")
        img.load()
    except Image.DecompressionBombError:
        raise ApiError(413, "FILE_TOO_LARGE", "The photo has too many pixels.")
    except (UnidentifiedImageError, OSError, ValueError):
        raise ApiError(415, "UNSUPPORTED_IMAGE", "Send a JPEG, PNG or WebP photo.")
    if fmt not in ACCEPTED_FORMATS:
        raise ApiError(415, "UNSUPPORTED_IMAGE", "Send a JPEG, PNG or WebP photo.")
    img = ImageOps.exif_transpose(img)          # stand it up; the result carries no orientation tag
    img.thumbnail((config.PHOTO_MAX_EDGE, config.PHOTO_MAX_EDGE), Image.Resampling.LANCZOS)
    thumb = ImageOps.fit(img, (config.THUMB_EDGE, config.THUMB_EDGE), Image.Resampling.LANCZOS)
    return Processed(_jpeg(img), _jpeg(thumb), img.width, img.height)


def public_url(path: Optional[str]) -> Optional[str]:
    """Rows made by the old server hold a full URL; new rows hold "bucket/name.jpg"."""
    if not path:
        return None
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{config.SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{path}"


def public_coord(v: Optional[float]) -> Optional[float]:
    """FR-13a: coordinates that leave the server are rounded to 3 decimals (about 100 m)."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return round(float(v), 3)


_OFFSET = re.compile(r"(Z|[+-]\d\d:?\d\d)$")


def taken_at_kst(value: Optional[str]) -> Optional[datetime]:
    """FR-11 `taken_at`: an ISO time. With an offset it is converted to Korea time; without one it is taken as
    Korea time already. Returned without a zone, as photos.image_time stores it (Q-09). Bad text: None."""
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00") if value.strip().endswith("Z") else value.strip()
    try:
        t = datetime.fromisoformat(text)
    except ValueError:
        return None
    if t.tzinfo is not None:
        t = t.astimezone(KST)
    return t.replace(tzinfo=None, microsecond=0)
