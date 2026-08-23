"""FastAPI application: router registration and domain-error mapping."""

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.errors import DomainError
from app.routers import auth, bills, products, register, users

logger = logging.getLogger("tulsi")

app = FastAPI(
    title="Tulsi Tiffins POS",
    version="1.0.0",
    description="Café POS + inventory. Every sale is one atomic transaction.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(products.router)
app.include_router(register.router)
app.include_router(bills.router)

# Uploaded product photos. Served read-only from the media volume; every file in
# here was re-encoded by services/media.py, so nothing user-supplied is executed.
Path(settings.media_root).mkdir(parents=True, exist_ok=True)
app.mount(
    settings.media_url_prefix,
    StaticFiles(directory=settings.media_root),
    name="media",
)


@app.exception_handler(DomainError)
def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
    """Services raise domain errors; they become HTTP here (NFR-13)."""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(IntegrityError)
def handle_integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
    """Last line of defence. If the `stock >= 0` CHECK ever fires, the sale is
    rejected rather than surfacing a 500 (TR-01)."""
    message = str(exc.orig)
    if "ck_products_stock_non_negative" in message:
        logger.error("stock CHECK constraint fired — a write bypassed billing service")
        return JSONResponse(
            status_code=409,
            content={"detail": "Insufficient stock: that item just sold out."},
        )
    logger.exception("integrity error")
    return JSONResponse(
        status_code=409, content={"detail": "That change conflicts with existing data."}
    )


@app.get("/api/health", tags=["ops"])
def health() -> dict[str, str]:
    return {"status": "ok"}
