"""Combines net worth, portfolio allocation, market snapshot, and the BTC score into the
single payload the dashboard page needs. Pure orchestration — all the actual math lives in
the services this calls."""

from sqlalchemy.orm import Session

from app.schemas.dashboard import DashboardOut
from app.schemas.financial import NetWorthChangeOut
from app.services import (
    financial_service,
    market_data_service,
    portfolio_service,
    score_service,
)


def get_dashboard(db: Session, user_id: int) -> DashboardOut:
    net_worth = financial_service.get_current_net_worth(db, user_id)
    net_worth_change = financial_service.get_net_worth_change(db, user_id, days=30)
    portfolio = portfolio_service.get_allocation(db, user_id)
    crypto_breakdown = portfolio_service.get_crypto_breakdown(db, user_id)
    market = market_data_service.get_snapshot(db)

    score_row, score_result, weights = score_service.compute_and_store_score(db)
    score = score_service.to_score_out(score_result, weights, score_row.score_date)

    return DashboardOut(
        net_worth=net_worth,
        net_worth_change_30d=NetWorthChangeOut(**net_worth_change) if net_worth_change else None,
        portfolio=portfolio,
        crypto_breakdown=crypto_breakdown,
        market=market,
        score=score,
    )
