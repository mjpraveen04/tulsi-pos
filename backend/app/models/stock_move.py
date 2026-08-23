from sqlalchemy import Enum, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import StockMoveReason


class StockMove(Base, TimestampMixin):
    """Append-only stock ledger — the single source of truth for stock (NFR-06).

    Rows are only ever INSERTed. Nothing in the application may UPDATE or DELETE
    a move; a mistake is corrected by posting a compensating move. Every row
    records who acted and when, which is what makes the history auditable
    (NFR-18).
    """

    __tablename__ = "stock_moves"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"), nullable=False, index=True
    )
    # Signed: +receive/+opening, -remove, -sale.
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[StockMoveReason] = mapped_column(
        Enum(StockMoveReason, name="stock_move_reason"), nullable=False
    )
    bill_id: Mapped[int | None] = mapped_column(
        ForeignKey("bills.id"), nullable=True, index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    product: Mapped["Product"] = relationship(lazy="joined")  # noqa: F821
    user: Mapped["User"] = relationship(lazy="joined")  # noqa: F821
    bill: Mapped["Bill | None"] = relationship(lazy="joined")  # noqa: F821
