from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas.user import UserCreate, UserDetail, UserUpdate
from app.security import require_manager
from app.services import users as users_service

# Manager-only for the whole router (FR-09…11). Enforced here, on the server —
# hiding the tab in the UI is a convenience, not the control.
router = APIRouter(prefix="/api/users", tags=["staff"], dependencies=[Depends(require_manager)])


@router.get("", response_model=list[UserDetail])
def list_users(db: Session = Depends(get_db)) -> list[User]:
    return users_service.list_users(db)


@router.post("", response_model=UserDetail, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    return users_service.create_user(db, payload)


@router.patch("/{user_id}", response_model=UserDetail)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
) -> User:
    return users_service.update_user(db, user_id, payload, current_user)


@router.patch("/{user_id}/deactivate", response_model=UserDetail)
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
) -> User:
    return users_service.deactivate_user(db, user_id, current_user)
