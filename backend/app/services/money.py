"""Money maths. Decimal only — never float (TR-04)."""

from decimal import ROUND_HALF_UP, Decimal

from app.config import settings

TWO_PLACES = Decimal("0.01")


def quantize(amount: Decimal) -> Decimal:
    """Round half-up to 2 dp, the convention on an Indian cash receipt."""
    return Decimal(amount).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def line_total(unit_price: Decimal, qty: int) -> Decimal:
    return quantize(Decimal(unit_price) * qty)


def totals(subtotal: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    """subtotal → (subtotal, gst, total) at the configured GST rate (5%).

    >>> totals(Decimal("295.00"))
    (Decimal('295.00'), Decimal('14.75'), Decimal('309.75'))
    """
    subtotal = quantize(subtotal)
    gst = quantize(subtotal * Decimal(settings.gst_rate))
    return subtotal, gst, quantize(subtotal + gst)
