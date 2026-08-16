from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.financial_snapshot import EntryType
from app.models.user import User
from app.schemas.financial import (
    CostBasisSet,
    FinancialEntryCreate,
    FinancialEntryOut,
    FinancialEntryUpdate,
    NetWorthChangeOut,
    NetWorthSnapshotOut,
    PurchaseCreate,
)
from app.services import financial_service

router = APIRouter(prefix="/api/financials", tags=["financials"], dependencies=[Depends(get_current_user)])


@router.get("/entries", response_model=list[FinancialEntryOut])
def list_entries(
    entry_type: EntryType | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[FinancialEntryOut]:
    return financial_service.list_entries(db, current_user.id, entry_type, date_from, date_to)


@router.post("/entries", response_model=FinancialEntryOut, status_code=status.HTTP_201_CREATED)
def create_entry(
    body: FinancialEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FinancialEntryOut:
    try:
        return financial_service.create_entry(db, current_user.id, body)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.put("/entries/{entry_id}", response_model=FinancialEntryOut)
def update_entry(
    entry_id: int,
    body: FinancialEntryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FinancialEntryOut:
    try:
        entry = financial_service.update_entry(db, current_user.id, entry_id, body)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entry not found")
    return entry


@router.post("/entries/{entry_id}/refresh-value", response_model=FinancialEntryOut)
def refresh_entry_value(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FinancialEntryOut:
    try:
        entry = financial_service.refresh_entry_value(db, current_user.id, entry_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entry not found")
    return entry


@router.post("/entries/{entry_id}/add-purchase", response_model=FinancialEntryOut)
def add_purchase(
    entry_id: int,
    body: PurchaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FinancialEntryOut:
    try:
        entry = financial_service.add_purchase(
            db,
            current_user.id,
            entry_id,
            body.additional_quantity,
            body.purchase_price,
            body.purchase_price_currency,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entry not found")
    return entry


@router.post("/entries/{entry_id}/set-cost-basis", response_model=FinancialEntryOut)
def set_cost_basis(
    entry_id: int,
    body: CostBasisSet,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FinancialEntryOut:
    try:
        entry = financial_service.set_cost_basis(
            db, current_user.id, entry_id, body.purchase_price, body.purchase_price_currency
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entry not found")
    return entry


@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    deleted = financial_service.delete_entry(db, current_user.id, entry_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entry not found")


@router.get("/net-worth-history", response_model=list[NetWorthSnapshotOut])
def net_worth_history(
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[NetWorthSnapshotOut]:
    return financial_service.get_net_worth_history(db, current_user.id, date_from, date_to)


@router.get("/net-worth/current", response_model=NetWorthSnapshotOut)
def net_worth_current(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NetWorthSnapshotOut:
    snapshot = financial_service.get_current_net_worth(db, current_user.id)
    if snapshot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No financial data recorded yet")
    return snapshot


@router.get("/net-worth/change", response_model=NetWorthChangeOut)
def net_worth_change(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NetWorthChangeOut:
    change = financial_service.get_net_worth_change(db, current_user.id, days)
    if change is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not enough historical data for this period")
    return change
