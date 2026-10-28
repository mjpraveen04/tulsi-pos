"""Product photo upload (FR-13 extension).

File upload is the one route that accepts arbitrary bytes, so most of these
tests are about what must be *rejected*.
"""

from io import BytesIO

from PIL import Image
from sqlalchemy import func, select

from app.config import settings
from app.models import ProductPhoto


def png_bytes(size=(120, 90), color=(200, 40, 40)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def jpeg_bytes(size=(120, 90)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, (10, 120, 60)).save(buffer, format="JPEG")
    return buffer.getvalue()


def stored_photo_count(db) -> int:
    db.expire_all()
    return db.scalar(select(func.count()).select_from(ProductPhoto))


def upload(client, product_id, headers, content, filename="photo.png", content_type="image/png"):
    return client.post(
        f"/api/products/{product_id}/photo",
        files={"file": (filename, content, content_type)},
        headers=headers,
    )


def test_manager_can_upload_a_photo(client, db, manager, make_product, auth_headers):
    product = make_product("Masala Dosa", "90", 24)

    response = upload(client, product.id, auth_headers(manager, "1234"), png_bytes())

    assert response.status_code == 200
    photo_url = response.json()["photo_url"]
    assert photo_url.startswith("/media/products/")
    assert photo_url.endswith(".png")

    served = client.get(photo_url)
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/png"
    with Image.open(BytesIO(served.content)) as image:
        assert image.format == "PNG"

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


def test_large_images_are_downscaled(client, manager, make_product, auth_headers):
    """A 3000px photo off a phone must not be served to a tablet as-is."""
    product = make_product("South Thali", "160", 10)

    response = upload(client, product.id, auth_headers(manager, "1234"), png_bytes((3000, 2000)))

    served = client.get(response.json()["photo_url"])
    with Image.open(BytesIO(served.content)) as saved:
        assert max(saved.size) == settings.photo_max_edge


def test_replacing_a_photo_deletes_the_old_one(client, db, manager, make_product, auth_headers):
    product = make_product("Upma", "60", 12)
    headers = auth_headers(manager, "1234")

    first = upload(client, product.id, headers, png_bytes()).json()["photo_url"]
    second = upload(client, product.id, headers, png_bytes(color=(10, 10, 200))).json()["photo_url"]

    assert first != second
    assert client.get(first).status_code == 404
    assert client.get(second).status_code == 200
    assert stored_photo_count(db) == 1


def test_removing_a_photo_clears_the_field_and_the_bytes(
    client, db, manager, make_product, auth_headers
):
    product = make_product("Idly (2 pc)", "50", 40)
    headers = auth_headers(manager, "1234")
    photo_url = upload(client, product.id, headers, png_bytes()).json()["photo_url"]

    response = client.delete(f"/api/products/{product.id}/photo", headers=headers)

    assert response.status_code == 200
    assert response.json()["photo_url"] is None
    assert client.get(photo_url).status_code == 404
    assert stored_photo_count(db) == 0


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
    client, manager, make_product, auth_headers
):
    """A polyglot's trailing payload must not survive into the served file."""
    product = make_product("Samosa (2 pc)", "40", 4)
    payload = png_bytes() + b"<?php system($_GET['c']); ?>"

    response = upload(client, product.id, auth_headers(manager, "1234"), payload)

    assert response.status_code == 200
    served = client.get(response.json()["photo_url"])
    assert b"<?php" not in served.content


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


def test_a_doctored_photo_url_cannot_delete_other_photos(
    client, db, manager, make_product, auth_headers
):
    """Only a URL the media service issued maps to a stored photo."""
    from app.services import media

    product = make_product("Masala Dosa", "90", 24)
    real = upload(client, product.id, auth_headers(manager, "1234"), png_bytes()).json()
    real_name = real["photo_url"].rsplit("/", 1)[1]

    for hostile in [
        f"/media/products/../{real_name}",
        f"/media/other/{real_name}",
        f"/media/products/{real_name}x",
        "/etc/passwd",
        "/media/products/",
    ]:
        media.delete_product_photo(db, hostile)
    db.commit()

    assert stored_photo_count(db) == 1
    assert client.get(real["photo_url"]).status_code == 200


def test_unknown_or_malformed_photo_names_are_404(client):
    assert client.get("/media/products/" + "0" * 32 + ".png").status_code == 404
    assert client.get("/media/products/not-a-photo.png").status_code == 404
