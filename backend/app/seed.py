"""Demo data so the app is usable the moment it comes up (README Section 10).

Idempotent: safe to run on every container start. Opening stock is posted as
OPENING ledger moves, never as a bare UPDATE, so the ledger reconciles with
`product.stock` from the very first row (NFR-06).

The PINs below are demo credentials. Change or remove them before any real
deployment.
"""

import logging
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Product, StockMove, StockMoveReason, User, UserRole
from app.security import hash_pin

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tulsi.seed")

STAFF = [
    ("Anita R.", UserRole.MANAGER, "1234"),
    ("Ravi K.", UserRole.CASHIER, "1111"),
    ("Priya M.", UserRole.CASHIER, "2222"),
]

# The café menu from the prototype: (name, category, price, opening stock).
MENU = [
    ("Masala Dosa", "Tiffin", "90", 24),
    ("Plain Dosa", "Tiffin", "70", 18),
    ("Idly (2 pc)", "Tiffin", "50", 40),
    ("Medu Vada", "Tiffin", "55", 6),
    ("Upma", "Tiffin", "60", 12),
    ("Vada Pav", "Snacks", "40", 30),
    ("Pav Bhaji", "Snacks", "120", 9),
    ("Samosa (2 pc)", "Snacks", "40", 4),
    ("Masala Chai", "Beverages", "25", 80),
    ("Filter Coffee", "Beverages", "40", 60),
    ("Mango Lassi", "Beverages", "60", 15),
    ("South Thali", "Meals", "160", 10),
]

# Matches the prototype's low-stock threshold, so Medu Vada and Samosa show
# amber and Pav Bhaji does not.
REORDER_LEVEL = 6


def seed(db: Session) -> None:
    if db.execute(select(func.count()).select_from(User)).scalar_one() > 0:
        logger.info("users already present — skipping seed")
        return

    manager: User | None = None
    for name, role, pin in STAFF:
        user = User(name=name, role=role, pin_hash=hash_pin(pin), is_active=True)
        db.add(user)
        if manager is None:
            manager = user
    db.flush()
    assert manager is not None

    for name, category, price, opening in MENU:
        product = Product(
            name=name,
            category=category,
            price=Decimal(price),
            stock=0,
            reorder_level=REORDER_LEVEL,
            # Photos are uploaded by a manager from the Inventory screen; until
            # then each card shows a category-tinted tile.
            photo_url=None,
            is_archived=False,
        )
        db.add(product)
        db.flush()

        if opening > 0:
            db.add(
                StockMove(
                    product_id=product.id,
                    delta=opening,
                    reason=StockMoveReason.OPENING,
                    user_id=manager.id,
                )
            )
            product.stock = opening

    db.commit()
    logger.info("seeded %d staff and %d menu items", len(STAFF), len(MENU))


def main() -> None:
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
