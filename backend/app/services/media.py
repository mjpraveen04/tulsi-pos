"""Product photo storage.

File upload is the one place a POS lets an outsider's bytes onto the server, so
nothing here trusts the request:

- the browser's `content-type` and `filename` are both ignored;
- the bytes must actually decode as an image, via Pillow;
- the image is **re-encoded** from the decoded pixels, which drops EXIF and
  neutralises polyglot files (a valid PNG that is also a valid script);
- only PNG/JPEG/WebP are accepted — never SVG, which can carry script and would
  run same-origin when served back;
- the stored name is a UUID we generate, so a crafted filename can't traverse
  out of the media directory.
"""

import uuid
from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app.config import settings
from app.errors import ValidationError

# Pillow format name -> (extension, save format)
ALLOWED_FORMATS = {
    "PNG": ("png", "PNG"),
    "JPEG": ("jpg", "JPEG"),
    "WEBP": ("webp", "WEBP"),
}

PRODUCTS_DIR = "products"


def _media_dir() -> Path:
    path = Path(settings.media_root) / PRODUCTS_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_product_photo(raw: bytes) -> str:
    """Validate, normalise and store an uploaded image. Returns its URL path."""
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

    extension, save_format = ALLOWED_FORMATS[image.format]

    # A menu card is ~160px wide; anything above this is wasted bandwidth on a
    # tablet over café wifi.
    image.thumbnail((settings.photo_max_edge, settings.photo_max_edge))

    if save_format == "JPEG" and image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    filename = f"{uuid.uuid4().hex}.{extension}"
    destination = _media_dir() / filename
    image.save(destination, format=save_format, optimize=True)

    return f"{settings.media_url_prefix}/{PRODUCTS_DIR}/{filename}"


def delete_product_photo(photo_url: str | None) -> None:
    """Remove a previously stored photo. Silent when there's nothing to remove.

    Only ever deletes inside the media directory, and only a file this module
    could have written, so a doctored `photo_url` cannot delete anything else.
    """
    if not photo_url:
        return

    expected_prefix = f"{settings.media_url_prefix}/{PRODUCTS_DIR}/"
    if not photo_url.startswith(expected_prefix):
        return

    name = photo_url[len(expected_prefix) :]
    if "/" in name or "\\" in name or name in ("", ".", ".."):
        return

    target = _media_dir() / name
    try:
        # resolve() collapses any traversal; confirm it really landed inside.
        if target.resolve().parent == _media_dir().resolve():
            target.unlink(missing_ok=True)
    except OSError:
        # A photo we cannot delete is not worth failing the request over.
        pass
