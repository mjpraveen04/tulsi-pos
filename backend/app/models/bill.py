from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Bill(Base, TimestampMixin):
    """A completed sale. Written only by services/billing.py, in one transaction."""

    __tablename__ = "bills"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Sequential and unique (FR-24). Allocated from the `bill_no_seq` sequence
    # only after the stock check passes, so rejected sales leave no gap.
    bill_no: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    cashier_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    gst: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    lines: Mapped[list["BillLine"]] = relationship(
        back_populates="bill", cascade="all, delete-orphan", lazy="selectin"
    )
    payment: Mapped["Payment"] = relationship(  # noqa: F821
        back_populates="bill", uselist=False, lazy="selectin"
    )
    cashier: Mapped["User"] = relationship(lazy="joined")  # noqa: F821


class BillLine(Base):
    """One line of a bill, carrying the price at the time of sale (FR-25)."""

    __tablename__ = "bill_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    bill_id: Mapped[int] = mapped_column(ForeignKey("bills.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    # Copied from the product at creation — later price edits must not rewrite
    # history. This column is why TC-08 passes.
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    bill: Mapped["Bill"] = relationship(back_populates="lines")
    product: Mapped["Product"] = relationship(lazy="joined")  # noqa: F821
