"""Test harness.

The release-gate tests exercise `SELECT ... FOR UPDATE`, a real CHECK
constraint and genuine concurrent transactions, so they run against a real
PostgreSQL 16 — SQLite cannot prove any of it. The database is created and
migrated with Alembic (never `create_all`), matching how production is built
(NFR-17).
"""

import os
import subprocess
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

BACKEND_DIR = Path(__file__).resolve().parent.parent

DEFAULT_TEST_URL = "postgresql+psycopg2://tulsi:tulsi@localhost:5432/tulsi_pos_test"
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_URL)

# app.config caches settings at import time, so the URL must be in the
# environment before anything under app/ is imported.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL


def _ensure_database() -> None:
    """CREATE DATABASE if it isn't there yet, then migrate it to head."""
    url = make_url(TEST_DATABASE_URL)
    admin_url = url.set(database="postgres")
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin_engine.dispose()

    subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        check=True,
        env={**os.environ, "DATABASE_URL": TEST_DATABASE_URL},
        capture_output=True,
    )


@pytest.fixture(scope="session", autouse=True)
def _database() -> None:
    _ensure_database()


@pytest.fixture(scope="session")
def engine(_database: None):
    from app.db import engine as app_engine

    return app_engine


TABLES = ["product_photos", "stock_moves", "payments", "bill_lines", "bills", "products", "users"]


@pytest.fixture(autouse=True)
def clean_tables(engine) -> Iterator[None]:
    """Every test starts from an empty schema and a rewound bill sequence."""
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))
        conn.execute(text("ALTER SEQUENCE bill_no_seq RESTART WITH 1042"))
    yield


@pytest.fixture
def db(engine) -> Iterator[Session]:
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    session = factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client() -> Iterator[TestClient]:
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


# --------------------------------------------------------------------------
# Domain fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def manager(db: Session):
    from app.models import User, UserRole
    from app.security import hash_pin

    user = User(name="Anita R.", role=UserRole.MANAGER, pin_hash=hash_pin("1234"))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def cashier(db: Session):
    from app.models import User, UserRole
    from app.security import hash_pin

    user = User(name="Ravi K.", role=UserRole.CASHIER, pin_hash=hash_pin("1111"))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def make_product(db: Session, manager):
    """Create a product with its OPENING ledger move, like the real service."""
    from app.models import Product, StockMove, StockMoveReason

    def _make(name: str, price: str, stock: int, category: str = "Tiffin", reorder: int = 6):
        product = Product(
            name=name,
            category=category,
            price=Decimal(price),
            stock=0,
            reorder_level=reorder,
        )
        db.add(product)
        db.flush()
        if stock:
            db.add(
                StockMove(
                    product_id=product.id,
                    delta=stock,
                    reason=StockMoveReason.OPENING,
                    user_id=manager.id,
                )
            )
            product.stock = stock
        db.commit()
        db.refresh(product)
        return product

    return _make


@pytest.fixture
def token_for(client: TestClient):
    def _token(user, pin: str) -> str:
        response = client.post(
            "/api/auth/login", json={"user_id": user.id, "pin": pin}
        )
        assert response.status_code == 200, response.text
        return response.json()["access_token"]

    return _token


@pytest.fixture
def auth_headers(token_for):
    def _headers(user, pin: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token_for(user, pin)}"}

    return _headers
