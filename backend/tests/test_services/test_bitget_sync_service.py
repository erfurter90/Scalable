"""End-to-end sync() flow with the Bitget HTTP layer replaced by a monkeypatched
BitgetProvider — no live network calls. Fixtures use the real record shape confirmed against
a live Bitget account during development: paired Buy/Sell legs sharing a bizOrderId, plus
single-row Deposit/Transfer records. See test_exchange_sync_common.py for the shared replay
math and test_bitvavo_sync_service.py for the equivalent Bitvavo flow."""

from decimal import Decimal

import pytest

from app.core.config import get_settings
from app.models.financial_snapshot import FinancialEntry
from app.models.transaction import Transaction
from app.providers.bitget_provider import BitgetProvider, BitgetResult
from app.schemas.financial import FinancialEntryCreate
from app.services import bitget_sync_service, financial_service


@pytest.fixture(autouse=True)
def _mock_market_data_and_pacing(monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MODE", "mock")
    get_settings.cache_clear()
    monkeypatch.setattr(bitget_sync_service.time, "sleep", lambda *_: None)  # skip pagination pacing delay in tests
    yield
    get_settings.cache_clear()


def _patch_provider(monkeypatch, *, balances, records=None):
    """Simulates one populated 29-day window (`records`) followed by empty older windows,
    same as a real account whose visible history fits in the most recent page."""
    monkeypatch.setattr(BitgetProvider, "is_configured", property(lambda self: True))
    monkeypatch.setattr(BitgetProvider, "get_balance", lambda self, coin=None: BitgetResult("ok", balances))

    calls = {"n": 0}

    def _get_records(self, start_time_ms, end_time_ms, limit=100):
        calls["n"] += 1
        return BitgetResult("ok", records if calls["n"] == 1 else [])

    monkeypatch.setattr(BitgetProvider, "get_tax_spot_records", _get_records)


def _buy_leg(coin, amount, ts="1700000000000", biz="biz-1"):
    return {"id": f"{biz}-buy", "coin": coin, "spotTaxType": "Buy", "amount": amount, "fee": "0", "ts": ts, "bizOrderId": biz}


def _sell_leg(coin, amount, ts="1700000000000", biz="biz-1"):
    return {"id": f"{biz}-sell", "coin": coin, "spotTaxType": "Sell", "amount": amount, "fee": "0", "ts": ts, "bizOrderId": biz}


def test_sync_not_configured(db_session, test_user, monkeypatch):
    monkeypatch.setattr(BitgetProvider, "is_configured", property(lambda self: False))

    result = bitget_sync_service.sync(db_session, test_user.id)

    assert result.configured is False
    assert result.assets == []


def test_sync_buy_leg_creates_entry_converting_usdt_to_eur(db_session, test_user, monkeypatch):
    # Bought 0.1 BTC, paid 5000 USDT -> price = 50000 USDT/BTC -> mock rate 0.92 -> 46000.00 EUR
    _patch_provider(
        monkeypatch,
        balances=[{"coin": "BTC", "available": "0.1", "frozen": "0", "locked": "0"}],
        records=[_buy_leg("BTC", "0.1"), _sell_leg("USDT", "-5000")],
    )

    result = bitget_sync_service.sync(db_session, test_user.id)

    assert result.configured is True
    asset = result.assets[0]
    assert asset.symbol == "BTC"
    assert asset.quantity == Decimal("0.1")
    assert asset.average_cost_basis == Decimal("46000.00")
    assert asset.current_value_eur == Decimal("6000.00")  # mock bitcoin/eur price = 60000.00

    entry = db_session.query(FinancialEntry).filter(FinancialEntry.user_id == test_user.id).one()
    assert entry.source == "bitget"
    assert entry.label == "Bitget"

    transactions = db_session.query(Transaction).filter(Transaction.user_id == test_user.id).all()
    assert len(transactions) == 1
    assert transactions[0].external_id == "trade:biz-1"


def test_sync_handles_sell_leg_as_the_tracked_coin(db_session, test_user, monkeypatch):
    # Selling BTC for USDT: BTC is the "Sell" leg, USDT is the "Buy" leg -- must still be
    # recognized as a BTC transaction (direction isn't fixed to "crypto is always base").
    _patch_provider(
        monkeypatch,
        balances=[{"coin": "BTC", "available": "0.05", "frozen": "0", "locked": "0"}],
        records=[
            _buy_leg("BTC", "0.1", ts="1699000000000"),
            _sell_leg("USDT", "-5000", ts="1699000000000"),
            _sell_leg("BTC", "-0.05", ts="1700000000000", biz="biz-2"),
            _buy_leg("USDT", "3000", ts="1700000000000", biz="biz-2"),
        ],
    )

    result = bitget_sync_service.sync(db_session, test_user.id)

    # bought 0.1 @ 50000 USDT (-> 46000 EUR), sold 0.05 -- weighted avg unaffected by sale price
    assert result.assets[0].quantity == Decimal("0.05")
    assert result.assets[0].average_cost_basis == Decimal("46000.00")


def test_sync_deposit_marks_cost_basis_incomplete(db_session, test_user, monkeypatch):
    _patch_provider(
        monkeypatch,
        balances=[{"coin": "BTC", "available": "0.05", "frozen": "0", "locked": "0"}],
        records=[{"id": "dep-1", "coin": "BTC", "spotTaxType": "Deposit", "amount": "0.05", "fee": "0", "ts": "1700000000000", "bizOrderId": "biz-dep"}],
    )

    result = bitget_sync_service.sync(db_session, test_user.id)

    assert result.assets[0].quantity == Decimal("0.05")
    assert result.assets[0].cost_basis_incomplete is True
    assert result.assets[0].average_cost_basis is None


def test_sync_falls_back_to_real_balance_when_history_is_incomplete(db_session, test_user, monkeypatch):
    # Confirmed on a real account: a coin can have a much larger balance than its captured
    # buy/sell history explains (e.g. an initial acquisition older than the API's ledger
    # coverage). Selling far more than the replay ever recorded buying clamps the replayed
    # quantity toward zero -- nowhere near the real ~100-unit balance Bitget reports. The
    # sync must trust the real balance for quantity rather than silently show ~0, and must
    # not present a cost basis it can't actually vouch for.
    _patch_provider(
        monkeypatch,
        balances=[{"coin": "BTC", "available": "0.1", "frozen": "0", "locked": "0"}],
        records=[
            _buy_leg("BTC", "0.08", ts="1700000000000", biz="biz-1"),
            _sell_leg("USDT", "-4000", ts="1700000000000", biz="biz-1"),
            _sell_leg("BTC", "-0.5", ts="1700100000000", biz="biz-2"),
            _buy_leg("USDT", "25000", ts="1700100000000", biz="biz-2"),
        ],
    )

    result = bitget_sync_service.sync(db_session, test_user.id)

    asset = result.assets[0]
    assert asset.symbol == "BTC"
    assert asset.quantity == Decimal("0.1")  # the real Bitget balance, not the replay's ~0
    assert asset.cost_basis_incomplete is True
    assert asset.average_cost_basis is None
    assert asset.note is not None

    entry = db_session.query(FinancialEntry).filter(FinancialEntry.user_id == test_user.id).one()
    assert entry.quantity == Decimal("0.1")
    assert entry.average_cost_basis is None


def test_sync_price_failure_leaves_existing_entry_untouched(db_session, test_user, monkeypatch, today):
    # Confirmed during development: CoinGecko's free tier rate-limited mid-sync. The naive
    # "delete old entry, then fetch price, then create new one" order would delete the old
    # entry and then fail to recreate it, making the position vanish from the app entirely
    # until the next successful sync. The existing entry must survive a price-fetch failure.
    existing_entry = financial_service.create_entry(
        db_session,
        test_user.id,
        FinancialEntryCreate(
            entry_type="asset", category="holding", subcategory="crypto", label="Bitget SOL",
            amount=Decimal("500.00"), quantity=Decimal("5"), price_asset_id="solana", snapshot_date=today,
        ),
    )

    # "solana" has no mock price configured (see mock_provider._MOCK_COIN_PRICES) -- exercises
    # the compute_value_from_quantity failure path without a live network call.
    _patch_provider(
        monkeypatch,
        balances=[{"coin": "SOL", "available": "5", "frozen": "0", "locked": "0"}],
        records=[_buy_leg("SOL", "5"), _sell_leg("USDT", "-100")],
    )

    result = bitget_sync_service.sync(db_session, test_user.id)

    assert result.assets[0].error is not None
    assert result.assets[0].replaced_entry_labels == []
    still_there = db_session.query(FinancialEntry).filter(FinancialEntry.id == existing_entry.id).first()
    assert still_there is not None
    assert still_there.quantity == Decimal("5")


def test_sync_ignores_internal_transfers(db_session, test_user, monkeypatch):
    # Internal spot<->funding transfers must NOT be treated as external deposits/withdrawals
    # -- otherwise routine fund shuffling before every purchase would wrongly mark positions
    # as cost-basis-incomplete.
    _patch_provider(
        monkeypatch,
        balances=[{"coin": "BTC", "available": "0.1", "frozen": "0", "locked": "0"}],
        records=[
            {"id": "t1", "coin": "USDT", "spotTaxType": "Transfer in", "amount": "5000", "fee": "0", "ts": "1699999000000", "bizOrderId": "biz-transfer"},
            _buy_leg("BTC", "0.1", ts="1700000000000", biz="biz-1"),
            _sell_leg("USDT", "-5000", ts="1700000000000", biz="biz-1"),
        ],
    )

    result = bitget_sync_service.sync(db_session, test_user.id)

    assert result.assets[0].cost_basis_incomplete is False
    assert result.assets[0].average_cost_basis == Decimal("46000.00")
    # the "Transfer in" row must not have produced a Transaction row at all
    all_txns = db_session.query(Transaction).filter(Transaction.user_id == test_user.id).all()
    assert len(all_txns) == 1


def test_sync_replaces_existing_manual_entry_labeled_as_bitget(db_session, test_user, monkeypatch, today):
    manual_entry = financial_service.create_entry(
        db_session,
        test_user.id,
        FinancialEntryCreate(
            entry_type="asset", category="holding", subcategory="btc", label="Bitget BTC",
            quantity=Decimal("0.05"), price_asset_id="bitcoin", snapshot_date=today,
        ),
    )
    assert manual_entry.source == "manual"

    _patch_provider(
        monkeypatch,
        balances=[{"coin": "BTC", "available": "0.1", "frozen": "0", "locked": "0"}],
        records=[_buy_leg("BTC", "0.1"), _sell_leg("USDT", "-5000")],
    )

    result = bitget_sync_service.sync(db_session, test_user.id)

    assert result.assets[0].replaced_entry_labels == ["Bitget BTC"]
    remaining = db_session.query(FinancialEntry).filter(FinancialEntry.user_id == test_user.id).all()
    assert len(remaining) == 1
    assert remaining[0].source == "bitget"
    assert remaining[0].label == "Bitget"


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
        balances=[{"coin": "BTC", "available": "0.1", "frozen": "0", "locked": "0"}],
        records=[_buy_leg("BTC", "0.1"), _sell_leg("USDT", "-5000")],
    )

    result = bitget_sync_service.sync(db_session, test_user.id)

    assert result.assets[0].replaced_entry_labels == []
    still_there = db_session.query(FinancialEntry).filter(FinancialEntry.id == trade_republic_entry.id).first()
    assert still_there is not None
    assert still_there.quantity == Decimal("0.02")

    all_entries = db_session.query(FinancialEntry).filter(FinancialEntry.user_id == test_user.id).all()
    assert len(all_entries) == 2
    labels = {entry.label for entry in all_entries}
    assert labels == {"Trade Republic", "Bitget"}


