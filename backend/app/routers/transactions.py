from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.transaction import RecentTransactionOut
from app.services import transaction_service

router = APIRouter(prefix="/api/transactions", tags=["transactions"], dependencies=[Depends(get_current_user)])


@router.get("/recent", response_model=list[RecentTransactionOut])
def recent(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[RecentTransactionOut]:
    return transaction_service.get_recent_transactions(db, current_user.id, limit=10)
