from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import PaymentMethod


class Payment(Base, TimestampMixin):
    """Exactly one per bill. `tendered`/`change_due` are cash-only (FR-27)."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    bill_id: Mapped[int] = mapped_column(ForeignKey("bills.id"), nullable=False, unique=True)
    method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, name="payment_method"), nullable=False
    )
    tendered: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    change_due: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    bill: Mapped["Bill"] = relationship(back_populates="payment")  # noqa: F821
