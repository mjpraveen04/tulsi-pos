from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.services import media as media_service

router = APIRouter(prefix=settings.media_url_prefix, tags=["media"])


@router.get("/products/{name}")
def product_photo(name: str, db: Session = Depends(get_db)) -> Response:
    """Serve a stored product photo.

    Public, as the static mount it replaces was: `<img>` tags cannot send a
    bearer token. Every image here was re-encoded on upload, and the names are
    unguessable UUIDs.
    """
    photo = media_service.get_product_photo(db, name)
    return Response(
        content=photo.data,
        media_type=photo.content_type,
        # A photo URL is never reused for different bytes, so it can be cached hard.
        headers={"Cache-Control": "public, max-age=604800, immutable"},
    )
