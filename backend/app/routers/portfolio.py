from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.portfolio import CryptoBreakdownOut, PortfolioAllocationOut
from app.services import portfolio_service

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"], dependencies=[Depends(get_current_user)])


@router.get("/allocation", response_model=PortfolioAllocationOut)
def allocation(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PortfolioAllocationOut:
    result = portfolio_service.get_allocation(db, current_user.id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No asset data recorded yet")
    return result


@router.get("/crypto-breakdown", response_model=CryptoBreakdownOut)
def crypto_breakdown(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CryptoBreakdownOut:
    result = portfolio_service.get_crypto_breakdown(db, current_user.id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No 'crypto' subcategory assets recorded yet")
    return result
