"""WP3 — staff management and its guards (FR-09…11)."""


def test_manager_can_list_staff(client, manager, cashier, auth_headers):
    response = client.get("/api/users", headers=auth_headers(manager, "1234"))

    assert response.status_code == 200
    assert {u["name"] for u in response.json()} == {"Anita R.", "Ravi K."}
    assert "pin_hash" not in response.text


def test_new_staff_member_can_sign_in_immediately(client, manager, auth_headers):
    """FR-09: creating a user makes their PIN work right away."""
    created = client.post(
        "/api/users",
        json={"name": "Karthik S.", "role": "CASHIER", "pin": "4321"},
        headers=auth_headers(manager, "1234"),
    )
    assert created.status_code == 201
    new_id = created.json()["id"]

    login = client.post("/api/auth/login", json={"user_id": new_id, "pin": "4321"})
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "CASHIER"


def test_duplicate_names_are_rejected(client, manager, auth_headers):
    headers = auth_headers(manager, "1234")
    client.post(
        "/api/users", json={"name": "Karthik S.", "role": "CASHIER", "pin": "4321"}, headers=headers
    )

    clash = client.post(
        "/api/users", json={"name": "karthik s.", "role": "CASHIER", "pin": "5555"}, headers=headers
    )
    assert clash.status_code == 409


def test_pin_reset_invalidates_the_old_pin(client, manager, cashier, auth_headers):
    """FR-10: after a reset the old PIN stops working and the new one starts."""
    reset = client.patch(
        f"/api/users/{cashier.id}", json={"pin": "8888"}, headers=auth_headers(manager, "1234")
    )
    assert reset.status_code == 200

    assert client.post("/api/auth/login", json={"user_id": cashier.id, "pin": "1111"}).status_code == 401
    assert client.post("/api/auth/login", json={"user_id": cashier.id, "pin": "8888"}).status_code == 200


def test_manager_can_rename_and_change_role(client, manager, cashier, auth_headers):
    response = client.patch(
        f"/api/users/{cashier.id}",
        json={"name": "Ravi Kumar", "role": "MANAGER"},
        headers=auth_headers(manager, "1234"),
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Ravi Kumar"
    assert response.json()["role"] == "MANAGER"


def test_deactivate_keeps_the_record_but_blocks_login(client, manager, cashier, auth_headers):
    """FR-11: soft delete — history stays intact."""
    response = client.patch(
        f"/api/users/{cashier.id}/deactivate", headers=auth_headers(manager, "1234")
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert client.post("/api/auth/login", json={"user_id": cashier.id, "pin": "1111"}).status_code == 401

    still_listed = client.get("/api/users", headers=auth_headers(manager, "1234")).json()
    assert any(u["id"] == cashier.id for u in still_listed)


def test_cannot_deactivate_yourself(client, manager, auth_headers):
    response = client.patch(
        f"/api/users/{manager.id}/deactivate", headers=auth_headers(manager, "1234")
    )

    assert response.status_code == 400
    assert "yourself" in response.json()["detail"]


def test_one_of_two_managers_can_be_deactivated(client, db, manager, auth_headers):
    """With a spare manager on the books, removing one is allowed."""
    from app.models import User, UserRole
    from app.security import hash_pin

    second_manager = User(name="Deepa V.", role=UserRole.MANAGER, pin_hash=hash_pin("7777"))
    db.add(second_manager)
    db.commit()
    db.refresh(second_manager)

    response = client.patch(
        f"/api/users/{second_manager.id}/deactivate", headers=auth_headers(manager, "1234")
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_cannot_deactivate_the_last_active_manager(db, manager, cashier):
    """Defence in depth (FR-11).

    Over HTTP the self-guard shadows this one — the only actor who could target
    the last manager is that manager. So the rule is asserted directly against
    the service, which is where it lives and what protects any future caller.
    """
    import pytest

    from app.errors import ValidationError
    from app.services import users as users_service

    with pytest.raises(ValidationError, match="only active manager"):
        users_service.deactivate_user(db, manager.id, actor=cashier)

    db.rollback()
    db.refresh(manager)
    assert manager.is_active is True


def test_cannot_demote_the_last_active_manager(client, manager, cashier, auth_headers):
    response = client.patch(
        f"/api/users/{manager.id}", json={"role": "CASHIER"}, headers=auth_headers(manager, "1234")
    )

    assert response.status_code == 400
    assert "only active manager" in response.json()["detail"]


def test_staff_endpoints_reject_a_cashier(client, cashier, auth_headers):
    """FR-04: the guard is server-side, not the hidden tab."""
    headers = auth_headers(cashier, "1111")

    assert client.get("/api/users", headers=headers).status_code == 403
    assert client.post(
        "/api/users", json={"name": "X", "role": "CASHIER", "pin": "0000"}, headers=headers
    ).status_code == 403
    assert client.patch(f"/api/users/{cashier.id}", json={"name": "Y"}, headers=headers).status_code == 403
    assert client.patch(f"/api/users/{cashier.id}/deactivate", headers=headers).status_code == 403
