from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.models.enums import PaymentMethod


class BillLineIn(BaseModel):
    product_id: int
    qty: int = Field(gt=0)


class PaymentIn(BaseModel):
    method: PaymentMethod
    # Cash only. Validated against the computed total server-side too (FR-27).
    tendered: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)

    @model_validator(mode="after")
    def _cash_requires_tendered(self) -> "PaymentIn":
        if self.method is PaymentMethod.CASH and self.tendered is None:
            raise ValueError("Cash payments must include the amount received.")
        if self.method is PaymentMethod.UPI and self.tendered is not None:
            raise ValueError("UPI payments must not include a tendered amount.")
        return self


class BillCreate(BaseModel):
    lines: list[BillLineIn] = Field(min_length=1)
    payment: PaymentIn


class BillLineOut(BaseModel):
    product_id: int
    name: str
    qty: int
    unit_price: Decimal
    line_total: Decimal


class ReceiptOut(BaseModel):
    """The payload the receipt screen prints (README Section 5, step 8)."""

    bill_no: int
    created_at: datetime
    cashier_id: int
    cashier_name: str
    lines: list[BillLineOut]
    subtotal: Decimal
    gst: Decimal
    total: Decimal
    method: PaymentMethod
    tendered: Decimal | None
    change_due: Decimal | None
    item_count: int


class BillSummaryOut(BaseModel):
    bill_no: int
    created_at: datetime
    cashier_name: str
    item_count: int
    summary: str
    total: Decimal
    method: PaymentMethod


class DailyTotalOut(BaseModel):
    date: date
    total: Decimal
    bill_count: int
    item_count: int
