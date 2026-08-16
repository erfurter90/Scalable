from pydantic import BaseModel

from app.schemas.financial import NetWorthChangeOut, NetWorthSnapshotOut
from app.schemas.market_data import MarketSnapshotOut
from app.schemas.portfolio import CryptoBreakdownOut, PortfolioAllocationOut
from app.schemas.score import ScoreOut


class DashboardOut(BaseModel):
    """One aggregate payload for the whole dashboard page — net worth, portfolio, and
    portfolio/net-worth fields are None until the user has recorded at least one entry;
    market and score are always present since they don't depend on user data (their
    individual metrics may still be status="unavailable")."""

    net_worth: NetWorthSnapshotOut | None
    net_worth_change_30d: NetWorthChangeOut | None
    portfolio: PortfolioAllocationOut | None
    crypto_breakdown: CryptoBreakdownOut | None
    market: MarketSnapshotOut
    score: ScoreOut
