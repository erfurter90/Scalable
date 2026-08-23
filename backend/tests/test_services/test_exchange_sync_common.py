"""compute_holding() replay-ledger math — exchange-agnostic, so tested once here against a
fixed `source` rather than duplicated per exchange."""

from decimal import Decimal

from app.models.transaction import Transaction, TransactionType
from app.services.exchange_sync_common import compute_holding

_SOURCE = "bitvavo"


def _add_txn(db, user_id, *, type_, amount, price=None, fee=None, asset="BTC", external_id, day, source=_SOURCE):
    txn = Transaction(
        user_id=user_id,
        date=day,
        type=type_,
        asset=asset,
        amount=Decimal(amount),
        price=Decimal(price) if price is not None else None,
        fee=Decimal(fee) if fee is not None else None,
        currency="EUR",
        source=source,
        external_id=external_id,
    )
    db.add(txn)
    db.commit()
    return txn


def test_compute_holding_single_buy(db_session, test_user, today):
    _add_txn(db_session, test_user.id, type_=TransactionType.buy, amount="0.1", price="50000", external_id="t1", day=today)

    holding = compute_holding(db_session, test_user.id, "BTC", _SOURCE)

    assert holding.quantity == Decimal("0.1")
    assert holding.average_cost_basis == Decimal("50000.00")  # (0.1 * 50000) / 0.1
    assert holding.cost_basis_incomplete is False


def test_compute_holding_two_buys_weighted_average(db_session, test_user, today):
    _add_txn(db_session, test_user.id, type_=TransactionType.buy, amount="0.1", price="50000", external_id="t1", day=today)
    _add_txn(db_session, test_user.id, type_=TransactionType.buy, amount="0.1", price="60000", external_id="t2", day=today)

    holding = compute_holding(db_session, test_user.id, "BTC", _SOURCE)

    # (0.1*50000 + 0.1*60000) / 0.2 = 55000.00 -- same formula as add_purchase's blend
    assert holding.quantity == Decimal("0.2")
    assert holding.average_cost_basis == Decimal("55000.00")


def test_compute_holding_buy_includes_fee(db_session, test_user, today):
    _add_txn(db_session, test_user.id, type_=TransactionType.buy, amount="0.1", price="50000", fee="10", external_id="t1", day=today)

    holding = compute_holding(db_session, test_user.id, "BTC", _SOURCE)

    # (0.1*50000 + 10) / 0.1 = 5010 / 0.1 = 50100.00
    assert holding.average_cost_basis == Decimal("50100.00")


def test_compute_holding_sell_reduces_proportionally(db_session, test_user, today):
    _add_txn(db_session, test_user.id, type_=TransactionType.buy, amount="0.2", price="50000", external_id="t1", day=today)
    _add_txn(db_session, test_user.id, type_=TransactionType.sell, amount="0.1", price="70000", external_id="t2", day=today)

    holding = compute_holding(db_session, test_user.id, "BTC", _SOURCE)

    # selling half the position removes half the cost total too, regardless of sale price --
    # weighted-average cost basis is unaffected by the price actually realized on the sale.
    assert holding.quantity == Decimal("0.1")
    assert holding.average_cost_basis == Decimal("50000.00")


def test_compute_holding_withdrawal_reduces_like_a_sell(db_session, test_user, today):
    _add_txn(db_session, test_user.id, type_=TransactionType.buy, amount="0.2", price="50000", external_id="t1", day=today)
    _add_txn(db_session, test_user.id, type_=TransactionType.withdrawal, amount="0.1", external_id="t2", day=today)

    holding = compute_holding(db_session, test_user.id, "BTC", _SOURCE)

    assert holding.quantity == Decimal("0.1")
    assert holding.average_cost_basis == Decimal("50000.00")


def test_compute_holding_deposit_marks_cost_basis_incomplete(db_session, test_user, today):
    _add_txn(db_session, test_user.id, type_=TransactionType.buy, amount="0.1", price="50000", external_id="t1", day=today)
    _add_txn(db_session, test_user.id, type_=TransactionType.deposit, amount="0.05", external_id="t2", day=today)

    holding = compute_holding(db_session, test_user.id, "BTC", _SOURCE)

    # Quantity still counts the deposited coins, but since we don't know what they cost, the
    # app must not present a cost basis as if it were exact.
    assert holding.quantity == Decimal("0.15")
    assert holding.cost_basis_incomplete is True
    assert holding.average_cost_basis is None


def test_compute_holding_fully_sold_returns_zero_quantity(db_session, test_user, today):
    _add_txn(db_session, test_user.id, type_=TransactionType.buy, amount="0.1", price="50000", external_id="t1", day=today)
    _add_txn(db_session, test_user.id, type_=TransactionType.sell, amount="0.1", price="70000", external_id="t2", day=today)

    holding = compute_holding(db_session, test_user.id, "BTC", _SOURCE)

    assert holding.quantity == Decimal("0")
    assert holding.average_cost_basis is None


def test_compute_holding_ignores_other_users_and_other_assets(db_session, test_user, today):
    _add_txn(db_session, test_user.id, type_=TransactionType.buy, amount="0.1", price="50000", asset="ETH", external_id="t1", day=today)

    holding = compute_holding(db_session, test_user.id, "BTC", _SOURCE)

    assert holding.quantity == Decimal("0")


def test_compute_holding_ignores_other_sources(db_session, test_user, today):
    # A Bitget BTC transaction must not leak into a Bitvavo holding computation for the same
    # coin -- each exchange's replay is scoped strictly to its own `source` tag.
    _add_txn(db_session, test_user.id, type_=TransactionType.buy, amount="0.1", price="50000", external_id="t1", day=today, source="bitget")

    holding = compute_holding(db_session, test_user.id, "BTC", "bitvavo")

    assert holding.quantity == Decimal("0")
