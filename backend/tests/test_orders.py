"""WP7 — order history, price stability (TC-08) and the daily total (FR-29/30)."""

from datetime import date, timedelta
from decimal import Decimal


def _sell(client, headers, product, qty=1, method="UPI"):
    payment = {"method": method}
    if method == "CASH":
        payment["tendered"] = "10000.00"
    response = client.post(
        "/api/bills",
        json={"lines": [{"product_id": product.id, "qty": qty}], "payment": payment},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_tc08_old_receipt_keeps_the_price_at_sale(
    client, manager, cashier, make_product, auth_headers
):
    """TC-08 — sell at ₹90, raise the price to ₹110, reopen the old bill."""
    product = make_product("Masala Dosa", "90", 24)
    sold = _sell(client, auth_headers(cashier, "1111"), product, qty=2)

    assert Decimal(sold["subtotal"]) == Decimal("180.00")

    raised = client.patch(
        f"/api/products/{product.id}",
        json={"price": "110.00"},
        headers=auth_headers(manager, "1234"),
    )
    assert Decimal(raised.json()["price"]) == Decimal("110.00")

    reopened = client.get(
        f"/api/bills/{sold['bill_no']}", headers=auth_headers(cashier, "1111")
    ).json()

    assert Decimal(reopened["lines"][0]["unit_price"]) == Decimal("90.00")
    assert Decimal(reopened["lines"][0]["line_total"]) == Decimal("180.00")
    assert Decimal(reopened["subtotal"]) == Decimal("180.00")
    assert Decimal(reopened["total"]) == Decimal("189.00")


def test_archived_product_still_appears_on_its_old_receipt(
    client, manager, cashier, make_product, auth_headers
):
    """FR-14: archiving hides it from the Register, not from history."""
    product = make_product("Seasonal Special", "75", 10)
    sold = _sell(client, auth_headers(cashier, "1111"), product)

    client.patch(f"/api/products/{product.id}/archive", headers=auth_headers(manager, "1234"))

    reopened = client.get(
        f"/api/bills/{sold['bill_no']}", headers=auth_headers(cashier, "1111")
    ).json()
    assert reopened["lines"][0]["name"] == "Seasonal Special"


def test_history_lists_bills_newest_first(client, cashier, make_product, auth_headers):
    """FR-29."""
    headers = auth_headers(cashier, "1111")
    product = make_product("Idly (2 pc)", "50", 40)

    first = _sell(client, headers, product)
    second = _sell(client, headers, product, qty=3)

    listed = client.get("/api/bills", headers=headers).json()

    assert [b["bill_no"] for b in listed] == [second["bill_no"], first["bill_no"]]
    assert listed[0]["item_count"] == 3
    assert listed[0]["summary"] == "3× Idly (2 pc)"
    assert listed[0]["cashier_name"] == "Ravi K."
    assert listed[0]["method"] == "UPI"


def test_history_can_be_searched_by_bill_number(client, cashier, make_product, auth_headers):
    headers = auth_headers(cashier, "1111")
    product = make_product("Vada Pav", "40", 30)
    _sell(client, headers, product)
    target = _sell(client, headers, product)

    found = client.get(f"/api/bills?bill_no={target['bill_no']}", headers=headers).json()

    assert len(found) == 1
    assert found[0]["bill_no"] == target["bill_no"]


def test_history_can_be_filtered_by_date(client, cashier, make_product, auth_headers):
    headers = auth_headers(cashier, "1111")
    product = make_product("Upma", "60", 12)
    _sell(client, headers, product)

    today = client.get(f"/api/bills?date={date.today().isoformat()}", headers=headers).json()
    yesterday = client.get(
        f"/api/bills?date={(date.today() - timedelta(days=1)).isoformat()}", headers=headers
    ).json()

    assert len(today) == 1
    assert yesterday == []


def test_unknown_bill_number_is_404(client, cashier, auth_headers):
    response = client.get("/api/bills/999999", headers=auth_headers(cashier, "1111"))

    assert response.status_code == 404
    assert "No bill #999999" in response.json()["detail"]


def test_multi_line_receipt_summary(client, cashier, make_product, auth_headers):
    dosa = make_product("Masala Dosa", "90", 24)
    chai = make_product("Masala Chai", "25", 80)
    headers = auth_headers(cashier, "1111")

    created = client.post(
        "/api/bills",
        json={
            "lines": [{"product_id": dosa.id, "qty": 2}, {"product_id": chai.id, "qty": 3}],
            "payment": {"method": "CASH", "tendered": "500.00"},
        },
        headers=headers,
    ).json()

    listed = client.get("/api/bills", headers=headers).json()[0]
    assert listed["summary"] == "2× Masala Dosa, 3× Masala Chai"
    assert listed["item_count"] == 5
    assert Decimal(listed["total"]) == Decimal(created["total"])


def test_daily_total_sums_todays_bills(client, manager, cashier, make_product, auth_headers):
    """FR-30 — the Orders summary cards."""
    product = make_product("South Thali", "160", 10)
    cashier_headers = auth_headers(cashier, "1111")

    _sell(client, cashier_headers, product, qty=2)  # 320.00 + 16.00 = 336.00
    _sell(client, cashier_headers, product, qty=1)  # 160.00 +  8.00 = 168.00

    report = client.get("/api/reports/daily-total", headers=auth_headers(manager, "1234")).json()

    assert report["date"] == date.today().isoformat()
    assert report["bill_count"] == 2
    assert report["item_count"] == 3
    assert Decimal(report["total"]) == Decimal("504.00")


def test_daily_total_is_zero_on_a_quiet_day(client, manager, auth_headers):
    report = client.get("/api/reports/daily-total", headers=auth_headers(manager, "1234")).json()

    assert report["bill_count"] == 0
    assert Decimal(report["total"]) == Decimal("0")


def test_daily_total_is_manager_only(client, cashier, auth_headers):
    """FR-04 — a cashier gets 403 on the report."""
    assert client.get(
        "/api/reports/daily-total", headers=auth_headers(cashier, "1111")
    ).status_code == 403


def test_cashiers_can_read_their_own_order_history(client, cashier, make_product, auth_headers):
    """Bill history is 🔓 in the contract — the Orders *tab* is what's manager-only."""
    headers = auth_headers(cashier, "1111")
    product = make_product("Masala Chai", "25", 80)
    sold = _sell(client, headers, product)

    assert client.get("/api/bills", headers=headers).status_code == 200
    assert client.get(f"/api/bills/{sold['bill_no']}", headers=headers).status_code == 200
