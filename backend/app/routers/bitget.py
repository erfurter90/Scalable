from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.rate_limit import limiter
from app.models.user import User
from app.providers.bitget_provider import BitgetProvider
from app.schemas.bitget import BitgetStatusOut, BitgetSyncResultOut
from app.services import bitget_sync_service

router = APIRouter(prefix="/api/integrations/bitget", tags=["bitget"], dependencies=[Depends(get_current_user)])


@router.get("/status", response_model=BitgetStatusOut)
def status() -> BitgetStatusOut:
    return BitgetStatusOut(configured=BitgetProvider().is_configured)


@router.post("/sync", response_model=BitgetSyncResultOut)
@limiter.limit("5/minute")  # each sync fans out into several external API calls per held asset
def sync(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BitgetSyncResultOut:
    return bitget_sync_service.sync(db, current_user.id)
