"""WP5 — the atomic sale over HTTP, including TC-02/03/05/06 (FR-19…25)."""

from decimal import Decimal

from sqlalchemy import func, select

from app.models import Bill, StockMove, StockMoveReason
from app.services import money


def test_money_maths_rounds_half_up(client):
    """FR-21 in isolation: Decimal arithmetic, half-up at 2 dp."""
    assert money.totals(Decimal("295.00")) == (
        Decimal("295.00"),
        Decimal("14.75"),
        Decimal("309.75"),
    )
    # 0.125 → 0.13, not 0.12 (banker's rounding would give 0.12).
    assert money.quantize(Decimal("0.125")) == Decimal("0.13")
    assert money.quantize(Decimal("2.675")) == Decimal("2.68")
    assert money.line_total(Decimal("90.00"), 3) == Decimal("270.00")


def test_tc02_gst_and_totals(client, cashier, make_product, auth_headers):
    """TC-02 — 2× Dosa ₹90, 1× Coffee ₹40, 3× Chai ₹25 → ₹295.00 / ₹14.75 / ₹309.75."""
    dosa = make_product("Masala Dosa", "90", 24)
    coffee = make_product("Filter Coffee", "40", 60, category="Beverages")
    chai = make_product("Masala Chai", "25", 80, category="Beverages")

    response = client.post(
        "/api/bills",
        json={
            "lines": [
                {"product_id": dosa.id, "qty": 2},
                {"product_id": coffee.id, "qty": 1},
                {"product_id": chai.id, "qty": 3},
            ],
            "payment": {"method": "CASH", "tendered": "500.00"},
        },
        headers=auth_headers(cashier, "1111"),
    )

    assert response.status_code == 201
    receipt = response.json()
    assert Decimal(receipt["subtotal"]) == Decimal("295.00")
    assert Decimal(receipt["gst"]) == Decimal("14.75")
    assert Decimal(receipt["total"]) == Decimal("309.75")
    assert receipt["item_count"] == 6
    assert receipt["cashier_name"] == "Ravi K."


