"""Importing this package registers every model on Base.metadata, which Alembic
autogenerate and `Base.metadata.create_all()` (used by tests) both rely on."""

from app.models.financial_snapshot import (
    AssetSubcategory,
    EntryType,
    FinancialEntry,
    NetWorthSnapshot,
)
from app.models.market_data import DataPointStatus, MarketDataPoint
from app.models.score_history import ScoreHistory
from app.models.scoring_config import ScoringWeightsConfig
from app.models.transaction import Transaction, TransactionType
from app.models.user import User

__all__ = [
    "AssetSubcategory",
    "DataPointStatus",
    "EntryType",
    "FinancialEntry",
    "MarketDataPoint",
    "NetWorthSnapshot",
    "ScoreHistory",
    "ScoringWeightsConfig",
    "Transaction",
    "TransactionType",
    "User",
]