def test_sync_is_idempotent_and_picks_up_new_purchase_on_rerun(db_session, test_user, monkeypatch):
    _patch_provider(
        monkeypatch,
        balances=[{"coin": "BTC", "available": "0.1", "frozen": "0", "locked": "0"}],
        records=[_buy_leg("BTC", "0.1"), _sell_leg("USDT", "-5000")],
    )
    bitget_sync_service.sync(db_session, test_user.id)
    result_again = bitget_sync_service.sync(db_session, test_user.id)

    assert result_again.assets[0].quantity == Decimal("0.1")
    assert db_session.query(Transaction).filter(Transaction.user_id == test_user.id).count() == 1

    _patch_provider(
        monkeypatch,
        balances=[{"coin": "BTC", "available": "0.2", "frozen": "0", "locked": "0"}],
        records=[
            _buy_leg("BTC", "0.1", ts="1700000000000", biz="biz-1"),
            _sell_leg("USDT", "-5000", ts="1700000000000", biz="biz-1"),
            _buy_leg("BTC", "0.1", ts="1700100000000", biz="biz-2"),
            _sell_leg("USDT", "-5000", ts="1700100000000", biz="biz-2"),
        ],
    )
    result_third = bitget_sync_service.sync(db_session, test_user.id)

    assert db_session.query(Transaction).filter(Transaction.user_id == test_user.id).count() == 2
    assert result_third.assets[0].quantity == Decimal("0.2")


