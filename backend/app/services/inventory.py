"""Products and the append-only stock ledger (FR-12…18, NFR-06).

Every change to `product.stock` in this module happens beside a `StockMove`
insert, in the same transaction. Nothing here ever UPDATEs or DELETEs a move.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import ConflictError, NotFoundError, ValidationError
from app.models import Product, StockMove, StockMoveReason, User
from app.schemas.product import ProductCreate, ProductUpdate, StockAdjustRequest
from app.services import media


def list_products(
    db: Session,
    q: str | None = None,
    category: str | None = None,
    include_archived: bool = False,
) -> list[Product]:
    stmt = select(Product)
    if not include_archived:
        stmt = stmt.where(Product.is_archived.is_(False))
    if q:
        stmt = stmt.where(Product.name.ilike(f"%{q.strip()}%"))
    if category and category.lower() != "all":
        stmt = stmt.where(Product.category == category)
    return list(db.execute(stmt.order_by(Product.category, Product.name)).scalars())


def get_product(db: Session, product_id: int) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise NotFoundError("That menu item no longer exists.")
    return product


def create_product(db: Session, payload: ProductCreate, actor: User) -> Product:
    """Creates the product and, when it opens with stock, the OPENING move that
    backs that stock in the ledger (FR-12)."""
    product = Product(
        name=payload.name.strip(),
        category=payload.category.strip(),
        price=payload.price,
        stock=0,
        reorder_level=payload.reorder_level,
        photo_url=payload.photo_url,
        is_archived=False,
    )
    db.add(product)
    db.flush()  # assign product.id without ending the transaction

    if payload.opening_stock > 0:
        db.add(
            StockMove(
                product_id=product.id,
                delta=payload.opening_stock,
                reason=StockMoveReason.OPENING,
                user_id=actor.id,
            )
        )
        product.stock = payload.opening_stock

    db.commit()
    db.refresh(product)
    return product


def update_product(db: Session, product_id: int, payload: ProductUpdate) -> Product:
    """Edits details only. Stock is never set directly — it moves through the
    ledger. Past bills keep their own `unit_price`, so a price edit here cannot
    rewrite history (FR-13/25)."""
    product = get_product(db, product_id)

    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(product, field, value.strip() if isinstance(value, str) else value)

    db.commit()
    db.refresh(product)
    return product


def set_archived(db: Session, product_id: int, archived: bool) -> Product:
    """Hides from the Register while leaving it on old bills (FR-14)."""
    product = get_product(db, product_id)
    product.is_archived = archived
    db.commit()
    db.refresh(product)
    return product


def set_photo(db: Session, product_id: int, raw: bytes) -> Product:
    """Attach an uploaded photo, replacing whatever was there before (FR-13)."""
    product = get_product(db, product_id)

    new_url = media.save_product_photo(raw)
    previous = product.photo_url
    product.photo_url = new_url
    db.commit()
    db.refresh(product)

    # Only bin the old file once the new one is safely committed.
    media.delete_product_photo(previous)
    return product


def clear_photo(db: Session, product_id: int) -> Product:
    product = get_product(db, product_id)

    previous = product.photo_url
    product.photo_url = None
    db.commit()
    db.refresh(product)

    media.delete_product_photo(previous)
    return product


def adjust_stock(
    db: Session, product_id: int, payload: StockAdjustRequest, actor: User
) -> Product:
    """One-tap receive/remove: ledger row + cached stock, one transaction (FR-15)."""
    if payload.reason not in (StockMoveReason.RECEIVE, StockMoveReason.REMOVE):
        raise ValidationError("Stock adjustments must be RECEIVE or REMOVE.")

    # Lock the row so a concurrent sale can't slip between the check and the write.
    product = db.execute(
        select(Product).where(Product.id == product_id).with_for_update()
    ).scalar_one_or_none()
    if product is None:
        raise NotFoundError("That menu item no longer exists.")

    delta = payload.signed_delta()
    new_stock = product.stock + delta
    if new_stock < 0:
        raise ConflictError(
            f"Can't remove {payload.delta} — only {product.stock} in stock."
        )

    db.add(
        StockMove(
            product_id=product.id,
            delta=delta,
            reason=payload.reason,
            user_id=actor.id,
        )
    )
    product.stock = new_stock

    db.commit()
    db.refresh(product)
    return product


def list_stock_moves(db: Session, limit: int = 40) -> list[StockMove]:
    """Recent ledger activity for the Inventory feed, newest first (NFR-18)."""
    return list(
        db.execute(
            select(StockMove).order_by(StockMove.created_at.desc(), StockMove.id.desc()).limit(limit)
        ).scalars()
    )


def ledger_balance(db: Session, product_id: int) -> int:
    """Sum of the ledger for one product. Reconciliation asserts this equals the
    cached `product.stock` (NFR-06)."""
    return db.execute(
        select(func.coalesce(func.sum(StockMove.delta), 0)).where(
            StockMove.product_id == product_id
        )
    ).scalar_one()
