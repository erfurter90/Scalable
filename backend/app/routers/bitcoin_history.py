"""Router für Bitcoin-Preishistorie."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.services.bitcoin_price_history_service import (
    get_price_history,
    update_price_history,
    get_prices_for_date_range,
)

router = APIRouter(prefix="/api/bitcoin-history", tags=["bitcoin-history"])


@router.get("/prices")
async def get_prices(
    start_date: str = Query(None, description="Format: YYYY-MM-DD"),
    end_date: str = Query(None, description="Format: YYYY-MM-DD"),
):
    """
    Gib alle gespeicherten Bitcoin-Preise zurück.
    Falls start_date und end_date angegeben sind, nur Preise für diesen Bereich.
    """
    if start_date and end_date:
        prices = get_prices_for_date_range(start_date, end_date)
    else:
        result = get_price_history()
        prices = result.get("prices", [])

    return {
        "status": "ok",
        "prices": prices,
        "count": len(prices),
    }


@router.post("/update")
async def update_prices():
    """
    Aktualisiere die Bitcoin-Preishistorie mit dem heutigen Preis.
    Wird automatisch täglich aufgerufen, kann aber auch manuell getriggert werden.
    """
    history = await update_price_history()

    return {
        "status": "ok",
        "message": "Bitcoin price history updated",
        "last_updated": history.get("last_updated"),
        "total_days": len(history.get("prices", {})),
    }
