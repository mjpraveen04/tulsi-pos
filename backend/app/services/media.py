"""Product photo storage.

File upload is the one place a POS lets an outsider's bytes onto the server, so
nothing here trusts the request:

- the browser's `content-type` and `filename` are both ignored;
- the bytes must actually decode as an image, via Pillow;
- the image is **re-encoded** from the decoded pixels, which drops EXIF and
  neutralises polyglot files (a valid PNG that is also a valid script);
- only PNG/JPEG/WebP are accepted — never SVG, which can carry script and would
  run same-origin when served back;
- the stored name is a UUID we generate, and lookups go by that primary key,
  so a crafted filename or `photo_url` can't reach any other photo.

The bytes live in the `product_photos` table, not on disk: the free cloud host
wipes its filesystem on every restart, and a database row also commits in the
same transaction as the product's `photo_url`. Nothing here commits — the
calling service does.
"""

import re
import uuid
from io import BytesIO

from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.config import settings
from app.errors import NotFoundError, ValidationError
from app.models import ProductPhoto

# Pillow format name -> (extension, save format, content type)
ALLOWED_FORMATS = {
    "PNG": ("png", "PNG", "image/png"),
    "JPEG": ("jpg", "JPEG", "image/jpeg"),
    "WEBP": ("webp", "WEBP", "image/webp"),
}

PRODUCTS_DIR = "products"

# What a URL this module issued ends in: <32 hex>.<extension>
_PHOTO_NAME = re.compile(r"^([0-9a-f]{32})\.(png|jpg|webp)$")


def _photo_id(name: str) -> str | None:
    match = _PHOTO_NAME.match(name)
    return match.group(1) if match else None


def save_product_photo(db: Session, product_id: int, raw: bytes) -> str:
    """Validate, normalise and stage an uploaded image. Returns its URL path."""
    if not raw:
        raise ValidationError("That file is empty. Pick an image and try again.")

    if len(raw) > settings.max_photo_bytes:
        limit_mb = settings.max_photo_bytes // (1024 * 1024)
        raise ValidationError(f"That image is larger than {limit_mb} MB. Pick a smaller one.")

    try:
        image = Image.open(BytesIO(raw))
        image.verify()  # cheap structural check; consumes the file object
        image = Image.open(BytesIO(raw))  # reopen — verify() leaves it unusable
        image.load()
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValidationError(
            "That file isn't a picture we can read. Use a PNG, JPG or WebP."
        ) from None

    if image.format not in ALLOWED_FORMATS:
        raise ValidationError(
            f"{image.format or 'That format'} isn't supported. Use a PNG, JPG or WebP."
        )

    extension, save_format, content_type = ALLOWED_FORMATS[image.format]

    # A menu card is ~160px wide; anything above this is wasted bandwidth on a
    # tablet over café wifi.
    image.thumbnail((settings.photo_max_edge, settings.photo_max_edge))

    if save_format == "JPEG" and image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    buffer = BytesIO()
    image.save(buffer, format=save_format, optimize=True)

    photo_id = uuid.uuid4().hex
    db.add(
        ProductPhoto(
            id=photo_id,
            product_id=product_id,
            content_type=content_type,
            data=buffer.getvalue(),
        )
    )
    return f"{settings.media_url_prefix}/{PRODUCTS_DIR}/{photo_id}.{extension}"


def get_product_photo(db: Session, name: str) -> ProductPhoto:
    """Look up a stored photo by the file name in its URL."""
    photo_id = _photo_id(name)
    photo = db.get(ProductPhoto, photo_id) if photo_id else None
    if photo is None:
        raise NotFoundError("Photo not found")
    return photo


def delete_product_photo(db: Session, photo_url: str | None) -> None:
    """Stage removal of a previously stored photo. Silent when there's nothing to remove.

    Only a URL this module could have issued maps to a row, so a doctored
    `photo_url` cannot delete anything else.
    """
    if not photo_url:
        return

    expected_prefix = f"{settings.media_url_prefix}/{PRODUCTS_DIR}/"
    if not photo_url.startswith(expected_prefix):
        return

    photo_id = _photo_id(photo_url[len(expected_prefix) :])
    photo = db.get(ProductPhoto, photo_id) if photo_id else None
    if photo is not None:
        db.delete(photo)
