import enum
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class EntryType(enum.StrEnum):
    income = "income"
    expense = "expense"
    asset = "asset"
    liability = "liability"


class AssetSubcategory(enum.StrEnum):
    """Only meaningful when entry_type == asset. Drives the portfolio allocation breakdown."""

    cash = "cash"
    btc = "btc"
    crypto = "crypto"
    stocks = "stocks"
    etf = "etf"
    other = "other"


class FinancialEntry(Base):
    """One line item (income source, expense category, asset holding, or liability) as of a
    given date. Append-only by design: a new snapshot_date gets new rows rather than mutating
    old ones, which makes historical time-series queries trivial and idempotent."""

    __tablename__ = "financial_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    entry_type: Mapped[EntryType] = mapped_column(Enum(EntryType, native_enum=False, length=16))
    category: Mapped[str] = mapped_column(String(64))  # e.g. "salary", "rent", "mortgage"
    subcategory: Mapped[str | None] = mapped_column(String(32), nullable=True)  # AssetSubcategory for assets
    label: Mapped[str] = mapped_column(String(128))  # user-facing name, e.g. "Bitvavo BTC"
    # Numeric(20, 8): comfortably covers plain EUR cents as well as an amount entered directly
    # in a crypto unit (e.g. currency="BTC", amount="0.04647339") without silently rounding
    # away the precision the user actually typed.
    amount: Mapped[float] = mapped_column(Numeric(20, 8))  # always positive; sign implied by entry_type
    currency: Mapped[str] = mapped_column(String(8), default="EUR")
    # Optional quantity-based valuation for btc/crypto assets: when set (together with
    # price_asset_id), `amount` is derived server-side as quantity * live price at
    # create/update/refresh time, rather than the user computing and typing a EUR figure
    # that immediately goes stale as the price moves. Always nullable/unused for every other
    # entry_type/subcategory.
    quantity: Mapped[float | None] = mapped_column(Numeric(30, 10), nullable=True)
    price_asset_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # CoinGecko coin id
    # Weighted-average acquisition price per unit, always in EUR (the app's base currency) —
    # a purchase entered in USD is converted at the current USD/EUR rate before blending in.
    # Only meaningful alongside quantity/price_asset_id; None if no purchase price was ever
    # recorded for this holding.
    average_cost_basis: Mapped[float | None] = mapped_column(Numeric(20, 8), nullable=True)
    snapshot_date: Mapped[date] = mapped_column(Date, index=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # "manual" (default, user-typed) or "bitvavo" (written by bitvavo_sync_service). Lets the
    # UI badge auto-synced holdings and lets the sync service safely find-and-replace only the
    # entries it owns without touching entries the user entered by hand for other assets.
    source: Mapped[str] = mapped_column(String(32), default="manual", server_default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class NetWorthSnapshot(Base):
    """Pre-aggregated per-day totals, recomputed whenever FinancialEntry rows change for that
    date. Exists purely so the dashboard doesn't re-sum every entry on every load."""

    __tablename__ = "net_worth_snapshots"
    __table_args__ = (UniqueConstraint("user_id", "snapshot_date", name="uq_net_worth_user_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    snapshot_date: Mapped[date] = mapped_column(Date, index=True)
    total_assets: Mapped[float] = mapped_column(Numeric(18, 2))
    total_liabilities: Mapped[float] = mapped_column(Numeric(18, 2))
    net_worth: Mapped[float] = mapped_column(Numeric(18, 2))
    cash_total: Mapped[float] = mapped_column(Numeric(18, 2))
    investments_total: Mapped[float] = mapped_column(Numeric(18, 2))  # btc + crypto + stocks + etf + other
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
