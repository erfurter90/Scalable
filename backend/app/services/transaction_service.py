"""Read-only queries over the Transaction audit log (see app/models/transaction.py) for
user-facing "what happened recently" displays -- distinct from exchange_sync_common's
write-side upsert_transaction, which is exchange sync's own concern."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.transaction import Transaction

_SOURCE_LABELS = {"bitvavo": "Bitvavo", "bitget": "Bitget", "coinbase": "Coinbase"}


@dataclass
class RecentTransaction:
    source: str
    asset: str
    quantity: Decimal
    price: Decimal | None
    total_cost: Decimal | None
    occurred_at: datetime | None


def _source_label(source: str) -> str:
    return _SOURCE_LABELS.get(source, source.capitalize())


def get_recent_transactions(db: Session, user_id: int, limit: int = 10) -> list[RecentTransaction]:
    """Most recent transactions across every source, newest first. Sorts by `occurred_at`
    (full timestamp) but falls back to the day-only `date` column for the handful of rows
    synced before `occurred_at` existed, so they still sort sensibly instead of landing
    arbitrarily rather than at the bottom."""
    rows = (
        db.query(Transaction)
        .filter(Transaction.user_id == user_id)
        .order_by(func.coalesce(Transaction.occurred_at, Transaction.date).desc(), Transaction.id.desc())
        .limit(limit)
        .all()
    )
    results = []
    for row in rows:
        price = Decimal(str(row.price)) if row.price is not None else None
        quantity = Decimal(str(row.amount))
        results.append(
            RecentTransaction(
                source=_source_label(row.source),
                asset=row.asset,
                quantity=quantity,
                price=price,
                total_cost=(price * quantity) if price is not None else None,
                occurred_at=row.occurred_at,
            )
        )
    return results
