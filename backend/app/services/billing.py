"""The atomic sale (README Section 6 — FR-19…25, NFR-04/05).

This is the most important code in the project. One transaction writes the bill,
its lines, its payment, one SALE move per line, and the decremented cached
stock — or it writes nothing at all.

Two things stop an oversell:

1. `SELECT ... FOR UPDATE` on every product row involved, taken *before* the
   stock check. Two tills billing the last dosa serialise on that lock, so the
   second one sees stock=0 and is rejected rather than both seeing stock=1.
2. `CHECK (stock >= 0)` on the products table, as a backstop for any path that
   ever bypasses this function.

Rows are locked in ascending product id order so two bills covering overlapping
baskets can never deadlock against each other.
"""

from collections import OrderedDict
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.errors import InsufficientStockError, NotFoundError, ValidationError
from app.models import (
    Bill,
    BillLine,
    Payment,
    PaymentMethod,
    Product,
    StockMove,
    StockMoveReason,
    User,
)
from app.schemas.bill import BillCreate, BillLineOut, PaymentIn, ReceiptOut
from app.services import money


def _next_bill_no(db: Session) -> int:
    """Sequential and collision-free under concurrency (FR-24).

    Called only after the stock check passes, so a rejected sale does not burn
    a number.
    """
    return int(db.execute(text("SELECT nextval('bill_no_seq')")).scalar_one())


def _lock_products(db: Session, product_ids: list[int]) -> dict[int, Product]:
    """Row-lock every product in the basket, in a deterministic order."""
    rows = db.execute(
        select(Product)
        .where(Product.id.in_(product_ids))
        .order_by(Product.id)
        .with_for_update()
    ).scalars().all()
    return {p.id: p for p in rows}


def _record_payment(db: Session, bill: Bill, payment: PaymentIn, total: Decimal) -> Payment:
    """Cash captures what was handed over and returns the change (FR-27).

    Split out so the rollback test (NFR-05) can inject a failure at exactly this
    point — after the bill and lines exist in the transaction but before commit.
    """
    tendered: Decimal | None = None
    change_due: Decimal | None = None

    if payment.method is PaymentMethod.CASH:
        tendered = money.quantize(payment.tendered or Decimal("0"))
        if tendered < total:
            raise ValidationError(
                f"Amount received (₹{tendered}) is less than the total (₹{total})."
            )
        change_due = money.quantize(tendered - total)

    row = Payment(
        bill_id=bill.id,
        method=payment.method,
        tendered=tendered,
        change_due=change_due,
    )
    db.add(row)
    bill.payment = row
    return row


def create_bill(db: Session, cashier: User, payload: BillCreate) -> Bill:
    """Record a completed sale. All-or-nothing (FR-22, NFR-05)."""

    # Merge repeated lines for the same product so the stock check sees the real
    # requested quantity, and so we lock each row once.
    wanted: OrderedDict[int, int] = OrderedDict()
    for line in payload.lines:
        wanted[line.product_id] = wanted.get(line.product_id, 0) + line.qty

    try:
        products = _lock_products(db, sorted(wanted))

        missing = set(wanted) - set(products)
        if missing:
            raise NotFoundError(
                "Some items are no longer on the menu. Please rebuild the order."
            )

        # 2. Check every line before writing anything.
        for product_id, qty in wanted.items():
            product = products[product_id]
            if product.is_archived:
                raise ValidationError(f"{product.name} is no longer on the menu.")
            if qty > product.stock:
                raise InsufficientStockError(product.stock)

        # 3/4. Price-at-sale copy and Decimal money maths.
        subtotal = Decimal("0.00")
        computed: list[tuple[Product, int, Decimal, Decimal]] = []
        for product_id, qty in wanted.items():
            product = products[product_id]
            unit_price = Decimal(product.price)
            total_for_line = money.line_total(unit_price, qty)
            subtotal += total_for_line
            computed.append((product, qty, unit_price, total_for_line))

        subtotal, gst, total = money.totals(subtotal)

        # 5. Allocate the bill number only now that the sale is going to happen.
        bill = Bill(
            bill_no=_next_bill_no(db),
            cashier_id=cashier.id,
            subtotal=subtotal,
            gst=gst,
            total=total,
        )
        bill.cashier = cashier
        db.add(bill)
        db.flush()  # assign bill.id for the lines, payment and moves

        # 6. Lines, ledger moves and the cached-stock decrement.
        for product, qty, unit_price, total_for_line in computed:
            line = BillLine(
                bill_id=bill.id,
                product_id=product.id,
                qty=qty,
                unit_price=unit_price,
                line_total=total_for_line,
            )
            line.product = product
            bill.lines.append(line)

            db.add(
                StockMove(
                    product_id=product.id,
                    delta=-qty,
                    reason=StockMoveReason.SALE,
                    bill_id=bill.id,
                    user_id=cashier.id,
                )
            )
            product.stock = product.stock - qty

        # 7. Payment (and, for cash, the change).
        _record_payment(db, bill, payload.payment, total)

        # 8. One commit for the whole sale.
        db.commit()
    except Exception:
        # Nothing partial survives: no bill, no lines, no moves, no decrement.
        db.rollback()
        raise

    return bill


def build_receipt(bill: Bill) -> ReceiptOut:
    """Shape a bill for the receipt screen, at price-at-sale (FR-25)."""
    lines = [
        BillLineOut(
            product_id=line.product_id,
            name=line.product.name,
            qty=line.qty,
            unit_price=line.unit_price,
            line_total=line.line_total,
        )
        for line in bill.lines
    ]
    return ReceiptOut(
        bill_no=bill.bill_no,
        created_at=bill.created_at,
        cashier_id=bill.cashier_id,
        cashier_name=bill.cashier.name,
        lines=lines,
        subtotal=bill.subtotal,
        gst=bill.gst,
        total=bill.total,
        method=bill.payment.method,
        tendered=bill.payment.tendered,
        change_due=bill.payment.change_due,
        item_count=sum(line.qty for line in bill.lines),
    )