def test_tc03_insufficient_stock_is_rejected_and_nothing_is_written(
    client, db, cashier, make_product, auth_headers
):
    """TC-03 — item has 3, ask for 5."""
    product = make_product("Samosa (2 pc)", "40", 3)

    response = client.post(
        "/api/bills",
        json={
            "lines": [{"product_id": product.id, "qty": 5}],
            "payment": {"method": "CASH", "tendered": "500.00"},
        },
        headers=auth_headers(cashier, "1111"),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Insufficient stock: only 3 left"

    db.expire_all()
    assert db.get(type(product), product.id).stock == 3
    assert db.execute(select(func.count()).select_from(Bill)).scalar_one() == 0
    assert db.execute(
        select(func.count()).select_from(StockMove).where(StockMove.reason == StockMoveReason.SALE)
    ).scalar_one() == 0


def test_tc05_stock_deduction_and_ledger_move(client, db, cashier, make_product, auth_headers):
    """TC-05 — Dosa=24, sell 2 → 22, with a −2 SALE move referencing the bill."""
    product = make_product("Masala Dosa", "90", 24)

    response = client.post(
        "/api/bills",
        json={
            "lines": [{"product_id": product.id, "qty": 2}],
            "payment": {"method": "UPI"},
        },
        headers=auth_headers(cashier, "1111"),
    )
    assert response.status_code == 201
    bill_no = response.json()["bill_no"]

    db.expire_all()
    assert db.get(type(product), product.id).stock == 22

    bill = db.execute(select(Bill).where(Bill.bill_no == bill_no)).scalar_one()
    move = db.execute(
        select(StockMove).where(
            StockMove.product_id == product.id, StockMove.reason == StockMoveReason.SALE
        )
    ).scalar_one()

    assert move.delta == -2
    assert move.bill_id == bill.id
    assert move.user_id == cashier.id

    # NFR-06: ledger still reconciles after a sale.
    balance = db.execute(
        select(func.coalesce(func.sum(StockMove.delta), 0)).where(
            StockMove.product_id == product.id
        )
    ).scalar_one()
    assert balance == 22


def test_tc06_bill_numbers_are_sequential_and_unique(client, cashier, make_product, auth_headers):
    """TC-06 — second bill is first + 1, no duplicates."""
    product = make_product("Idly (2 pc)", "50", 40)
    headers = auth_headers(cashier, "1111")

    def ring_up() -> int:
        response = client.post(
            "/api/bills",
            json={"lines": [{"product_id": product.id, "qty": 1}], "payment": {"method": "UPI"}},
            headers=headers,
        )
        assert response.status_code == 201
        return response.json()["bill_no"]

    first, second, third = ring_up(), ring_up(), ring_up()

    assert second == first + 1
    assert third == second + 1
    assert len({first, second, third}) == 3


def test_repeated_lines_for_one_product_are_merged_before_the_stock_check(
    client, db, cashier, make_product, auth_headers
):
    """Two 2× lines of a 3-stock item is a 4× request — it must be rejected."""
    product = make_product("Medu Vada", "55", 3)

    response = client.post(
        "/api/bills",
        json={
            "lines": [{"product_id": product.id, "qty": 2}, {"product_id": product.id, "qty": 2}],
            "payment": {"method": "UPI"},
        },
        headers=auth_headers(cashier, "1111"),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Insufficient stock: only 3 left"
    db.expire_all()
    assert db.get(type(product), product.id).stock == 3


def test_selling_the_exact_remaining_stock_is_allowed(client, db, cashier, make_product, auth_headers):
    product = make_product("Mango Lassi", "60", 2)

    response = client.post(
        "/api/bills",
        json={"lines": [{"product_id": product.id, "qty": 2}], "payment": {"method": "UPI"}},
        headers=auth_headers(cashier, "1111"),
    )

    assert response.status_code == 201
    db.expire_all()
    assert db.get(type(product), product.id).stock == 0


def test_sold_out_item_cannot_be_billed(client, cashier, make_product, auth_headers):
    product = make_product("Gone", "10", 0)

    response = client.post(
        "/api/bills",
        json={"lines": [{"product_id": product.id, "qty": 1}], "payment": {"method": "UPI"}},
        headers=auth_headers(cashier, "1111"),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Insufficient stock: only 0 left"


def test_archived_item_cannot_be_billed(client, db, cashier, make_product, auth_headers):
    """FR-14: off the menu means off the register."""
    product = make_product("Retired Special", "80", 5)
    product.is_archived = True
    db.commit()

    response = client.post(
        "/api/bills",
        json={"lines": [{"product_id": product.id, "qty": 1}], "payment": {"method": "UPI"}},
        headers=auth_headers(cashier, "1111"),
    )

    assert response.status_code == 400
    assert "no longer on the menu" in response.json()["detail"]


def test_unknown_product_is_rejected(client, cashier, auth_headers):
    response = client.post(
        "/api/bills",
        json={"lines": [{"product_id": 999999, "qty": 1}], "payment": {"method": "UPI"}},
        headers=auth_headers(cashier, "1111"),
    )

    assert response.status_code == 404


def test_empty_and_malformed_baskets_are_rejected(client, cashier, make_product, auth_headers):
    """NFR-10: shape is validated before any business logic runs."""
    product = make_product("Masala Dosa", "90", 24)
    headers = auth_headers(cashier, "1111")

    assert client.post(
        "/api/bills", json={"lines": [], "payment": {"method": "UPI"}}, headers=headers
    ).status_code == 422

    assert client.post(
        "/api/bills",
        json={"lines": [{"product_id": product.id, "qty": 0}], "payment": {"method": "UPI"}},
        headers=headers,
    ).status_code == 422

    assert client.post(
        "/api/bills",
        json={"lines": [{"product_id": product.id, "qty": -3}], "payment": {"method": "UPI"}},
        headers=headers,
    ).status_code == 422


def test_receipt_carries_price_at_sale(client, cashier, make_product, auth_headers):
    """FR-25: the line records the price charged, not a live lookup."""
    product = make_product("Masala Dosa", "90", 24)

    receipt = client.post(
        "/api/bills",
        json={"lines": [{"product_id": product.id, "qty": 2}], "payment": {"method": "UPI"}},
        headers=auth_headers(cashier, "1111"),
    ).json()

    line = receipt["lines"][0]
    assert line["name"] == "Masala Dosa"
    assert Decimal(line["unit_price"]) == Decimal("90.00")
    assert Decimal(line["line_total"]) == Decimal("180.00")


def test_cashiers_and_managers_can_both_ring_up_sales(
    client, manager, cashier, make_product, auth_headers
):
    """FR-19: the Register is the one screen both roles share."""
    product = make_product("Vada Pav", "40", 30)

    for user, pin in [(cashier, "1111"), (manager, "1234")]:
        response = client.post(
            "/api/bills",
            json={"lines": [{"product_id": product.id, "qty": 1}], "payment": {"method": "UPI"}},
            headers=auth_headers(user, pin),
        )
        assert response.status_code == 201
