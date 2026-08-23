import enum
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Enum, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class TransactionType(enum.StrEnum):
    buy = "buy"
    sell = "sell"
    deposit = "deposit"
    withdrawal = "withdrawal"
    fee = "fee"
    dividend = "dividend"
    interest = "interest"


class Transaction(Base):
    """Generic transaction-import schema (section 13 of the spec). Modeled now but not yet
    wired to any UI/endpoint in the MVP — it exists so a future CSV importer (bank exports,
    Trade Republic, Bitvavo, Coinbase, ...) has a stable target without a schema migration."""

    __tablename__ = "transactions"
    __table_args__ = (UniqueConstraint("user_id", "source", "external_id", name="uq_transaction_user_source_external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    # Full timestamp (UTC) when known -- `date` above only ever held day precision, but every
    # exchange source actually reports a precise time, so this is populated alongside it for
    # displays that need time-of-day (e.g. a "recent transactions" widget). Nullable because
    # rows synced before this field existed have no way to recover the dropped time.
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType, native_enum=False, length=16))
    asset: Mapped[str] = mapped_column(String(32))  # "BTC", "EUR", "AAPL", ...
    amount: Mapped[float] = mapped_column(Numeric(30, 10))  # quantity of asset
    price: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)  # per unit, in `currency`
    fee: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    currency: Mapped[str] = mapped_column(String(8))
    source: Mapped[str] = mapped_column(String(32))  # "trade_republic", "bitvavo", "coinbase", "manual", ...
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)  # dedupe key from source
    raw_row_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