def test_sync_unmapped_symbol_records_transactions_without_entry(db_session, test_user, monkeypatch):
    _patch_provider(
        monkeypatch,
        balances=[{"coin": "SOMECOIN", "available": "10", "frozen": "0", "locked": "0"}],
        records=[_buy_leg("SOMECOIN", "10"), _sell_leg("USDT", "-10")],
    )

    result = bitget_sync_service.sync(db_session, test_user.id)

    assert result.assets[0].coingecko_id is None
    assert result.assets[0].note is not None
    assert db_session.query(FinancialEntry).filter(FinancialEntry.user_id == test_user.id).count() == 0


def test_sync_skips_zero_balance_symbols(db_session, test_user, monkeypatch):
    _patch_provider(monkeypatch, balances=[{"coin": "BTC", "available": "0", "frozen": "0", "locked": "0"}])

    result = bitget_sync_service.sync(db_session, test_user.id)

    assert result.assets == []


def test_sync_skips_quote_currency_itself(db_session, test_user, monkeypatch):
    _patch_provider(monkeypatch, balances=[{"coin": "USDT", "available": "500", "frozen": "0", "locked": "0"}])

    result = bitget_sync_service.sync(db_session, test_user.id)

    assert result.assets == []


def test_sync_fx_rate_unavailable_fails_fast_with_clear_error(db_session, test_user, monkeypatch):
    from app.models.market_data import DataPointStatus, MarketDataPoint

    monkeypatch.setattr(
        "app.services.market_data_service.get_fresh",
        lambda db, metric, max_age_seconds=None: MarketDataPoint(
            metric="fx_usd_eur", status=DataPointStatus.error, value=None, source="mock"
        ),
    )
    _patch_provider(monkeypatch, balances=[{"coin": "BTC", "available": "0.1", "frozen": "0", "locked": "0"}])

    result = bitget_sync_service.sync(db_session, test_user.id)

    assert result.configured is True
    assert result.error is not None
    assert result.assets == []
