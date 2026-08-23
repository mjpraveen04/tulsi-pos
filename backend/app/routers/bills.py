from datetime import date

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas.bill import BillCreate, BillSummaryOut, DailyTotalOut, ReceiptOut
from app.security import get_current_user, require_manager
from app.services import billing as billing_service
from app.services import orders as orders_service

router = APIRouter(prefix="/api", tags=["bills"])


@router.post("/bills", response_model=ReceiptOut, status_code=status.HTTP_201_CREATED)
def create_bill(
    payload: BillCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReceiptOut:
    """The atomic sale. Cashiers and managers both ring up orders."""
    bill = billing_service.create_bill(db, current_user, payload)
    return billing_service.build_receipt(bill)


@router.get("/bills", response_model=list[BillSummaryOut])
def list_bills(
    date: date | None = None,
    bill_no: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[BillSummaryOut]:
    return [orders_service.summarise(b) for b in orders_service.list_bills(db, date, bill_no)]


@router.get("/bills/{bill_no}", response_model=ReceiptOut)
def get_bill(
    bill_no: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReceiptOut:
    """Full receipt at the original price-at-sale (FR-25/29)."""
    return billing_service.build_receipt(orders_service.get_bill_by_no(db, bill_no))


@router.get("/reports/daily-total", response_model=DailyTotalOut)
def daily_total(
    date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
) -> DailyTotalOut:
    return orders_service.daily_total(db, date)
