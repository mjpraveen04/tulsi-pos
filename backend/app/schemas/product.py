from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.enums import StockMoveReason


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str
    price: Decimal
    stock: int
    reorder_level: int
    photo_url: str | None
    is_archived: bool

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_low_stock(self) -> bool:
        """Drives the amber badge on the Register card (FR-17)."""
        return 0 < self.stock <= self.reorder_level

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_sold_out(self) -> bool:
        return self.stock <= 0


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=60)
    price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    opening_stock: int = Field(default=0, ge=0)
    reorder_level: int = Field(default=5, ge=0)
    photo_url: str | None = None


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    category: str | None = Field(default=None, min_length=1, max_length=60)
    price: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    reorder_level: int | None = Field(default=None, ge=0)
    photo_url: str | None = None


class StockAdjustRequest(BaseModel):
    """One-tap receive/remove (FR-15). `delta` is always a positive magnitude;
    the sign comes from `reason`, so a caller cannot smuggle in a negative
    RECEIVE."""

    delta: int = Field(gt=0, description="Positive magnitude of the movement")
    reason: StockMoveReason

    def signed_delta(self) -> int:
        return self.delta if self.reason is StockMoveReason.RECEIVE else -self.delta


class StockMoveOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    product_name: str
    delta: int
    reason: StockMoveReason
    bill_id: int | None
    bill_no: int | None
    user_id: int
    user_name: str
    created_at: datetime


class MenuCategory(BaseModel):
    category: str
    products: list[ProductOut]


class MenuOut(BaseModel):
    categories: list[MenuCategory]
    products: list[ProductOut]
