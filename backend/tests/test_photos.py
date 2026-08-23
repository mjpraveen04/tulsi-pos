"""Product photo upload (FR-13 extension).

File upload is the one route that accepts arbitrary bytes, so most of these
tests are about what must be *rejected*.
"""

from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from app.config import settings


@pytest.fixture(autouse=True)
def media_root(tmp_path, monkeypatch):
    """Keep uploads out of the real media volume during tests."""
    monkeypatch.setattr(settings, "media_root", str(tmp_path))
    return tmp_path


def png_bytes(size=(120, 90), color=(200, 40, 40)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def jpeg_bytes(size=(120, 90)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, (10, 120, 60)).save(buffer, format="JPEG")
    return buffer.getvalue()


def upload(client, product_id, headers, content, filename="photo.png", content_type="image/png"):
    return client.post(
        f"/api/products/{product_id}/photo",
        files={"file": (filename, content, content_type)},
        headers=headers,
    )


def test_manager_can_upload_a_photo(client, db, manager, make_product, auth_headers, media_root):
    product = make_product("Masala Dosa", "90", 24)

    response = upload(client, product.id, auth_headers(manager, "1234"), png_bytes())

    assert response.status_code == 200
    photo_url = response.json()["photo_url"]
    assert photo_url.startswith("/media/products/")
    assert photo_url.endswith(".png")

    stored = media_root / "products" / Path(photo_url).name
    assert stored.exists()

    db.expire_all()
    assert db.get(type(product), product.id).photo_url == photo_url


def test_uploaded_photo_appears_on_the_register_menu(
    client, manager, make_product, auth_headers
):
    product = make_product("Vada Pav", "40", 30)
    upload(client, product.id, auth_headers(manager, "1234"), png_bytes())

    menu = client.get("/api/register/menu", headers=auth_headers(manager, "1234")).json()
    card = next(p for p in menu["products"] if p["id"] == product.id)

    assert card["photo_url"].startswith("/media/products/")


def test_jpeg_is_accepted_and_keeps_its_extension(client, manager, make_product, auth_headers):
    product = make_product("Pav Bhaji", "120", 9)

    response = upload(
        client, product.id, auth_headers(manager, "1234"), jpeg_bytes(), "x.jpg", "image/jpeg"
    )

    assert response.status_code == 200
    assert response.json()["photo_url"].endswith(".jpg")


def test_large_images_are_downscaled(client, manager, make_product, auth_headers, media_root):
    """A 3000px photo off a phone must not be served to a tablet as-is."""
    product = make_product("South Thali", "160", 10)

    response = upload(client, product.id, auth_headers(manager, "1234"), png_bytes((3000, 2000)))

    stored = media_root / "products" / Path(response.json()["photo_url"]).name
    with Image.open(stored) as saved:
        assert max(saved.size) == settings.photo_max_edge


def test_replacing_a_photo_deletes_the_old_file(
    client, manager, make_product, auth_headers, media_root
):
    product = make_product("Upma", "60", 12)
    headers = auth_headers(manager, "1234")

    first = upload(client, product.id, headers, png_bytes()).json()["photo_url"]
    second = upload(client, product.id, headers, png_bytes(color=(10, 10, 200))).json()["photo_url"]

    assert first != second
    assert not (media_root / "products" / Path(first).name).exists()
    assert (media_root / "products" / Path(second).name).exists()


def test_removing_a_photo_clears_the_field_and_the_file(
    client, manager, make_product, auth_headers, media_root
):
    product = make_product("Idly (2 pc)", "50", 40)
    headers = auth_headers(manager, "1234")
    photo_url = upload(client, product.id, headers, png_bytes()).json()["photo_url"]

    response = client.delete(f"/api/products/{product.id}/photo", headers=headers)

    assert response.status_code == 200
    assert response.json()["photo_url"] is None
    assert not (media_root / "products" / Path(photo_url).name).exists()


# --------------------------------------------------------------------------
# What must be rejected
# --------------------------------------------------------------------------


def test_a_script_renamed_as_png_is_rejected(client, manager, make_product, auth_headers):
    """The filename and content-type headers are attacker-controlled — the bytes decide."""
    product = make_product("Masala Chai", "25", 80)

    response = upload(
        client,
        product.id,
        auth_headers(manager, "1234"),
        b"<?php system($_GET['c']); ?>",
        "innocent.png",
        "image/png",
    )

    assert response.status_code == 400
    assert "isn't a picture" in response.json()["detail"]


def test_svg_is_rejected(client, manager, make_product, auth_headers):
    """SVG can carry script and would execute same-origin when served back."""
    product = make_product("Mango Lassi", "60", 15)
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'

    response = upload(
        client, product.id, auth_headers(manager, "1234"), svg, "logo.svg", "image/svg+xml"
    )

    assert response.status_code == 400


def test_oversized_images_are_rejected(client, manager, make_product, auth_headers, monkeypatch):
    product = make_product("Medu Vada", "55", 6)
    monkeypatch.setattr(settings, "max_photo_bytes", 1024)

    response = upload(client, product.id, auth_headers(manager, "1234"), png_bytes((400, 400)))

    assert response.status_code == 400
    assert "larger than" in response.json()["detail"]


def test_empty_upload_is_rejected(client, manager, make_product, auth_headers):
    product = make_product("Plain Dosa", "70", 18)

    response = upload(client, product.id, auth_headers(manager, "1234"), b"")

    assert response.status_code == 400


def test_uploaded_file_is_re_encoded_not_stored_verbatim(
    client, manager, make_product, auth_headers, media_root
):
    """A polyglot's trailing payload must not survive into the served file."""
    product = make_product("Samosa (2 pc)", "40", 4)
    payload = png_bytes() + b"<?php system($_GET['c']); ?>"

    response = upload(client, product.id, auth_headers(manager, "1234"), payload)

    assert response.status_code == 200
    stored = media_root / "products" / Path(response.json()["photo_url"]).name
    assert b"<?php" not in stored.read_bytes()


def test_photo_routes_are_manager_only(client, cashier, make_product, auth_headers):
    """FR-04."""
    product = make_product("Filter Coffee", "40", 60)
    headers = auth_headers(cashier, "1111")

    assert upload(client, product.id, headers, png_bytes()).status_code == 403
    assert client.delete(f"/api/products/{product.id}/photo", headers=headers).status_code == 403


def test_photo_routes_need_a_token(client, manager, make_product):
    product = make_product("Masala Dosa", "90", 24)

    assert upload(client, product.id, {}, png_bytes()).status_code == 401
    assert client.delete(f"/api/products/{product.id}/photo").status_code == 401


def test_uploading_to_an_unknown_product_is_404(client, manager, auth_headers):
    response = upload(client, 999999, auth_headers(manager, "1234"), png_bytes())

    assert response.status_code == 404


def test_a_doctored_photo_url_cannot_delete_other_files(db, manager, make_product, tmp_path):
    """Path traversal through the stored URL must not escape the media directory."""
    from app.services import media

    victim = Path(settings.media_root) / "important.txt"
    victim.write_text("keep me")

    for hostile in [
        "/media/products/../important.txt",
        "/media/products/../../etc/passwd",
        "/etc/passwd",
        "../important.txt",
        "/media/products/",
    ]:
        media.delete_product_photo(hostile)

    assert victim.exists()
