"""WP4 — products and the append-only stock ledger (FR-12…18, NFR-06)."""

from decimal import Decimal

import pytest
from sqlalchemy import text


def _create(client, headers, **overrides):
    body = {
        "name": "Rava Dosa",
        "category": "Tiffin",
        "price": "95.00",
        "opening_stock": 15,
        "reorder_level": 6,
    }
    body.update(overrides)
    return client.post("/api/products", json=body, headers=headers)


def test_creating_a_product_writes_an_opening_ledger_move(client, db, manager, auth_headers):
    """FR-12: opening stock is backed by a ledger row, not a bare column write."""
    from app.models import StockMove, StockMoveReason

    response = _create(client, auth_headers(manager, "1234"))

    assert response.status_code == 201
    body = response.json()
    assert body["stock"] == 15
    assert Decimal(body["price"]) == Decimal("95.00")

    moves = db.query(StockMove).filter_by(product_id=body["id"]).all()
    assert len(moves) == 1
    assert moves[0].delta == 15
    assert moves[0].reason is StockMoveReason.OPENING
    assert moves[0].user_id == manager.id


def test_product_created_with_no_opening_stock_has_no_move(client, db, manager, auth_headers):
    from app.models import StockMove

    response = _create(client, auth_headers(manager, "1234"), opening_stock=0)

    assert response.json()["stock"] == 0
    assert db.query(StockMove).filter_by(product_id=response.json()["id"]).count() == 0


def test_receive_and_remove_write_moves_and_update_cached_stock(
    client, db, manager, make_product, auth_headers
):
    """FR-15: one transaction writes the ledger row and the cached mirror."""
    from app.models import StockMove, StockMoveReason

    product = make_product("Masala Dosa", "90", 24)
    headers = auth_headers(manager, "1234")

    received = client.post(
        f"/api/products/{product.id}/stock", json={"delta": 10, "reason": "RECEIVE"}, headers=headers
    )
    assert received.status_code == 200
    assert received.json()["stock"] == 34

    removed = client.post(
        f"/api/products/{product.id}/stock", json={"delta": 4, "reason": "REMOVE"}, headers=headers
    )
    assert removed.status_code == 200
    assert removed.json()["stock"] == 30

    moves = (
        db.query(StockMove).filter_by(product_id=product.id).order_by(StockMove.id).all()
    )
    assert [(m.delta, m.reason) for m in moves] == [
        (24, StockMoveReason.OPENING),
        (10, StockMoveReason.RECEIVE),
        (-4, StockMoveReason.REMOVE),
    ]


def test_ledger_sum_always_equals_cached_stock(client, db, manager, make_product, auth_headers):
    """NFR-06 reconciliation: the ledger is the source of truth."""
    from app.services import inventory as inventory_service

    product = make_product("Idly (2 pc)", "50", 40)
    headers = auth_headers(manager, "1234")

    for delta, reason in [(5, "RECEIVE"), (12, "RECEIVE"), (3, "REMOVE"), (20, "REMOVE")]:
        client.post(
            f"/api/products/{product.id}/stock",
            json={"delta": delta, "reason": reason},
            headers=headers,
        )

    db.expire_all()
    refreshed = inventory_service.get_product(db, product.id)
    assert refreshed.stock == 34
    assert inventory_service.ledger_balance(db, product.id) == refreshed.stock


def test_removing_more_than_available_is_rejected_and_writes_nothing(
    client, db, manager, make_product, auth_headers
):
    from app.models import StockMove

    product = make_product("Samosa (2 pc)", "40", 4)
    before = db.query(StockMove).filter_by(product_id=product.id).count()

    response = client.post(
        f"/api/products/{product.id}/stock",
        json={"delta": 9, "reason": "REMOVE"},
        headers=auth_headers(manager, "1234"),
    )

    assert response.status_code == 409
    assert "only 4 in stock" in response.json()["detail"]

    db.expire_all()
    assert db.query(StockMove).filter_by(product_id=product.id).count() == before
    assert db.get(type(product), product.id).stock == 4


def test_stock_adjustments_must_be_receive_or_remove(client, manager, make_product, auth_headers):
    """A caller cannot post a SALE or OPENING move through the inventory route."""
    product = make_product("Upma", "60", 12)
    headers = auth_headers(manager, "1234")

    for reason in ("SALE", "OPENING"):
        response = client.post(
            f"/api/products/{product.id}/stock", json={"delta": 1, "reason": reason}, headers=headers
        )
        assert response.status_code == 400

    # Negative magnitudes are rejected by validation, so RECEIVE can never subtract.
    assert client.post(
        f"/api/products/{product.id}/stock", json={"delta": -5, "reason": "RECEIVE"}, headers=headers
    ).status_code == 422


