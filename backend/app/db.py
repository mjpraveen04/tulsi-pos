"""Engine and session plumbing.

Sync SQLAlchemy is deliberate: the no-oversell guarantee leans on
`SELECT ... FOR UPDATE` inside a single transaction, and sync sessions make the
locking (and the concurrency test that proves it) straightforward to reason
about. FastAPI runs `def` endpoints in a threadpool, so this stays non-blocking
at the server level.
"""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
