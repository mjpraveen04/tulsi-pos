"""WP2 — authentication and token handling (FR-01…08, NFR-07…09)."""

from datetime import UTC, datetime, timedelta

from jose import jwt

from app.config import settings


def test_login_with_correct_pin_returns_token_and_user(client, manager):
    response = client.post("/api/auth/login", json={"user_id": manager.id, "pin": "1234"})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"] == {"id": manager.id, "name": "Anita R.", "role": "MANAGER"}

    claims = jwt.decode(body["access_token"], settings.jwt_secret, algorithms=["HS256"])
    assert claims["sub"] == str(manager.id)
    assert claims["role"] == "MANAGER"


def test_login_with_wrong_pin_is_rejected(client, manager):
    """FR-01: a wrong PIN grants no session."""
    response = client.post("/api/auth/login", json={"user_id": manager.id, "pin": "9999"})

    assert response.status_code == 401
    assert "access_token" not in response.json()


def test_login_for_unknown_user_is_rejected(client):
    response = client.post("/api/auth/login", json={"user_id": 4242, "pin": "1234"})
    assert response.status_code == 401


def test_login_rejects_non_four_digit_pin(client, manager):
    """NFR-10: shape is validated server-side, not just in the UI."""
    assert client.post("/api/auth/login", json={"user_id": manager.id, "pin": "12"}).status_code == 422
    assert client.post("/api/auth/login", json={"user_id": manager.id, "pin": "abcd"}).status_code == 422


def test_deactivated_user_cannot_log_in(client, db, cashier):
    """FR-11: deactivation blocks login but keeps the row."""
    cashier.is_active = False
    db.commit()

    response = client.post("/api/auth/login", json={"user_id": cashier.id, "pin": "1111"})
    assert response.status_code == 401


def test_token_lifetime_is_one_shift(client, manager):
    """NFR-08: ~8 hours."""
    token = client.post(
        "/api/auth/login", json={"user_id": manager.id, "pin": "1234"}
    ).json()["access_token"]

    claims = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    lifetime = claims["exp"] - claims["iat"]
    assert lifetime == settings.jwt_expire_hours * 3600 == 8 * 3600


def test_me_returns_the_signed_in_user(client, manager, auth_headers):
    response = client.get("/api/auth/me", headers=auth_headers(manager, "1234"))

    assert response.status_code == 200
    assert response.json()["name"] == "Anita R."


def test_logout_endpoint_exists(client, manager, auth_headers):
    """FR-08 — stateless tokens, but the endpoint exists for symmetry."""
    assert client.post("/api/auth/logout", headers=auth_headers(manager, "1234")).status_code == 200


def test_protected_endpoint_without_token_is_401(client):
    """NFR-07: every endpoint except login needs a token."""
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/products").status_code == 401
    assert client.post("/api/bills", json={"lines": [], "payment": {"method": "UPI"}}).status_code == 401


def test_expired_token_is_401(client, manager):
    """NFR-07: an expired shift token stops working."""
    expired = jwt.encode(
        {
            "sub": str(manager.id),
            "role": "MANAGER",
            "iat": int((datetime.now(UTC) - timedelta(hours=10)).timestamp()),
            "exp": int((datetime.now(UTC) - timedelta(hours=2)).timestamp()),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401


def test_token_signed_with_another_secret_is_401(client, manager):
    forged = jwt.encode({"sub": str(manager.id), "role": "MANAGER"}, "not-our-secret")

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401


def test_pin_targets_never_leak_hashes(client, manager, cashier):
    """The login picker needs names only (FR-07, NFR-09)."""
    response = client.get("/api/users/pin-targets")

    assert response.status_code == 200
    body = response.json()
    assert {u["name"] for u in body} == {"Anita R.", "Ravi K."}
    for entry in body:
        assert set(entry) == {"id", "name", "role"}
    assert "pin" not in response.text.lower()


def test_pins_are_stored_as_salted_bcrypt_hashes(db, manager, cashier):
    """FR-07 / NFR-09: no plaintext, and equal PINs still get distinct hashes."""
    from app.models import User
    from app.security import hash_pin, verify_pin

    assert manager.pin_hash != "1234"
    assert manager.pin_hash.startswith("$2b$")
    assert verify_pin("1234", manager.pin_hash)
    assert not verify_pin("1111", manager.pin_hash)

    # Same PIN, different salt → different hash.
    assert hash_pin("1234") != hash_pin("1234")
    assert all(u.pin_hash.startswith("$2b$") for u in db.query(User).all())
