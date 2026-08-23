from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.models.transaction import Transaction, TransactionType
from app.services.transaction_service import get_recent_transactions

_NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)


def _add_txn(db, user_id, *, external_id, occurred_at=None, day=None, source="bitget", asset="BTC", price="50000", type_=TransactionType.buy):
    txn = Transaction(
        user_id=user_id,
        date=day or (occurred_at.date() if occurred_at else _NOW.date()),
        occurred_at=occurred_at,
        type=type_,
        asset=asset,
        amount=Decimal("0.1"),
        price=Decimal(price) if price is not None else None,
        fee=None,
        currency="EUR",
        source=source,
        external_id=external_id,
    )
    db.add(txn)
    db.commit()
    return txn


def test_returns_most_recent_first(db_session, test_user):
    _add_txn(db_session, test_user.id, external_id="t1", occurred_at=_NOW - timedelta(days=2))
    _add_txn(db_session, test_user.id, external_id="t2", occurred_at=_NOW)
    _add_txn(db_session, test_user.id, external_id="t3", occurred_at=_NOW - timedelta(days=1))

    results = get_recent_transactions(db_session, test_user.id)

    # SQLite has no tz-aware DateTime type -- values round-trip as naive UTC, so comparisons
    # here drop tzinfo too rather than asserting on it.
    assert [r.occurred_at for r in results] == [
        (_NOW).replace(tzinfo=None),
        (_NOW - timedelta(days=1)).replace(tzinfo=None),
        (_NOW - timedelta(days=2)).replace(tzinfo=None),
    ]


def test_computes_total_cost_from_price_and_quantity(db_session, test_user):
    _add_txn(db_session, test_user.id, external_id="t1", occurred_at=_NOW, price="50000")

    results = get_recent_transactions(db_session, test_user.id)

    assert results[0].price == Decimal("50000")
    assert results[0].total_cost == Decimal("5000.0")  # 0.1 * 50000


def test_deposit_without_price_has_no_total_cost(db_session, test_user):
    _add_txn(db_session, test_user.id, external_id="t1", occurred_at=_NOW, price=None, type_=TransactionType.deposit)

    results = get_recent_transactions(db_session, test_user.id)

    assert results[0].price is None
    assert results[0].total_cost is None


def test_source_is_mapped_to_display_label(db_session, test_user):
    _add_txn(db_session, test_user.id, external_id="t1", occurred_at=_NOW, source="bitget")
    _add_txn(db_session, test_user.id, external_id="t2", occurred_at=_NOW - timedelta(minutes=1), source="bitvavo")
    _add_txn(db_session, test_user.id, external_id="t3", occurred_at=_NOW - timedelta(minutes=2), source="coinbase")

    results = get_recent_transactions(db_session, test_user.id)

    assert [r.source for r in results] == ["Bitget", "Bitvavo", "Coinbase"]


def test_respects_limit(db_session, test_user):
    for i in range(15):
        _add_txn(db_session, test_user.id, external_id=f"t{i}", occurred_at=_NOW - timedelta(minutes=i))

    results = get_recent_transactions(db_session, test_user.id, limit=10)

    assert len(results) == 10


def test_ignores_other_users(db_session, test_user):
    other_user_id = test_user.id + 999
    _add_txn(db_session, other_user_id, external_id="t1", occurred_at=_NOW)

    results = get_recent_transactions(db_session, test_user.id)

    assert results == []


def test_legacy_row_without_occurred_at_still_sorts_by_date(db_session, test_user):
    # Rows synced before the occurred_at column existed only have `date` -- they must still
    # appear (and sort reasonably) rather than being silently excluded.
    _add_txn(db_session, test_user.id, external_id="t1", occurred_at=None, day=_NOW.date() - timedelta(days=5))
    _add_txn(db_session, test_user.id, external_id="t2", occurred_at=_NOW)

    results = get_recent_transactions(db_session, test_user.id)

    assert len(results) == 2
    assert results[0].occurred_at == _NOW.replace(tzinfo=None)
    assert results[1].occurred_at is None
