"""TC-01 and the RBAC sweep (FR-04/06, NFR-07/11).

Asserts the contract in README Section 5 endpoint by endpoint: 401 without a
token, 403 with the wrong role. The UI hiding a tab is never the control.
"""

import pytest

# (method, path, manager_only) — mirrors the legend in README Section 5.
ENDPOINTS = [
    ("GET", "/api/auth/me", False),
    ("POST", "/api/auth/logout", False),
    ("GET", "/api/products", False),
    ("GET", "/api/register/menu", False),
    ("GET", "/api/register/upi-qr", False),
    ("GET", "/api/bills", False),
    ("GET", "/api/users", True),
    ("POST", "/api/users", True),
    ("GET", "/api/products/stock-moves", True),
    ("POST", "/api/products", True),
    ("GET", "/api/reports/daily-total", True),
]

BODIES = {
    "/api/users": {"name": "Temp", "role": "CASHIER", "pin": "9999"},
    "/api/products": {"name": "Temp", "category": "Tiffin", "price": "10.00", "opening_stock": 1},
}


def _call(client, method, path, headers=None):
    return client.request(method, path, headers=headers or {}, json=BODIES.get(path))


@pytest.mark.parametrize("method,path,manager_only", ENDPOINTS)
def test_no_token_is_401(client, method, path, manager_only):
    """NFR-07: login is the only door without a token."""
    assert _call(client, method, path).status_code == 401


@pytest.mark.parametrize("method,path,manager_only", ENDPOINTS)
def test_role_is_enforced_server_side(
    client, manager, cashier, auth_headers, method, path, manager_only
):
    """TC-01: a cashier is blocked from every manager endpoint (403)."""
    cashier_response = _call(client, method, path, auth_headers(cashier, "1111"))
    manager_response = _call(client, method, path, auth_headers(manager, "1234"))

    if manager_only:
        assert cashier_response.status_code == 403, path
    else:
        assert cashier_response.status_code != 403, path

    assert manager_response.status_code != 403, path


def test_tc01_cashier_sees_the_register_but_not_inventory(
    client, cashier, make_product, auth_headers
):
    """TC-01 end to end: Register works, Products/Staff/Orders-report are blocked."""
    make_product("Masala Dosa", "90", 24)
    headers = auth_headers(cashier, "1111")

    assert client.get("/api/register/menu", headers=headers).status_code == 200
    assert client.get("/api/users", headers=headers).status_code == 403
    assert client.get("/api/products/stock-moves", headers=headers).status_code == 403
    assert client.get("/api/reports/daily-total", headers=headers).status_code == 403
    assert client.post(
        "/api/products",
        json={"name": "X", "category": "Tiffin", "price": "10.00", "opening_stock": 1},
        headers=headers,
    ).status_code == 403


def test_a_cashier_token_cannot_be_upgraded_by_editing_its_claims(client, cashier, token_for):
    """The role comes from a signed token — rewriting the claim breaks the signature."""
    from jose import jwt

    token = token_for(cashier, "1111")
    payload = jwt.get_unverified_claims(token)
    payload["role"] = "MANAGER"
    forged = jwt.encode(payload, "attacker-secret", algorithm="HS256")

    assert client.get("/api/users", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_role_is_read_from_the_database_not_the_token(client, db, cashier, token_for):
    """A token minted before a demotion must not keep manager powers."""
    from app.models import UserRole

    cashier.role = UserRole.MANAGER
    db.commit()
    token = token_for(cashier, "1111")
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/users", headers=headers).status_code == 200

    cashier.role = UserRole.CASHIER
    db.commit()

    assert client.get("/api/users", headers=headers).status_code == 403


def test_a_token_for_a_deactivated_user_stops_working(client, db, manager, cashier, token_for):
    """FR-11: deactivating someone mid-shift kills their live session."""
    token = token_for(cashier, "1111")
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/auth/me", headers=headers).status_code == 200

    cashier.is_active = False
    db.commit()

    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_malformed_authorization_headers_are_401(client):
    for header in ["", "Bearer", "Bearer ", "Basic abc123", "Bearer not.a.jwt"]:
        assert client.get("/api/auth/me", headers={"Authorization": header}).status_code == 401
