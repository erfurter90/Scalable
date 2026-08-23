from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.rate_limit import limiter
from app.models.user import User
from app.providers.coinbase_provider import CoinbaseProvider
from app.schemas.coinbase import CoinbaseStatusOut, CoinbaseSyncResultOut
from app.services import coinbase_sync_service

router = APIRouter(prefix="/api/integrations/coinbase", tags=["coinbase"], dependencies=[Depends(get_current_user)])


@router.get("/status", response_model=CoinbaseStatusOut)
def status() -> CoinbaseStatusOut:
    return CoinbaseStatusOut(configured=CoinbaseProvider().is_configured)


@router.post("/sync", response_model=CoinbaseSyncResultOut)
@limiter.limit("5/minute")  # each sync fans out into several external API calls per held asset
def sync(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CoinbaseSyncResultOut:
    return coinbase_sync_service.sync(db, current_user.id)
