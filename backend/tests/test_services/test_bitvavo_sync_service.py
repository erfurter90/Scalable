"""End-to-end sync() flow with the Bitvavo HTTP layer replaced by a monkeypatched
BitvavoProvider — no live network calls, matching every other provider-backed test in this
suite. See test_exchange_sync_common.py for the exchange-agnostic compute_holding() replay
math (shared with bitget_sync_service)."""

from decimal import Decimal

import pytest

from app.core.config import get_settings
from app.models.financial_snapshot import FinancialEntry
from app.models.transaction import Transaction
from app.providers.bitvavo_provider import BitvavoProvider, BitvavoResult
from app.schemas.financial import FinancialEntryCreate
from app.services import bitvavo_sync_service, financial_service


@pytest.fixture(autouse=True)
def _mock_market_data(monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MODE", "mock")
    get_settings.cache_clear()
    monkeypatch.setattr(bitvavo_sync_service.time, "sleep", lambda *_: None)
    yield
    get_settings.cache_clear()


# ---- sync(): end-to-end with a monkeypatched provider -----------------------------------


def _patch_provider(monkeypatch, *, balances, trades_by_market=None, deposits=None, withdrawals=None):
    monkeypatch.setattr(BitvavoProvider, "is_configured", property(lambda self: True))
    monkeypatch.setattr(BitvavoProvider, "get_balance", lambda self, symbol=None: BitvavoResult("ok", balances))
    monkeypatch.setattr(
        BitvavoProvider,
        "get_trades",
        lambda self, market, limit=1000, trade_id_from=None: BitvavoResult(
            "ok", (trades_by_market or {}).get(market, [])
        ),
    )
    monkeypatch.setattr(
        BitvavoProvider, "get_deposit_history", lambda self, symbol=None, limit=1000: BitvavoResult("ok", deposits or [])
    )
    monkeypatch.setattr(
        BitvavoProvider,
        "get_withdrawal_history",
        lambda self, symbol=None, limit=1000: BitvavoResult("ok", withdrawals or []),
    )


def test_sync_not_configured(db_session, test_user, monkeypatch):
    monkeypatch.setattr(BitvavoProvider, "is_configured", property(lambda self: False))

    result = bitvavo_sync_service.sync(db_session, test_user.id)

    assert result.configured is False
    assert result.assets == []


def test_sync_creates_entry_from_trades(db_session, test_user, monkeypatch, today):
    _patch_provider(
        monkeypatch,
        balances=[{"symbol": "BTC", "available": "0.1", "inOrder": "0"}],
        trades_by_market={
            "BTC-EUR": [
                {"id": "trade-1", "timestamp": 1700000000000, "amount": "0.1", "price": "50000", "side": "buy", "fee": "0"}
            ]
        },
    )

    result = bitvavo_sync_service.sync(db_session, test_user.id)

    assert result.configured is True
    assert len(result.assets) == 1
    asset = result.assets[0]
    assert asset.symbol == "BTC"
    assert asset.quantity == Decimal("0.1")
    assert asset.average_cost_basis == Decimal("50000.00")
    assert asset.current_value_eur == Decimal("6000.00")  # mock bitcoin/eur price = 60000.00

    entry = db_session.query(FinancialEntry).filter(FinancialEntry.user_id == test_user.id).one()
    assert entry.source == "bitvavo"
    assert entry.price_asset_id == "bitcoin"
    assert entry.quantity == Decimal("0.1")

    transactions = db_session.query(Transaction).filter(Transaction.user_id == test_user.id).all()
    assert len(transactions) == 1
    assert transactions[0].external_id == "trade-1"


def test_sync_replaces_existing_manual_entry_labeled_as_bitvavo(db_session, test_user, monkeypatch, today):
    # A pre-existing manual entry the user already labeled as their Bitvavo holding (before
    # this feature existed) must be recognized and replaced on sync.
    manual_entry = financial_service.create_entry(
        db_session,
        test_user.id,
        FinancialEntryCreate(
            entry_type="asset",
            category="holding",
            subcategory="btc",
            label="Bitvavo Wallet",
            quantity=Decimal("0.05"),
            price_asset_id="bitcoin",
            snapshot_date=today,
        ),
    )
    assert manual_entry.source == "manual"

    _patch_provider(
        monkeypatch,
        balances=[{"symbol": "BTC", "available": "0.1", "inOrder": "0"}],
        trades_by_market={
            "BTC-EUR": [
                {"id": "trade-1", "timestamp": 1700000000000, "amount": "0.1", "price": "50000", "side": "buy", "fee": "0"}
            ]
        },
    )

    result = bitvavo_sync_service.sync(db_session, test_user.id)

    assert result.assets[0].replaced_entry_labels == ["Bitvavo Wallet"]
    remaining = db_session.query(FinancialEntry).filter(FinancialEntry.user_id == test_user.id).all()
    assert len(remaining) == 1
    assert remaining[0].source == "bitvavo"
    assert remaining[0].label == "Bitvavo"  # the old manual row is gone, not just updated


def test_sync_leaves_same_coin_held_elsewhere_untouched(db_session, test_user, monkeypatch, today):
    # The user can hold the same coin on Bitvavo AND on other platforms (Trade Republic,
    # Scalable, ...). Syncing Bitvavo must only ever touch the Bitvavo-labeled entry for a
    # coin, never entries for that same coin from unrelated sources -- matching on coin id
    # alone would silently delete holdings that have nothing to do with Bitvavo.
    trade_republic_entry = financial_service.create_entry(
        db_session,
        test_user.id,
        FinancialEntryCreate(
            entry_type="asset",
            category="holding",
            subcategory="btc",
            label="Trade Republic",
            quantity=Decimal("0.02"),
            price_asset_id="bitcoin",
            snapshot_date=today,
        ),
    )

    _patch_provider(
        monkeypatch,
        balances=[{"symbol": "BTC", "available": "0.1", "inOrder": "0"}],
        trades_by_market={
            "BTC-EUR": [
                {"id": "trade-1", "timestamp": 1700000000000, "amount": "0.1", "price": "50000", "side": "buy", "fee": "0"}
            ]
        },
    )

    result = bitvavo_sync_service.sync(db_session, test_user.id)

    assert result.assets[0].replaced_entry_labels == []
    still_there = db_session.query(FinancialEntry).filter(FinancialEntry.id == trade_republic_entry.id).first()
    assert still_there is not None
    assert still_there.quantity == Decimal("0.02")

    all_entries = db_session.query(FinancialEntry).filter(FinancialEntry.user_id == test_user.id).all()
    assert len(all_entries) == 2  # untouched Trade Republic entry + new Bitvavo entry
    labels = {entry.label for entry in all_entries}
    assert labels == {"Trade Republic", "Bitvavo"}


def test_sync_is_idempotent_and_picks_up_new_purchase_on_rerun(db_session, test_user, monkeypatch, today):
    _patch_provider(
        monkeypatch,
        balances=[{"symbol": "BTC", "available": "0.1", "inOrder": "0"}],
        trades_by_market={
            "BTC-EUR": [
                {"id": "trade-1", "timestamp": 1700000000000, "amount": "0.1", "price": "50000", "side": "buy", "fee": "0"}
            ]
        },
    )
    bitvavo_sync_service.sync(db_session, test_user.id)

    # Re-running with the exact same trades must not duplicate the Transaction row or change
    # the computed holding.
    result_again = bitvavo_sync_service.sync(db_session, test_user.id)
    assert result_again.assets[0].quantity == Decimal("0.1")
    assert db_session.query(Transaction).filter(Transaction.user_id == test_user.id).count() == 1

    # Simulate a new Sparplan purchase appearing on the next sync.
    _patch_provider(
        monkeypatch,
        balances=[{"symbol": "BTC", "available": "0.2", "inOrder": "0"}],
        trades_by_market={
            "BTC-EUR": [
                {"id": "trade-1", "timestamp": 1700000000000, "amount": "0.1", "price": "50000", "side": "buy", "fee": "0"},
                {"id": "trade-2", "timestamp": 1700100000000, "amount": "0.1", "price": "60000", "side": "buy", "fee": "0"},
            ]
        },
    )
    result_third = bitvavo_sync_service.sync(db_session, test_user.id)

    assert db_session.query(Transaction).filter(Transaction.user_id == test_user.id).count() == 2
    assert result_third.assets[0].quantity == Decimal("0.2")
    assert result_third.assets[0].average_cost_basis == Decimal("55000.00")


def test_sync_unmapped_symbol_records_transactions_without_entry(db_session, test_user, monkeypatch):
    _patch_provider(
        monkeypatch,
        balances=[{"symbol": "SOMECOIN", "available": "10", "inOrder": "0"}],
        trades_by_market={
            "SOMECOIN-EUR": [
                {"id": "trade-1", "timestamp": 1700000000000, "amount": "10", "price": "1", "side": "buy", "fee": "0"}
            ]
        },
    )

    result = bitvavo_sync_service.sync(db_session, test_user.id)

    assert result.assets[0].coingecko_id is None
    assert result.assets[0].note is not None
    assert db_session.query(FinancialEntry).filter(FinancialEntry.user_id == test_user.id).count() == 0
    assert db_session.query(Transaction).filter(Transaction.user_id == test_user.id).count() == 1


def test_sync_skips_zero_balance_symbols(db_session, test_user, monkeypatch):
    _patch_provider(monkeypatch, balances=[{"symbol": "BTC", "available": "0", "inOrder": "0"}])

    result = bitvavo_sync_service.sync(db_session, test_user.id)

    assert result.assets == []


def test_sync_price_unavailable_surfaces_error_without_crashing(db_session, test_user, monkeypatch):
    # "solana" has no mock price configured (see mock_provider._MOCK_COIN_PRICES) -- exercises
    # the compute_value_from_quantity failure path without a live network call.
    _patch_provider(
        monkeypatch,
        balances=[{"symbol": "SOL", "available": "5", "inOrder": "0"}],
        trades_by_market={
            "SOL-EUR": [
                {"id": "trade-1", "timestamp": 1700000000000, "amount": "5", "price": "20", "side": "buy", "fee": "0"}
            ]
        },
    )

    result = bitvavo_sync_service.sync(db_session, test_user.id)

    assert result.assets[0].error is not None
    assert db_session.query(FinancialEntry).filter(FinancialEntry.user_id == test_user.id).count() == 0
