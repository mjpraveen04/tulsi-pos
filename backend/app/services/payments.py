"""UPI static QR (FR-26/28).

No gateway and no webhooks — that is explicitly out of scope. The café shows a
static UPI intent QR built from its own VPA; the cashier confirms receipt by
hand in the payment modal.
"""

import base64
from decimal import Decimal
from io import BytesIO
from urllib.parse import quote

import qrcode

from app.config import settings


def upi_intent_url(amount: Decimal | None = None, note: str | None = None) -> str:
    """A `upi://pay` deep link any UPI app can read."""
    parts = [
        f"pa={quote(settings.upi_id)}",
        f"pn={quote(settings.upi_payee_name)}",
        "cu=INR",
    ]
    if amount is not None:
        parts.append(f"am={Decimal(amount):.2f}")
    if note:
        parts.append(f"tn={quote(note)}")
    return "upi://pay?" + "&".join(parts)


def upi_qr_data_uri(amount: Decimal | None = None, note: str | None = None) -> str:
    """PNG data URI so the modal can render the QR with a plain <img>."""
    img = qrcode.make(upi_intent_url(amount, note))
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
