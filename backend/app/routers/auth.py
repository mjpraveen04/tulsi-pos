from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas.user import LoginRequest, LoginResponse, UserPublic
from app.security import get_current_user
from app.services import auth as auth_service

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    """The only unauthenticated endpoint in the API."""
    token, user = auth_service.authenticate(db, payload.user_id, payload.pin)
    return LoginResponse(access_token=token, user=UserPublic.model_validate(user))


@router.get("/auth/me", response_model=UserPublic)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.post("/auth/logout")
def logout(current_user: User = Depends(get_current_user)) -> dict[str, str]:
    """Tokens are stateless; the client discards it. Here for symmetry (FR-08)."""
    return {"detail": "Signed out."}


@router.get("/users/pin-targets", response_model=list[UserPublic])
def pin_targets(db: Session = Depends(get_db)) -> list[User]:
    """Names for the login picker. No hashes, no PINs."""
    return auth_service.list_pin_targets(db)
