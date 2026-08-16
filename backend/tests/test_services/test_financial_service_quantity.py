"""Quantity-based valuation: entering "0.2 BTC" instead of a manually-calculated, immediately
stale EUR amount. The mock provider's fixed coin prices (see providers/mock_provider.py) make
these assertions exact and deterministic."""

from decimal import Decimal

import pytest

from app.core.config import get_settings
from app.models.financial_snapshot import EntryType
from app.schemas.financial import FinancialEntryCreate, FinancialEntryUpdate
from app.services import financial_service


@pytest.fixture(autouse=True)
def _mock_market_data(monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MODE", "mock")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_create_entry_with_quantity_computes_amount(db_session, test_user, today):
    data = FinancialEntryCreate(
        entry_type=EntryType.asset,
        category="holding",
        subcategory="btc",
        label="Bitvavo Wallet",
        quantity=Decimal("0.2"),
        price_asset_id="bitcoin",
        currency="EUR",
        snapshot_date=today,
    )

    entry = financial_service.create_entry(db_session, test_user.id, data)

    # mock price: bitcoin/eur = 60000.00 -> 0.2 * 60000.00 = 12000.00
    assert entry.amount == Decimal("12000.00")
    assert entry.quantity == Decimal("0.2")
    assert entry.price_asset_id == "bitcoin"


def test_create_entry_with_explicit_amount_ignores_quantity_fields(db_session, test_user, today):
    data = FinancialEntryCreate(
        entry_type=EntryType.asset,
        category="holding",
        subcategory="cash",
        label="checking",
        amount=Decimal("500.00"),
        snapshot_date=today,
    )

    entry = financial_service.create_entry(db_session, test_user.id, data)

    assert entry.amount == Decimal("500.00")
    assert entry.quantity is None


def test_create_entry_missing_amount_and_quantity_raises(db_session, test_user, today):
    with pytest.raises(ValueError):
        FinancialEntryCreate(
            entry_type=EntryType.asset,
            category="holding",
            subcategory="btc",
            label="x",
            snapshot_date=today,
        )


def test_create_entry_unknown_coin_raises_value_error(db_session, test_user, today):
    data = FinancialEntryCreate(
        entry_type=EntryType.asset,
        category="holding",
        subcategory="crypto",
        label="Mystery Coin",
        quantity=Decimal(10),
        price_asset_id="not-a-real-coin",
        snapshot_date=today,
    )

    with pytest.raises(ValueError, match="Could not fetch a current price"):
        financial_service.create_entry(db_session, test_user.id, data)

    # nothing should have been persisted
    assert financial_service.list_entries(db_session, test_user.id) == []


def test_update_entry_quantity_recomputes_amount(db_session, test_user, today):
    entry = financial_service.create_entry(
        db_session,
        test_user.id,
        FinancialEntryCreate(
            entry_type=EntryType.asset,
            category="holding",
            subcategory="btc",
            label="wallet",
            quantity=Decimal("0.1"),
            price_asset_id="bitcoin",
            snapshot_date=today,
        ),
    )
    assert entry.amount == Decimal("6000.00")  # 0.1 * 60000

    updated = financial_service.update_entry(
        db_session, test_user.id, entry.id, FinancialEntryUpdate(quantity=Decimal("0.3"))
    )

    assert updated.amount == Decimal("18000.00")  # 0.3 * 60000


def test_update_entry_explicit_amount_overrides_quantity_recompute(db_session, test_user, today):
    entry = financial_service.create_entry(
        db_session,
        test_user.id,
        FinancialEntryCreate(
            entry_type=EntryType.asset,
            category="holding",
            subcategory="btc",
            label="wallet",
            quantity=Decimal("0.1"),
            price_asset_id="bitcoin",
            snapshot_date=today,
        ),
    )

    updated = financial_service.update_entry(
        db_session, test_user.id, entry.id, FinancialEntryUpdate(amount=Decimal("999.00"))
    )

    assert updated.amount == Decimal("999.00")


def test_refresh_entry_value_recomputes_from_current_price(db_session, test_user, today):
    entry = financial_service.create_entry(
        db_session,
        test_user.id,
        FinancialEntryCreate(
            entry_type=EntryType.asset,
            category="holding",
            subcategory="btc",
            label="wallet",
            quantity=Decimal("0.2"),
            price_asset_id="bitcoin",
            snapshot_date=today,
        ),
    )
    assert entry.amount == Decimal("12000.00")

    # manually corrupt the stored amount to simulate a stale price, then refresh
    entry.amount = Decimal("1.00")
    db_session.commit()

    refreshed = financial_service.refresh_entry_value(db_session, test_user.id, entry.id)

    assert refreshed.amount == Decimal("12000.00")


def test_refresh_entry_value_without_quantity_raises(db_session, test_user, today):
    entry = financial_service.create_entry(
        db_session,
        test_user.id,
        FinancialEntryCreate(
            entry_type=EntryType.asset,
            category="holding",
            subcategory="cash",
            label="checking",
            amount=Decimal("500.00"),
            snapshot_date=today,
        ),
    )

    with pytest.raises(ValueError, match="no quantity/coin configured"):
        financial_service.refresh_entry_value(db_session, test_user.id, entry.id)


def test_refresh_entry_value_not_found_returns_none(db_session, test_user):
    assert financial_service.refresh_entry_value(db_session, test_user.id, 999999) is None
