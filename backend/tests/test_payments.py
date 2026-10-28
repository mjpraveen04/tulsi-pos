"""WP6 — cash change and UPI static QR, including TC-04 and TC-07 (FR-26…28)."""

from decimal import Decimal

from app.models import PaymentMethod


def _basket(dosa, coffee, chai):
    """The TC-02 basket: total ₹309.75."""
    return [
        {"product_id": dosa.id, "qty": 2},
        {"product_id": coffee.id, "qty": 1},
        {"product_id": chai.id, "qty": 3},
    ]


def test_tc04_cash_change(client, db, cashier, make_product, auth_headers):
    """TC-04 — total ₹309.75, tender ₹500 → change ₹190.25, saved as Cash."""
    dosa = make_product("Masala Dosa", "90", 24)
    coffee = make_product("Filter Coffee", "40", 60)
    chai = make_product("Masala Chai", "25", 80)

    response = client.post(
        "/api/bills",
        json={
            "lines": _basket(dosa, coffee, chai),
            "payment": {"method": "CASH", "tendered": "500.00"},
        },
        headers=auth_headers(cashier, "1111"),
    )

    assert response.status_code == 201
    receipt = response.json()
    assert Decimal(receipt["total"]) == Decimal("309.75")
    assert Decimal(receipt["tendered"]) == Decimal("500.00")
    assert Decimal(receipt["change_due"]) == Decimal("190.25")
    assert receipt["method"] == "CASH"

    from app.models import Bill, Payment

    bill = db.query(Bill).filter_by(bill_no=receipt["bill_no"]).one()
    payment = db.query(Payment).filter_by(bill_id=bill.id).one()
    assert payment.method is PaymentMethod.CASH
    assert payment.change_due == Decimal("190.25")


def test_exact_cash_gives_no_change(client, cashier, make_product, auth_headers):
    product = make_product("Masala Chai", "25", 80)

    receipt = client.post(
        "/api/bills",
        json={
            "lines": [{"product_id": product.id, "qty": 4}],
            "payment": {"method": "CASH", "tendered": "105.00"},
        },
        headers=auth_headers(cashier, "1111"),
    ).json()

    assert Decimal(receipt["total"]) == Decimal("105.00")
    assert Decimal(receipt["change_due"]) == Decimal("0.00")


def test_short_cash_is_rejected_and_nothing_is_written(
    client, db, cashier, make_product, auth_headers
):
    """FR-27: 'Payment received' cannot go through for less than the total."""
    from sqlalchemy import func, select

    from app.models import Bill

    product = make_product("South Thali", "160", 10)

    response = client.post(
        "/api/bills",
        json={
            "lines": [{"product_id": product.id, "qty": 1}],
            "payment": {"method": "CASH", "tendered": "100.00"},
        },
        headers=auth_headers(cashier, "1111"),
    )

    assert response.status_code == 400
    assert "less than the total" in response.json()["detail"]

    db.expire_all()
    assert db.execute(select(func.count()).select_from(Bill)).scalar_one() == 0
    assert db.get(type(product), product.id).stock == 10


def test_short_cash_does_not_burn_a_bill_number(client, cashier, make_product, auth_headers):
    """FR-24: a rejected payment must not leave a gap in the bill series.

    Postgres sequences are not rolled back, so the check has to run before the
    number is taken — not just before the commit.
    """
    product = make_product("Masala Chai", "25", 80)
    headers = auth_headers(cashier, "1111")

    def sell(tendered: str):
        return client.post(
            "/api/bills",
            json={
                "lines": [{"product_id": product.id, "qty": 1}],
                "payment": {"method": "CASH", "tendered": tendered},
            },
            headers=headers,
        )

    first = sell("100.00").json()["bill_no"]
    assert sell("1.00").status_code == 400
    second = sell("100.00").json()["bill_no"]

    assert second == first + 1


def test_cash_without_a_tendered_amount_is_rejected(client, cashier, make_product, auth_headers):
    product = make_product("Upma", "60", 12)

    response = client.post(
        "/api/bills",
        json={"lines": [{"product_id": product.id, "qty": 1}], "payment": {"method": "CASH"}},
        headers=auth_headers(cashier, "1111"),
    )

    assert response.status_code == 422


def test_tc07_upi_payment_marks_paid_and_deducts_stock(
    client, db, cashier, make_product, auth_headers
):
    """TC-07 — select UPI, confirm, bill saved as UPI with stock deducted."""
    product = make_product("Pav Bhaji", "120", 9)

    response = client.post(
        "/api/bills",
        json={"lines": [{"product_id": product.id, "qty": 2}], "payment": {"method": "UPI"}},
        headers=auth_headers(cashier, "1111"),
    )

    assert response.status_code == 201
    receipt = response.json()
    assert receipt["method"] == "UPI"
    assert receipt["tendered"] is None
    assert receipt["change_due"] is None
    assert Decimal(receipt["total"]) == Decimal("252.00")

    db.expire_all()
    assert db.get(type(product), product.id).stock == 7


def test_upi_must_not_carry_a_tendered_amount(client, cashier, make_product, auth_headers):
    product = make_product("Vada Pav", "40", 30)

    response = client.post(
        "/api/bills",
        json={
            "lines": [{"product_id": product.id, "qty": 1}],
            "payment": {"method": "UPI", "tendered": "50.00"},
        },
        headers=auth_headers(cashier, "1111"),
    )

    assert response.status_code == 422


def test_upi_qr_endpoint_returns_a_scannable_png(client, cashier, auth_headers):
    """FR-28: generated locally by the qrcode lib — no gateway involved."""
    response = client.get(
        "/api/register/upi-qr?amount=309.75&note=Order%201042",
        headers=auth_headers(cashier, "1111"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["upi_id"] == "tulsitiffins@upi"
    assert body["payee_name"] == "Tulsi Tiffins"
    assert body["intent_url"].startswith("upi://pay?pa=tulsitiffins%40upi")
    assert "am=309.75" in body["intent_url"]
    assert "cu=INR" in body["intent_url"]
    assert body["qr_data_uri"].startswith("data:image/png;base64,")
    assert len(body["qr_data_uri"]) > 200


def test_upi_qr_requires_authentication(client):
    assert client.get("/api/register/upi-qr").status_code == 401
