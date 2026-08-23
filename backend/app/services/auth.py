"""Authentication (FR-01…08)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import AuthenticationError
from app.models import User
from app.security import create_access_token, verify_pin


def get_active_user(db: Session, user_id: int) -> User | None:
    return db.execute(
        select(User).where(User.id == user_id, User.is_active.is_(True))
    ).scalar_one_or_none()


def list_pin_targets(db: Session) -> list[User]:
    """Names for the login picker. Deliberately excludes hashes (FR-01)."""
    return list(
        db.execute(
            select(User).where(User.is_active.is_(True)).order_by(User.role, User.name)
        ).scalars()
    )


def authenticate(db: Session, user_id: int, pin: str) -> tuple[str, User]:
    """Verify the PIN and issue a token. No session is created on failure."""
    user = get_active_user(db, user_id)

    # Verify even when the user is missing so a wrong id and a wrong PIN take a
    # comparable amount of time, and report the same message either way.
    pin_hash = user.pin_hash if user else "$2b$12$" + "." * 53
    if not verify_pin(pin, pin_hash) or user is None:
        raise AuthenticationError("Incorrect PIN. Please try again.")

    return create_access_token(user), user
