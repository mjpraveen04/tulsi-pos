from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import User
from app.schemas.product import MenuCategory, MenuOut, ProductOut
from app.security import get_current_user
from app.services import inventory as inventory_service
from app.services import payments as payments_service

router = APIRouter(prefix="/api/register", tags=["register"])


class UpiQrOut(BaseModel):
    upi_id: str
    payee_name: str
    intent_url: str
    qr_data_uri: str


@router.get("/menu", response_model=MenuOut)
def menu(
    category: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MenuOut:
    """Active products with live stock and low-stock flags (FR-17/19)."""
    products = inventory_service.list_products(db, q=q, category=category)
    out = [ProductOut.model_validate(p) for p in products]

    grouped: dict[str, list[ProductOut]] = {}
    for product in out:
        grouped.setdefault(product.category, []).append(product)

    return MenuOut(
        categories=[
            MenuCategory(category=name, products=items) for name, items in grouped.items()
        ],
        products=out,
    )


@router.get("/upi-qr", response_model=UpiQrOut)
def upi_qr(
    amount: Decimal | None = None,
    note: str | None = None,
    current_user: User = Depends(get_current_user),
) -> UpiQrOut:
    """The café's static UPI QR for the payment modal (FR-28)."""
    return UpiQrOut(
        upi_id=settings.upi_id,
        payee_name=settings.upi_payee_name,
        intent_url=payments_service.upi_intent_url(amount, note),
        qr_data_uri=payments_service.upi_qr_data_uri(amount, note),
    )
