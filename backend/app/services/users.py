"""Staff management (FR-09…11). Manager-only at the router; guarded here too."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import ConflictError, NotFoundError, ValidationError
from app.models import User, UserRole
from app.schemas.user import UserCreate, UserUpdate
from app.security import hash_pin


def list_users(db: Session) -> list[User]:
    return list(db.execute(select(User).order_by(User.role, User.name)).scalars())


def get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("That staff member no longer exists.")
    return user


def _active_manager_count(db: Session, exclude_id: int | None = None) -> int:
    stmt = select(func.count()).select_from(User).where(
        User.role == UserRole.MANAGER, User.is_active.is_(True)
    )
    if exclude_id is not None:
        stmt = stmt.where(User.id != exclude_id)
    return db.execute(stmt).scalar_one()


def create_user(db: Session, payload: UserCreate) -> User:
    """A newly created staff member can sign in with their PIN immediately."""
    clash = db.execute(
        select(User).where(func.lower(User.name) == payload.name.strip().lower())
    ).scalar_one_or_none()
    if clash is not None:
        raise ConflictError(f"There is already a team member called {clash.name}.")

    user = User(
        name=payload.name.strip(),
        role=payload.role,
        pin_hash=hash_pin(payload.pin),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, user_id: int, payload: UserUpdate, actor: User) -> User:
    """Rename, change role, or reset the PIN. A reset invalidates the old PIN
    immediately because the hash is overwritten (FR-10)."""
    user = get_user(db, user_id)

    if payload.name is not None:
        clash = db.execute(
            select(User).where(
                func.lower(User.name) == payload.name.strip().lower(), User.id != user.id
            )
        ).scalar_one_or_none()
        if clash is not None:
            raise ConflictError(f"There is already a team member called {clash.name}.")
        user.name = payload.name.strip()

    if payload.role is not None and payload.role is not user.role:
        # Demoting the last active manager would lock everyone out of Inventory,
        # Orders and Staff.
        if user.role is UserRole.MANAGER and _active_manager_count(db, exclude_id=user.id) == 0:
            raise ValidationError(
                "This is the only active manager — promote someone else first."
            )
        user.role = payload.role

    if payload.pin is not None:
        user.pin_hash = hash_pin(payload.pin)

    db.commit()
    db.refresh(user)
    return user


def deactivate_user(db: Session, user_id: int, actor: User) -> User:
    """Soft-delete: blocks login, keeps the audit trail intact (FR-11)."""
    user = get_user(db, user_id)

    if user.id == actor.id:
        raise ValidationError("You can't remove yourself.")

    if not user.is_active:
        return user

    if user.role is UserRole.MANAGER and _active_manager_count(db, exclude_id=user.id) == 0:
        raise ValidationError("You can't remove the only active manager.")

    user.is_active = False
    db.commit()
    db.refresh(user)
    return user
