"""End-to-end sync() flow with the Coinbase HTTP layer replaced by a monkeypatched
CoinbaseProvider — no live network calls. See test_exchange_sync_common.py for the shared
replay math and test_bitget_sync_service.py for the equivalent Bitget flow (the quantity-
reconciliation and price-failure-safety patterns are identical, ported over here too)."""

from decimal import Decimal

import pytest

from app.core.config import get_settings
from app.models.financial_snapshot import FinancialEntry
from app.models.transaction import Transaction
from app.providers.coinbase_provider import CoinbaseProvider, CoinbaseResult
from app.schemas.financial import FinancialEntryCreate
from app.services import coinbase_sync_service, financial_service


@pytest.fixture(autouse=True)
def _mock_market_data_and_pacing(monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MODE", "mock")
    get_settings.cache_clear()
    monkeypatch.setattr(coinbase_sync_service.time, "sleep", lambda *_: None)
    yield
    get_settings.cache_clear()


def _account(currency, available="0", hold="0"):
    return {"currency": currency, "available_balance": {"value": available}, "hold": {"value": hold}}


def _fill(product_id, price, size, side, trade_id, trade_time="2024-07-05T12:00:00Z", commission=None):
    fill = {
        "product_id": product_id,
        "price": price,
        "size": size,
        "side": side,
        "trade_id": trade_id,
        "trade_time": trade_time,
    }
    if commission is not None:
        fill["commission"] = commission
    return fill


def _patch_provider(monkeypatch, *, accounts, fills=None):
    """Single-page responses (has_next=False) unless a test overrides it directly."""
    monkeypatch.setattr(CoinbaseProvider, "is_configured", property(lambda self: True))
    monkeypatch.setattr(
        CoinbaseProvider, "get_accounts", lambda self, cursor=None: CoinbaseResult("ok", {"accounts": accounts, "has_next": False})
    )
    monkeypatch.setattr(
        CoinbaseProvider,
        "get_fills",
        lambda self, cursor=None, product_ids=None: CoinbaseResult("ok", {"fills": fills or [], "has_next": False}),
    )


def test_sync_not_configured(db_session, test_user, monkeypatch):
    monkeypatch.setattr(CoinbaseProvider, "is_configured", property(lambda self: False))

    result = coinbase_sync_service.sync(db_session, test_user.id)

    assert result.configured is False
    assert result.assets == []


def test_sync_buy_fill_eur_quoted_creates_entry(db_session, test_user, monkeypatch):
    _patch_provider(
        monkeypatch,
        accounts=[_account("BTC", available="0.1")],
        fills=[_fill("BTC-EUR", "50000", "0.1", "BUY", "t1")],
    )

    result = coinbase_sync_service.sync(db_session, test_user.id)

    assert result.configured is True
    asset = result.assets[0]
    assert asset.symbol == "BTC"
    assert asset.quantity == Decimal("0.1")
    assert asset.average_cost_basis == Decimal("50000.00")
    assert asset.current_value_eur == Decimal("6000.00")  # mock bitcoin/eur price = 60000.00

    entry = db_session.query(FinancialEntry).filter(FinancialEntry.user_id == test_user.id).one()
    assert entry.source == "coinbase"
    assert entry.label == "Coinbase"

    txn = db_session.query(Transaction).filter(Transaction.user_id == test_user.id).one()
    assert txn.external_id == "fill:t1"
    assert txn.currency == "EUR"


def test_sync_buy_fill_usd_quoted_converts_to_eur(db_session, test_user, monkeypatch):
    _patch_provider(
        monkeypatch,
        accounts=[_account("BTC", available="0.1")],
        fills=[_fill("BTC-USD", "50000", "0.1", "BUY", "t1")],
    )

    result = coinbase_sync_service.sync(db_session, test_user.id)

    # mock USD/EUR rate = 0.92 -> 50000 * 0.92 = 46000.00
    assert result.assets[0].average_cost_basis == Decimal("46000.00")


def test_sync_includes_fee_in_cost_basis(db_session, test_user, monkeypatch):
    _patch_provider(
        monkeypatch,
        accounts=[_account("BTC", available="0.1")],
        fills=[_fill("BTC-EUR", "50000", "0.1", "BUY", "t1", commission="10")],
    )

    result = coinbase_sync_service.sync(db_session, test_user.id)

    # (0.1*50000 + 10) / 0.1 = 5010 / 0.1 = 50100.00
    assert result.assets[0].average_cost_basis == Decimal("50100.00")


def test_sync_sell_fill_reduces_quantity(db_session, test_user, monkeypatch):
    _patch_provider(
        monkeypatch,
        accounts=[_account("BTC", available="0.05")],
        fills=[
            _fill("BTC-EUR", "50000", "0.1", "BUY", "t1", trade_time="2024-01-01T00:00:00Z"),
            _fill("BTC-EUR", "70000", "0.05", "SELL", "t2", trade_time="2024-02-01T00:00:00Z"),
        ],
    )

    result = coinbase_sync_service.sync(db_session, test_user.id)

    assert result.assets[0].quantity == Decimal("0.05")
    assert result.assets[0].average_cost_basis == Decimal("50000.00")  # unaffected by sale price


def test_sync_skips_unsupported_quote_currency(db_session, test_user, monkeypatch):
    _patch_provider(
        monkeypatch,
        accounts=[_account("BTC", available="0.1")],
        fills=[_fill("BTC-GBP", "45000", "0.1", "BUY", "t1")],
    )

    result = coinbase_sync_service.sync(db_session, test_user.id)

    # no transaction recorded at all for an unsupported quote -- and since compute_holding()
    # then sees zero replayed history against a real 0.1 balance, the mismatch fallback kicks
    # in and still surfaces the real quantity (with cost basis withheld).
    assert db_session.query(Transaction).filter(Transaction.user_id == test_user.id).count() == 0
    assert result.assets[0].quantity == Decimal("0.1")
    assert result.assets[0].average_cost_basis is None
    assert result.assets[0].cost_basis_incomplete is True


def test_sync_replaces_existing_manual_entry_labeled_as_coinbase(db_session, test_user, monkeypatch, today):
    manual_entry = financial_service.create_entry(
        db_session,
        test_user.id,
        FinancialEntryCreate(
            entry_type="asset", category="holding", subcategory="btc", label="Coinbase BTC",
            quantity=Decimal("0.05"), price_asset_id="bitcoin", snapshot_date=today,
        ),
    )
    assert manual_entry.source == "manual"

    _patch_provider(
        monkeypatch,
        accounts=[_account("BTC", available="0.1")],
        fills=[_fill("BTC-EUR", "50000", "0.1", "BUY", "t1")],
    )

    result = coinbase_sync_service.sync(db_session, test_user.id)

    assert result.assets[0].replaced_entry_labels == ["Coinbase BTC"]
    remaining = db_session.query(FinancialEntry).filter(FinancialEntry.user_id == test_user.id).all()
    assert len(remaining) == 1
    assert remaining[0].source == "coinbase"
    assert remaining[0].label == "Coinbase"


def test_sync_leaves_same_coin_held_elsewhere_untouched(db_session, test_user, monkeypatch, today):
    trade_republic_entry = financial_service.create_entry(
        db_session,
        test_user.id,
        FinancialEntryCreate(
            entry_type="asset", category="holding", subcategory="btc", label="Trade Republic",
            quantity=Decimal("0.02"), price_asset_id="bitcoin", snapshot_date=today,
        ),
    )

    _patch_provider(
        monkeypatch,
        accounts=[_account("BTC", available="0.1")],
        fills=[_fill("BTC-EUR", "50000", "0.1", "BUY", "t1")],
    )

    result = coinbase_sync_service.sync(db_session, test_user.id)

    assert result.assets[0].replaced_entry_labels == []
    still_there = db_session.query(FinancialEntry).filter(FinancialEntry.id == trade_republic_entry.id).first()
    assert still_there is not None
    assert still_there.quantity == Decimal("0.02")

    labels = {e.label for e in db_session.query(FinancialEntry).filter(FinancialEntry.user_id == test_user.id).all()}
    assert labels == {"Trade Republic", "Coinbase"}


def test_sync_is_idempotent_and_picks_up_new_purchase_on_rerun(db_session, test_user, monkeypatch):
    _patch_provider(
        monkeypatch,
        accounts=[_account("BTC", available="0.1")],
        fills=[_fill("BTC-EUR", "50000", "0.1", "BUY", "t1")],
    )
    coinbase_sync_service.sync(db_session, test_user.id)
    result_again = coinbase_sync_service.sync(db_session, test_user.id)

    assert result_again.assets[0].quantity == Decimal("0.1")
    assert db_session.query(Transaction).filter(Transaction.user_id == test_user.id).count() == 1

    _patch_provider(
        monkeypatch,
        accounts=[_account("BTC", available="0.2")],
        fills=[
            _fill("BTC-EUR", "50000", "0.1", "BUY", "t1"),
            _fill("BTC-EUR", "50000", "0.1", "BUY", "t2", trade_time="2024-08-01T00:00:00Z"),
        ],
    )
    result_third = coinbase_sync_service.sync(db_session, test_user.id)

    assert db_session.query(Transaction).filter(Transaction.user_id == test_user.id).count() == 2
    assert result_third.assets[0].quantity == Decimal("0.2")


def test_sync_paginates_fills_across_multiple_pages(db_session, test_user, monkeypatch):
    monkeypatch.setattr(CoinbaseProvider, "is_configured", property(lambda self: True))
    monkeypatch.setattr(
        CoinbaseProvider,
        "get_accounts",
        lambda self, cursor=None: CoinbaseResult("ok", {"accounts": [_account("BTC", available="0.2")], "has_next": False}),
    )

    pages = [
        {"fills": [_fill("BTC-EUR", "50000", "0.1", "BUY", "t1")], "has_next": True, "cursor": "page2"},
        {"fills": [_fill("BTC-EUR", "50000", "0.1", "BUY", "t2", trade_time="2024-08-01T00:00:00Z")], "has_next": False},
    ]
    calls = {"n": 0}

    def _get_fills(self, cursor=None, product_ids=None):
        page = pages[calls["n"]]
        calls["n"] += 1
        return CoinbaseResult("ok", page)

    monkeypatch.setattr(CoinbaseProvider, "get_fills", _get_fills)

    result = coinbase_sync_service.sync(db_session, test_user.id)

    assert calls["n"] == 2
    assert db_session.query(Transaction).filter(Transaction.user_id == test_user.id).count() == 2
    assert result.assets[0].quantity == Decimal("0.2")


def test_sync_unmapped_symbol_records_transactions_without_entry(db_session, test_user, monkeypatch):
    _patch_provider(
        monkeypatch,
        accounts=[_account("SOMECOIN", available="10")],
        fills=[_fill("SOMECOIN-EUR", "1", "10", "BUY", "t1")],
    )

    result = coinbase_sync_service.sync(db_session, test_user.id)

    assert result.assets[0].coingecko_id is None
    assert result.assets[0].note is not None
    assert db_session.query(FinancialEntry).filter(FinancialEntry.user_id == test_user.id).count() == 0
    assert db_session.query(Transaction).filter(Transaction.user_id == test_user.id).count() == 1


def test_sync_skips_zero_balance_symbols(db_session, test_user, monkeypatch):
    _patch_provider(monkeypatch, accounts=[_account("BTC", available="0")])

    result = coinbase_sync_service.sync(db_session, test_user.id)

    assert result.assets == []


def test_sync_skips_quote_currency_accounts(db_session, test_user, monkeypatch):
    _patch_provider(monkeypatch, accounts=[_account("EUR", available="500"), _account("USD", available="100")])

    result = coinbase_sync_service.sync(db_session, test_user.id)

    assert result.assets == []


def test_sync_falls_back_to_real_balance_when_history_is_incomplete(db_session, test_user, monkeypatch):
    # Confirmed on Bitget: a coin can have a much larger balance than its captured buy/sell
    # history explains (e.g. an initial acquisition older than the fills history covers).
    _patch_provider(
        monkeypatch,
        accounts=[_account("BTC", available="0.1")],
        fills=[
            _fill("BTC-EUR", "50000", "0.08", "BUY", "t1", trade_time="2024-01-01T00:00:00Z"),
            _fill("BTC-EUR", "50000", "0.5", "SELL", "t2", trade_time="2024-02-01T00:00:00Z"),
        ],
    )

    result = coinbase_sync_service.sync(db_session, test_user.id)

    asset = result.assets[0]
    assert asset.quantity == Decimal("0.1")  # the real Coinbase balance, not the replay's ~0
    assert asset.cost_basis_incomplete is True
    assert asset.average_cost_basis is None


def test_sync_price_failure_leaves_existing_entry_untouched(db_session, test_user, monkeypatch, today):
    existing_entry = financial_service.create_entry(
        db_session,
        test_user.id,
        FinancialEntryCreate(
            entry_type="asset", category="holding", subcategory="crypto", label="Coinbase SOL",
            amount=Decimal("500.00"), quantity=Decimal("5"), price_asset_id="solana", snapshot_date=today,
        ),
    )

    # "solana" has no mock price configured (see mock_provider._MOCK_COIN_PRICES) -- exercises
    # the compute_value_from_quantity failure path without a live network call.
    _patch_provider(
        monkeypatch,
        accounts=[_account("SOL", available="5")],
        fills=[_fill("SOL-EUR", "20", "5", "BUY", "t1")],
    )

    result = coinbase_sync_service.sync(db_session, test_user.id)

    assert result.assets[0].error is not None
    assert result.assets[0].replaced_entry_labels == []
    still_there = db_session.query(FinancialEntry).filter(FinancialEntry.id == existing_entry.id).first()
    assert still_there is not None
    assert still_there.quantity == Decimal("5")


def test_sync_fx_rate_unavailable_fails_fast_with_clear_error(db_session, test_user, monkeypatch):
    from app.models.market_data import DataPointStatus, MarketDataPoint

    monkeypatch.setattr(
        "app.services.market_data_service.get_fresh",
        lambda db, metric, max_age_seconds=None: MarketDataPoint(
            metric="fx_usd_eur", status=DataPointStatus.error, value=None, source="mock"
        ),
    )
    _patch_provider(monkeypatch, accounts=[_account("BTC", available="0.1")])

    result = coinbase_sync_service.sync(db_session, test_user.id)

    assert result.configured is True
    assert result.error is not None
    assert result.assets == []
