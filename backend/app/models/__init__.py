"""SQLAlchemy models — the data-access layer (README Section 4).

Only services may import these. Routers never touch the ORM (NFR-16).
"""

from app.models.base import Base
from app.models.bill import Bill, BillLine
from app.models.enums import PaymentMethod, StockMoveReason, UserRole
from app.models.payment import Payment
from app.models.product import Product
from app.models.product_photo import ProductPhoto
from app.models.stock_move import StockMove
from app.models.user import User

__all__ = [
    "Base",
    "Bill",
    "BillLine",
    "Payment",
    "PaymentMethod",
    "Product",
    "ProductPhoto",
    "StockMove",
    "StockMoveReason",
    "User",
    "UserRole",
]
