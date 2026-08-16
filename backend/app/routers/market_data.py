from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.schemas.market_data import BtcPriceOut, FearGreedOut, MarketSnapshotOut
from app.services import market_data_service

router = APIRouter(prefix="/api/market", tags=["market"], dependencies=[Depends(get_current_user)])


@router.get("/btc-price", response_model=BtcPriceOut)
def btc_price(db: Session = Depends(get_db)) -> BtcPriceOut:
    return market_data_service.get_btc_price(db)


@router.get("/fear-greed", response_model=FearGreedOut)
def fear_greed(db: Session = Depends(get_db)) -> FearGreedOut:
    return market_data_service.get_fear_greed(db)


@router.get("/snapshot", response_model=MarketSnapshotOut)
def snapshot(db: Session = Depends(get_db)) -> MarketSnapshotOut:
    return market_data_service.get_snapshot(db)
