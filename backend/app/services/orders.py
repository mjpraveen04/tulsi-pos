"""Bill history and the daily total (FR-29/30, NFR-18)."""

from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import NotFoundError
from app.models import Bill, BillLine
from app.schemas.bill import BillSummaryOut, DailyTotalOut


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min)
    return start, start + timedelta(days=1)


def list_bills(
    db: Session, day: date | None = None, bill_no: int | None = None, limit: int = 100
) -> list[Bill]:
    stmt = select(Bill)
    if bill_no is not None:
        stmt = stmt.where(Bill.bill_no == bill_no)
    if day is not None:
        start, end = _day_bounds(day)
        stmt = stmt.where(Bill.created_at >= start, Bill.created_at < end)
    stmt = stmt.order_by(Bill.bill_no.desc()).limit(limit)
    return list(db.execute(stmt).scalars().unique())


def get_bill_by_no(db: Session, bill_no: int) -> Bill:
    bill = db.execute(select(Bill).where(Bill.bill_no == bill_no)).scalars().unique().one_or_none()
    if bill is None:
        raise NotFoundError(f"No bill #{bill_no} was found.")
    return bill


def summarise(bill: Bill) -> BillSummaryOut:
    return BillSummaryOut(
        bill_no=bill.bill_no,
        created_at=bill.created_at,
        cashier_name=bill.cashier.name,
        item_count=sum(line.qty for line in bill.lines),
        summary=", ".join(f"{line.qty}× {line.product.name}" for line in bill.lines),
        total=bill.total,
        method=bill.payment.method,
    )


def daily_total(db: Session, day: date | None = None) -> DailyTotalOut:
    """Sum of one day's bills, plus the counts the Orders summary cards show."""
    day = day or date.today()
    start, end = _day_bounds(day)

    total, bill_count = db.execute(
        select(func.coalesce(func.sum(Bill.total), 0), func.count(Bill.id)).where(
            Bill.created_at >= start, Bill.created_at < end
        )
    ).one()

    item_count = db.execute(
        select(func.coalesce(func.sum(BillLine.qty), 0))
        .select_from(BillLine)
        .join(Bill, Bill.id == BillLine.bill_id)
        .where(Bill.created_at >= start, Bill.created_at < end)
    ).scalar_one()

    return DailyTotalOut(
        date=day, total=total, bill_count=bill_count, item_count=item_count
    )
