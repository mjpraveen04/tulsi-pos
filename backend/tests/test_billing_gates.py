"""WP5 release gates — NFR-04 (no oversell under concurrency) and NFR-05 (rollback).

These two are the gates from README Section 6/9. The build is not shippable if
either goes red.

They use real threads against real PostgreSQL sessions, because that is the only
way to prove `SELECT ... FOR UPDATE` actually serialises two tills.
"""

import threading
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.errors import ConflictError, InsufficientStockError
from app.models import Bill, BillLine, Payment, Product, StockMove
from app.schemas.bill import BillCreate
from app.services import billing as billing_service


def _sale(product_id: int, qty: int) -> BillCreate:
    return BillCreate.model_validate(
        {
            "lines": [{"product_id": product_id, "qty": qty}],
            "payment": {"method": "UPI"},
        }
    )


@pytest.mark.gate
def test_two_simultaneous_bills_for_the_last_unit_leave_exactly_one_winner(
    engine, db, manager, cashier, make_product
):
    """NFR-04 — the concurrency gate.

    One unit left; two cashiers hit "Payment received" at the same instant.
    Exactly one sale may commit, and stock must never go negative.
    """
    product = make_product("Last Dosa", "90", 1)
    product_id = product.id
    barrier = threading.Barrier(2)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    results: list[str] = []
    lock = threading.Lock()

    def ring_up(actor_id: int) -> None:
        session = factory()
        try:
            actor = session.get(type(manager), actor_id)
            # Both threads arrive at the transaction together.
            barrier.wait(timeout=10)
            billing_service.create_bill(session, actor, _sale(product_id, 1))
            outcome = "committed"
        except InsufficientStockError:
            outcome = "rejected"
        except Exception as exc:  # pragma: no cover - surfaces unexpected failures
            outcome = f"error: {exc!r}"
        finally:
            session.close()
        with lock:
            results.append(outcome)

    threads = [
        threading.Thread(target=ring_up, args=(manager.id,)),
        threading.Thread(target=ring_up, args=(cashier.id,)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
        assert not thread.is_alive(), "billing deadlocked"

    assert sorted(results) == ["committed", "rejected"], results

    db.expire_all()
    assert db.get(Product, product_id).stock == 0
    assert db.execute(select(func.count()).select_from(Bill)).scalar_one() == 1
    assert db.execute(
        select(func.coalesce(func.sum(StockMove.delta), 0)).where(
            StockMove.product_id == product_id
        )
    ).scalar_one() == 0


@pytest.mark.gate
def test_ten_concurrent_bills_never_oversell(engine, db, manager, make_product):
    """NFR-04 under load: 10 tills, 4 units. Exactly 4 sales, stock lands on 0."""
    product = make_product("Popular Thali", "160", 4)
    product_id = product.id
    shoppers = 10
    barrier = threading.Barrier(shoppers)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    results: list[str] = []
    lock = threading.Lock()

    def ring_up() -> None:
        session = factory()
        try:
            actor = session.get(type(manager), manager.id)
            barrier.wait(timeout=20)
            billing_service.create_bill(session, actor, _sale(product_id, 1))
            outcome = "committed"
        except ConflictError:
            outcome = "rejected"
        except Exception as exc:  # pragma: no cover
            outcome = f"error: {exc!r}"
        finally:
            session.close()
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=ring_up) for _ in range(shoppers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
        assert not thread.is_alive(), "billing deadlocked under load"

    assert results.count("committed") == 4, results
    assert results.count("rejected") == 6, results

    db.expire_all()
    assert db.get(Product, product_id).stock == 0
    assert db.execute(select(func.count()).select_from(Bill)).scalar_one() == 4

    # Bill numbers stay unique even when allocated concurrently (FR-24).
    numbers = list(db.execute(select(Bill.bill_no)).scalars())
    assert len(numbers) == len(set(numbers))


@pytest.mark.gate
def test_failure_midway_through_the_sale_writes_nothing(
    db, manager, make_product, monkeypatch
):
    """NFR-05 — the rollback gate.

    The bill, its lines and its stock moves are already staged in the
    transaction when the payment step blows up. Nothing may survive.
    """
    dosa = make_product("Masala Dosa", "90", 24)
    chai = make_product("Masala Chai", "25", 80)

    def explode(*args, **kwargs):
        raise RuntimeError("card reader caught fire")

    monkeypatch.setattr(billing_service, "_record_payment", explode)

    payload = BillCreate.model_validate(
        {
            "lines": [{"product_id": dosa.id, "qty": 2}, {"product_id": chai.id, "qty": 3}],
            "payment": {"method": "CASH", "tendered": "500.00"},
        }
    )

    with pytest.raises(RuntimeError, match="card reader"):
        billing_service.create_bill(db, manager, payload)

    db.rollback()
    db.expire_all()

    assert db.execute(select(func.count()).select_from(Bill)).scalar_one() == 0
    assert db.execute(select(func.count()).select_from(BillLine)).scalar_one() == 0
    assert db.execute(select(func.count()).select_from(Payment)).scalar_one() == 0
    # Only the two OPENING moves from the fixture remain — no SALE moves.
    assert db.execute(select(func.count()).select_from(StockMove)).scalar_one() == 2
    assert db.get(Product, dosa.id).stock == 24
    assert db.get(Product, chai.id).stock == 80


@pytest.mark.gate
def test_insufficient_stock_rolls_back_the_whole_basket(db, manager, make_product):
    """NFR-05: one bad line voids the entire sale, including the good lines."""
    plenty = make_product("Idly (2 pc)", "50", 40)
    scarce = make_product("Samosa (2 pc)", "40", 3)

    payload = BillCreate.model_validate(
        {
            "lines": [{"product_id": plenty.id, "qty": 2}, {"product_id": scarce.id, "qty": 5}],
            "payment": {"method": "CASH", "tendered": "500.00"},
        }
    )

    with pytest.raises(InsufficientStockError) as exc:
        billing_service.create_bill(db, manager, payload)
    assert str(exc.value) == "Insufficient stock: only 3 left"

    db.rollback()
    db.expire_all()

    assert db.execute(select(func.count()).select_from(Bill)).scalar_one() == 0
    assert db.get(Product, plenty.id).stock == 40
    assert db.get(Product, scarce.id).stock == 3


@pytest.mark.gate
def test_rejected_sale_does_not_consume_a_bill_number(db, manager, make_product):
    """FR-24: numbers are allocated only once the sale is certain to happen."""
    product = make_product("Masala Dosa", "90", 2)

    first = billing_service.create_bill(db, manager, _sale(product.id, 1))

    with pytest.raises(InsufficientStockError):
        billing_service.create_bill(db, manager, _sale(product.id, 99))
    db.rollback()

    second = billing_service.create_bill(db, manager, _sale(product.id, 1))

    assert second.bill_no == first.bill_no + 1


@pytest.mark.gate
def test_money_never_uses_float(db, manager, make_product):
    """TR-04: values come back out of the database as Decimal."""
    product = make_product("Mango Lassi", "60.50", 10)

    bill = billing_service.create_bill(db, manager, _sale(product.id, 3))

    db.expire_all()
    stored = db.get(Bill, bill.id)
    assert isinstance(stored.subtotal, Decimal)
    assert isinstance(stored.gst, Decimal)
    assert isinstance(stored.total, Decimal)
    assert stored.subtotal == Decimal("181.50")
    assert stored.gst == Decimal("9.08")  # 9.075 rounded half-up
    assert stored.total == Decimal("190.58")
