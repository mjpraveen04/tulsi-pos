from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Product, User
from app.schemas.product import (
    ProductCreate,
    ProductOut,
    ProductUpdate,
    StockAdjustRequest,
    StockMoveOut,
)
from app.security import get_current_user, require_manager
from app.services import inventory as inventory_service

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("", response_model=list[ProductOut])
def list_products(
    q: str | None = None,
    category: str | None = None,
    include_archived: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Product]:
    """Readable by any signed-in user — the Register grid needs it."""
    return inventory_service.list_products(db, q, category, include_archived)


@router.get("/stock-moves", response_model=list[StockMoveOut])
def list_stock_moves(
    limit: int = Query(default=40, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
) -> list[StockMoveOut]:
    """The Inventory activity feed, straight off the ledger (NFR-18)."""
    return [
        StockMoveOut(
            id=move.id,
            product_id=move.product_id,
            product_name=move.product.name,
            delta=move.delta,
            reason=move.reason,
            bill_id=move.bill_id,
            bill_no=move.bill.bill_no if move.bill else None,
            user_id=move.user_id,
            user_name=move.user.name,
            created_at=move.created_at,
        )
        for move in inventory_service.list_stock_moves(db, limit)
    ]


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
) -> Product:
    return inventory_service.create_product(db, payload, current_user)


@router.patch("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
) -> Product:
    return inventory_service.update_product(db, product_id, payload)


@router.patch("/{product_id}/archive", response_model=ProductOut)
def archive_product(
    product_id: int,
    archived: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
) -> Product:
    return inventory_service.set_archived(db, product_id, archived)


@router.post("/{product_id}/photo", response_model=ProductOut)
async def upload_photo(
    product_id: int,
    file: UploadFile = File(..., description="PNG, JPG or WebP"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
) -> Product:
    """Attach a photo to a menu item. The service validates the bytes."""
    raw = await file.read()
    return inventory_service.set_photo(db, product_id, raw)


@router.delete("/{product_id}/photo", response_model=ProductOut)
def delete_photo(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
) -> Product:
    return inventory_service.clear_photo(db, product_id)


@router.post("/{product_id}/stock", response_model=ProductOut)
def adjust_stock(
    product_id: int,
    payload: StockAdjustRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
) -> Product:
    return inventory_service.adjust_stock(db, product_id, payload, current_user)
