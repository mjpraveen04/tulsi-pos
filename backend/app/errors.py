"""Domain errors raised by the service layer.

Services never import FastAPI. They raise these; `main.py` maps them onto HTTP
status codes so routers stay thin (NFR-16) and messages stay human-readable
(NFR-13).
"""


class DomainError(Exception):
    status_code = 400

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFoundError(DomainError):
    status_code = 404


class ValidationError(DomainError):
    status_code = 400


class ConflictError(DomainError):
    status_code = 409


class InsufficientStockError(ConflictError):
    """Raised when a sale asks for more units than the ledger can back (FR-23)."""

    def __init__(self, available: int) -> None:
        super().__init__(f"Insufficient stock: only {available} left")
        self.available = available


class AuthenticationError(DomainError):
    status_code = 401


class PermissionError_(DomainError):
    status_code = 403
