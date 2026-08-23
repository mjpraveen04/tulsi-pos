import enum


class UserRole(str, enum.Enum):
    MANAGER = "MANAGER"
    CASHIER = "CASHIER"


class StockMoveReason(str, enum.Enum):
    OPENING = "OPENING"
    RECEIVE = "RECEIVE"
    REMOVE = "REMOVE"
    SALE = "SALE"


class PaymentMethod(str, enum.Enum):
    CASH = "CASH"
    UPI = "UPI"
