"""PIN hashing, JWT issue/verify, and the auth/role dependencies.

Every endpoint except `POST /api/auth/login` depends on `get_current_user`
(401 when the token is missing, malformed or expired) and manager-only
endpoints additionally depend on `require_manager` (403). The UI hiding a tab
is never the control (NFR-07/11).
"""

from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import User, UserRole

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# auto_error=False so a missing header produces our own 401 with a readable
# message rather than FastAPI's bare 403.
_bearer = HTTPBearer(auto_error=False)

_CREDENTIALS_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated. Please sign in again.",
    headers={"WWW-Authenticate": "Bearer"},
)


def hash_pin(pin: str) -> str:
    """Salted bcrypt hash. Plaintext PINs are never stored (FR-07, NFR-09)."""
    return _pwd_context.hash(pin)


def verify_pin(pin: str, pin_hash: str) -> bool:
    try:
        return _pwd_context.verify(pin, pin_hash)
    except ValueError:
        return False


def create_access_token(user: User) -> str:
    """JWT carrying the user id and role, valid for one shift (NFR-08)."""
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.id),
        "role": user.role.value,
        "name": user.name,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=settings.jwt_expire_hours)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise _CREDENTIALS_EXC

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (JWTError, KeyError, TypeError, ValueError):
        # Covers bad signature, expired token and malformed payloads alike.
        raise _CREDENTIALS_EXC from None

    # Imported here to avoid a circular import at module load: the auth service
    # imports security for hashing.
    from app.services import auth as auth_service

    user = auth_service.get_active_user(db, user_id)
    if user is None:
        raise _CREDENTIALS_EXC
    return user


def require_manager(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role is not UserRole.MANAGER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Managers only. Ask a manager to do this.",
        )
    return current_user
