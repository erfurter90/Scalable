"""Average acquisition cost basis: an optional purchase price on creation, and a "Nachkauf"
(add-purchase) action that blends a new buy into the running weighted-average cost. The mock
FX rate (USD/EUR = 0.92, see providers/mock_provider.py) and mock coin prices make these
assertions exact and deterministic."""

from decimal import Decimal

import pytest

from app.core.config import get_settings
from app.models.financial_snapshot import EntryType
from app.schemas.financial import FinancialEntryCreate
from app.services import financial_service


@pytest.fixture(autouse=True)
def _mock_market_data(monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MODE", "mock")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _quantity_entry(
    quantity: str, snapshot_date, purchase_price: str | None = None, purchase_price_currency: str | None = None
) -> FinancialEntryCreate:
    return FinancialEntryCreate(
        entry_type=EntryType.asset,
        category="holding",
        subcategory="btc",
        label="wallet",
        quantity=Decimal(quantity),
        price_asset_id="bitcoin",
        purchase_price=Decimal(purchase_price) if purchase_price else None,
        purchase_price_currency=purchase_price_currency,
        snapshot_date=snapshot_date,
    )


def test_create_entry_with_purchase_price_in_eur(db_session, test_user, today):
    entry = financial_service.create_entry(db_session, test_user.id, _quantity_entry("0.1", today, "50000", "EUR"))

    assert entry.average_cost_basis == Decimal("50000.00")


def test_create_entry_with_purchase_price_in_usd_converts_via_fx_rate(db_session, test_user, today):
    entry = financial_service.create_entry(db_session, test_user.id, _quantity_entry("0.1", today, "50000", "USD"))

    # mock USD/EUR rate = 0.92 -> 50000 * 0.92 = 46000.00
    assert entry.average_cost_basis == Decimal("46000.00")


def test_create_entry_without_purchase_price_leaves_cost_basis_none(db_session, test_user, today):
    entry = financial_service.create_entry(db_session, test_user.id, _quantity_entry("0.1", today))

    assert entry.average_cost_basis is None


def test_purchase_price_requires_quantity_and_coin(today):
    with pytest.raises(ValueError, match="requires both"):
        FinancialEntryCreate(
            entry_type=EntryType.asset,
            category="holding",
            label="x",
            amount=Decimal("100.00"),
            purchase_price=Decimal(50000),
            snapshot_date=today,
        )


def test_add_purchase_blends_weighted_average(db_session, test_user, today):
    entry = financial_service.create_entry(db_session, test_user.id, _quantity_entry("0.1", today, "50000", "EUR"))

    updated = financial_service.add_purchase(
        db_session, test_user.id, entry.id, Decimal("0.1"), Decimal(60000), "EUR"
    )

    # (50000*0.1 + 60000*0.1) / 0.2 = 55000.00
    assert updated.average_cost_basis == Decimal("55000.00")
    assert updated.quantity == Decimal("0.2")
    # amount refreshed at the live mock price: 0.2 * 60000 (bitcoin/eur) = 12000.00
    assert updated.amount == Decimal("12000.00")


def test_add_purchase_without_existing_cost_basis_raises(db_session, test_user, today):
    # Blending requires a known starting average — establishing one for the first time is
    # set_cost_basis()'s job, not add_purchase()'s (which would otherwise silently misrepresent
    # the pre-existing quantity's unknown cost as the new purchase's price).
    entry = financial_service.create_entry(db_session, test_user.id, _quantity_entry("0.1", today))
    assert entry.average_cost_basis is None

    with pytest.raises(ValueError, match="noch kein Anschaffungspreis erfasst"):
        financial_service.add_purchase(db_session, test_user.id, entry.id, Decimal("0.05"), Decimal(70000), "EUR")


def test_set_cost_basis_establishes_average_for_existing_quantity(db_session, test_user, today):
    entry = financial_service.create_entry(db_session, test_user.id, _quantity_entry("0.1", today))
    assert entry.average_cost_basis is None

    updated = financial_service.set_cost_basis(db_session, test_user.id, entry.id, Decimal(70000), "EUR")

    assert updated.average_cost_basis == Decimal("70000.00")
    assert updated.quantity == Decimal("0.1")  # unchanged


def test_set_cost_basis_converts_usd(db_session, test_user, today):
    entry = financial_service.create_entry(db_session, test_user.id, _quantity_entry("0.1", today))

    updated = financial_service.set_cost_basis(db_session, test_user.id, entry.id, Decimal(50000), "USD")

    # mock USD/EUR rate = 0.92 -> 50000 * 0.92 = 46000.00
    assert updated.average_cost_basis == Decimal("46000.00")


def test_set_cost_basis_overwrites_existing_average(db_session, test_user, today):
    entry = financial_service.create_entry(db_session, test_user.id, _quantity_entry("0.1", today, "50000", "EUR"))

    updated = financial_service.set_cost_basis(db_session, test_user.id, entry.id, Decimal(80000), "EUR")

    assert updated.average_cost_basis == Decimal("80000.00")
    assert updated.quantity == Decimal("0.1")  # unaffected


def test_set_cost_basis_on_non_quantity_entry_raises(db_session, test_user, today):
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

    with pytest.raises(ValueError, match="mengenbasierte Einträge"):
        financial_service.set_cost_basis(db_session, test_user.id, entry.id, Decimal(100), "EUR")


def test_set_cost_basis_not_found_returns_none(db_session, test_user):
    assert financial_service.set_cost_basis(db_session, test_user.id, 999999, Decimal(100), "EUR") is None


def test_add_purchase_converts_usd_purchase(db_session, test_user, today):
    entry = financial_service.create_entry(db_session, test_user.id, _quantity_entry("0.1", today, "50000", "EUR"))

    updated = financial_service.add_purchase(
        db_session, test_user.id, entry.id, Decimal("0.1"), Decimal(60000), "USD"
    )

    # 60000 USD -> 60000*0.92 = 55200 EUR; blended: (50000*0.1 + 55200*0.1)/0.2 = 52600.00
    assert updated.average_cost_basis == Decimal("52600.00")


def test_add_purchase_on_non_quantity_entry_raises(db_session, test_user, today):
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

    with pytest.raises(ValueError, match="mengenbasierte Einträge"):
        financial_service.add_purchase(db_session, test_user.id, entry.id, Decimal(1), Decimal(100), "EUR")


def test_add_purchase_not_found_returns_none(db_session, test_user):
    assert (
        financial_service.add_purchase(db_session, test_user.id, 999999, Decimal(1), Decimal(100), "EUR") is None
    )


def test_add_purchase_unsupported_currency_raises(db_session, test_user, today):
    entry = financial_service.create_entry(db_session, test_user.id, _quantity_entry("0.1", today, "50000", "EUR"))

    with pytest.raises(ValueError, match="Nur EUR oder USD"):
        financial_service.add_purchase(db_session, test_user.id, entry.id, Decimal("0.1"), Decimal(100), "GBP")
