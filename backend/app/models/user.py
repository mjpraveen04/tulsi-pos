from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.enums import UserRole


class User(Base, TimestampMixin):
    """Staff member. PINs are stored only as salted bcrypt hashes (FR-07)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), nullable=False
    )
    pin_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # Deactivated users cannot log in but stay attached to their history (FR-11).
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
