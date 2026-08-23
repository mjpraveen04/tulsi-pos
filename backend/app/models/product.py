from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Product(Base, TimestampMixin):
    """A menu item.

    `stock` is a cached mirror of the StockMove ledger, updated only inside the
    same transaction as the move that caused it (NFR-06). The CHECK constraint
    is the database-level backstop for the no-oversell guarantee (TR-01).
    """

    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("stock >= 0", name="ck_products_stock_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(60), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reorder_level: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    photo_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Archived products vanish from the Register but stay on old bills (FR-14).
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