def test_database_check_constraint_blocks_negative_stock(db, make_product):
    """TR-01 backstop: even a raw UPDATE cannot drive stock below zero."""
    from sqlalchemy.exc import IntegrityError

    product = make_product("Mango Lassi", "60", 2)

    with pytest.raises(IntegrityError, match="ck_products_stock_non_negative"):
        db.execute(text("UPDATE products SET stock = -1 WHERE id = :id"), {"id": product.id})
        db.commit()
    db.rollback()


def test_archived_products_disappear_from_the_register_but_stay_retrievable(
    client, manager, make_product, auth_headers
):
    """FR-14."""
    product = make_product("Pav Bhaji", "120", 9)
    headers = auth_headers(manager, "1234")

    assert client.patch(f"/api/products/{product.id}/archive", headers=headers).status_code == 200

    menu = client.get("/api/register/menu", headers=headers).json()
    assert all(p["id"] != product.id for p in menu["products"])

    listed = client.get("/api/products", headers=headers).json()
    assert all(p["id"] != product.id for p in listed)

    with_archived = client.get("/api/products?include_archived=true", headers=headers).json()
    assert any(p["id"] == product.id for p in with_archived)


def test_search_and_category_filter(client, manager, make_product, auth_headers):
    """FR-16."""
    make_product("Masala Dosa", "90", 24, category="Tiffin")
    make_product("Masala Chai", "25", 80, category="Beverages")
    make_product("Vada Pav", "40", 30, category="Snacks")
    headers = auth_headers(manager, "1234")

    by_name = client.get("/api/products?q=masala", headers=headers).json()
    assert {p["name"] for p in by_name} == {"Masala Dosa", "Masala Chai"}

    by_category = client.get("/api/products?category=Snacks", headers=headers).json()
    assert {p["name"] for p in by_category} == {"Vada Pav"}


def test_menu_flags_low_stock_and_sold_out(client, manager, make_product, auth_headers):
    """FR-17/19: the badge states the Register card renders."""
    make_product("Plenty", "10", 30, reorder=6)
    make_product("Running low", "10", 5, reorder=6)
    make_product("Gone", "10", 0, reorder=6)

    menu = client.get("/api/register/menu", headers=auth_headers(manager, "1234")).json()
    flags = {p["name"]: (p["is_low_stock"], p["is_sold_out"]) for p in menu["products"]}

    assert flags["Plenty"] == (False, False)
    assert flags["Running low"] == (True, False)
    assert flags["Gone"] == (False, True)


def test_menu_groups_by_category(client, manager, make_product, auth_headers):
    make_product("Masala Dosa", "90", 24, category="Tiffin")
    make_product("Idly (2 pc)", "50", 40, category="Tiffin")
    make_product("Masala Chai", "25", 80, category="Beverages")

    menu = client.get("/api/register/menu", headers=auth_headers(manager, "1234")).json()
    grouped = {c["category"]: len(c["products"]) for c in menu["categories"]}

    assert grouped == {"Tiffin": 2, "Beverages": 1}


def test_stock_move_feed_records_actor_and_time(client, db, manager, make_product, auth_headers):
    """NFR-18: every move is attributable."""
    product = make_product("Medu Vada", "55", 6)
    headers = auth_headers(manager, "1234")
    client.post(
        f"/api/products/{product.id}/stock", json={"delta": 3, "reason": "RECEIVE"}, headers=headers
    )

    feed = client.get("/api/products/stock-moves", headers=headers).json()

    assert feed[0]["reason"] == "RECEIVE"
    assert feed[0]["delta"] == 3
    assert feed[0]["user_name"] == "Anita R."
    assert feed[0]["product_name"] == "Medu Vada"
    assert feed[0]["created_at"]


def test_price_edit_does_not_touch_stock(client, manager, make_product, auth_headers):
    """FR-13."""
    product = make_product("Filter Coffee", "40", 60)

    response = client.patch(
        f"/api/products/{product.id}", json={"price": "45.00"}, headers=auth_headers(manager, "1234")
    )

    assert response.status_code == 200
    assert Decimal(response.json()["price"]) == Decimal("45.00")
    assert response.json()["stock"] == 60


def test_inventory_writes_are_manager_only(client, cashier, make_product, auth_headers):
    """FR-04: cashiers can read the menu but not change it."""
    product = make_product("Masala Dosa", "90", 24)
    headers = auth_headers(cashier, "1111")

    assert client.get("/api/products", headers=headers).status_code == 200
    assert client.get("/api/register/menu", headers=headers).status_code == 200

    assert _create(client, headers).status_code == 403
    assert client.patch(f"/api/products/{product.id}", json={"price": "1.00"}, headers=headers).status_code == 403
    assert client.patch(f"/api/products/{product.id}/archive", headers=headers).status_code == 403
    assert client.post(
        f"/api/products/{product.id}/stock", json={"delta": 1, "reason": "RECEIVE"}, headers=headers
    ).status_code == 403
    assert client.get("/api/products/stock-moves", headers=headers).status_code == 403
